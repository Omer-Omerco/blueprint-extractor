#!/usr/bin/env python3
"""
Cross-validation entre plans (locaux) et devis (produits/finitions).
Vérifie la cohérence des données extraites.
"""

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from collections import defaultdict


@dataclass
class Match:
    """Un match entre plan et devis."""
    room_id: str
    room_name: str
    devis_section: str
    match_type: str  # 'direct', 'inferred', 'partial'
    confidence: float
    details: str = ""


@dataclass
class Mismatch:
    """Une incohérence détectée."""
    room_id: str
    field: str  # 'dimensions', 'finition', 'type'
    plan_value: str
    devis_value: str
    severity: str  # 'critical', 'warning', 'info'
    message: str


@dataclass
class Missing:
    """Un élément manquant."""
    source: str  # 'plan' ou 'devis'
    item_id: str
    item_name: str
    expected_in: str
    message: str


@dataclass
class ValidationReport:
    """Rapport de cross-validation complet."""
    matches: list = field(default_factory=list)
    mismatches: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "matches": [asdict(m) for m in self.matches],
            "mismatches": [asdict(m) for m in self.mismatches],
            "missing": [asdict(m) for m in self.missing],
            "stats": self.stats
        }
    
    def summary(self) -> str:
        """Résumé textuel du rapport."""
        lines = [
            "=== Rapport de Cross-Validation ===",
            f"Matches: {len(self.matches)}",
            f"Mismatches: {len(self.mismatches)}",
            f"Missing: {len(self.missing)}",
            "",
            f"Taux de correspondance: {self.stats.get('match_rate', 0):.1%}",
            f"Rooms vérifiés: {self.stats.get('rooms_checked', 0)}",
            f"Sections devis analysées: {self.stats.get('devis_sections', 0)}",
        ]
        
        if self.mismatches:
            lines.append("\n--- Incohérences critiques ---")
            critical = [m for m in self.mismatches if m.severity == 'critical']
            for m in critical[:5]:
                lines.append(f"  • {m.room_id}: {m.message}")
        
        if self.missing:
            lines.append("\n--- Éléments manquants ---")
            for m in self.missing[:5]:
                lines.append(f"  • {m.item_id} ({m.source}): {m.message}")
        
        return "\n".join(lines)


def normalize_room_name(name: str) -> str:
    """Normalise un nom de local pour comparaison."""
    name = name.upper().strip()
    # Remplacements courants
    replacements = {
        "W.C.": "WC",
        "W-C": "WC",
        "SALLE DE BAIN": "WC",
        "TOILETTE": "WC",
        "TOILETTES": "WC",
        "SALLE DE CLASSE": "CLASSE",
        "LOCAL DE CLASSE": "CLASSE",
        "RANGEMENT": "RANGEMENT",
        "REMISE": "RANGEMENT",
        "ENTREPOSAGE": "RANGEMENT",
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name


def extract_room_type(room_name: str) -> str:
    """Extrait le type de local (CLASSE, WC, CORRIDOR, etc.)."""
    name = normalize_room_name(room_name)
    
    # Types principaux
    if "CLASSE" in name:
        return "CLASSE"
    if "WC" in name or "TOILETTE" in name:
        return "WC"
    if "CORRIDOR" in name:
        return "CORRIDOR"
    if "GYMNASE" in name:
        return "GYMNASE"
    if "RANGEMENT" in name or "REMISE" in name:
        return "RANGEMENT"
    if "BUREAU" in name:
        return "BUREAU"
    if "VESTIAIRE" in name:
        return "VESTIAIRE"
    if "ÉLECTRIQUE" in name:
        return "TECHNIQUE"
    if "MÉCANIQUE" in name or "CHAUFFERIE" in name:
        return "TECHNIQUE"
    if "CONCIERGERIE" in name:
        return "SERVICE"
    if "ESCALIER" in name:
        return "CIRCULATION"
    if "VESTIBULE" in name:
        return "CIRCULATION"
    
    return "AUTRE"


def find_room_in_devis(room_id: str, room_name: str, devis_data: dict) -> list:
    """Cherche un local dans les données du devis."""
    matches = []
    room_id_pattern = re.compile(re.escape(room_id), re.IGNORECASE)
    
    # Parcourir les sections du devis
    sections = devis_data.get("sections", [])
    for section in sections:
        content = section.get("content", "")
        title = section.get("title", "")
        
        # Chercher l'ID du local
        if room_id_pattern.search(content) or room_id_pattern.search(title):
            matches.append({
                "section": title,
                "csi_code": section.get("csi_code"),
                "page": section.get("page_num"),
                "match_type": "direct"
            })
        
        # Chercher le nom du local
        if room_name.upper() in content.upper():
            matches.append({
                "section": title,
                "csi_code": section.get("csi_code"),
                "page": section.get("page_num"),
                "match_type": "name"
            })
        
        # Parcourir les sous-sections
        for subsection in section.get("subsections", []):
            sub_content = subsection.get("content", "")
            sub_title = subsection.get("title", "")
            
            if room_id_pattern.search(sub_content) or room_id_pattern.search(sub_title):
                matches.append({
                    "section": f"{title} > {sub_title}",
                    "csi_code": subsection.get("csi_code") or section.get("csi_code"),
                    "page": subsection.get("page_num"),
                    "match_type": "direct"
                })
    
    return matches


def get_expected_finishes(room_type: str) -> dict:
    """Retourne les finitions attendues par type de local."""
    finishes = {
        "CLASSE": {
            "mur": ["peinture", "latex"],
            "plancher": ["VCT", "vinyle", "linoléum"],
            "plafond": ["acoustique", "suspendu"]
        },
        "WC": {
            "mur": ["céramique", "carrelage", "peinture époxy"],
            "plancher": ["céramique", "carrelage", "époxy"],
            "plafond": ["gypse", "peinture"]
        },
        "CORRIDOR": {
            "mur": ["peinture", "latex"],
            "plancher": ["VCT", "terrazzo", "vinyle"],
            "plafond": ["acoustique", "suspendu"]
        },
        "GYMNASE": {
            "mur": ["peinture époxy", "bloc béton"],
            "plancher": ["bois franc", "synthétique sport"],
            "plafond": ["acoustique", "structure apparente"]
        },
        "TECHNIQUE": {
            "mur": ["peinture", "béton"],
            "plancher": ["béton", "époxy"],
            "plafond": ["structure apparente"]
        }
    }
    return finishes.get(room_type, {})


def cross_validate(rooms_json: dict, devis_json: dict) -> ValidationReport:
    """
    Vérifie la cohérence entre plans (locaux) et devis.
    
    Args:
        rooms_json: Données extraites des plans (rooms_complete.json)
        devis_json: Données extraites du devis (devis_final.json ou devis_products.json)
    
    Returns:
        ValidationReport avec matches, mismatches, missing
    """
    report = ValidationReport()
    
    rooms = rooms_json.get("rooms", [])
    rooms_by_type = defaultdict(list)
    rooms_found_in_devis = set()
    
    # Indexer les rooms par type
    for room in rooms:
        room_type = extract_room_type(room.get("name", ""))
        rooms_by_type[room_type].append(room)
    
    # Vérifier chaque local
    for room in rooms:
        room_id = room.get("id", "")
        room_name = room.get("name", "")
        room_type = extract_room_type(room_name)
        
        # Chercher dans le devis
        devis_matches = find_room_in_devis(room_id, room_name, devis_json)
        
        if devis_matches:
            rooms_found_in_devis.add(room_id)
            # Prendre le meilleur match
            best_match = max(devis_matches, key=lambda m: 1 if m["match_type"] == "direct" else 0.5)
            
            report.matches.append(Match(
                room_id=room_id,
                room_name=room_name,
                devis_section=best_match["section"],
                match_type=best_match["match_type"],
                confidence=0.9 if best_match["match_type"] == "direct" else 0.6,
                details=f"Page {best_match.get('page', '?')}"
            ))
        else:
            # Local non trouvé dans le devis
            # Ce n'est pas forcément une erreur - vérifier si le type de local
            # a des spécifications génériques dans le devis
            expected_finishes = get_expected_finishes(room_type)
            
            if expected_finishes:
                report.missing.append(Missing(
                    source="devis",
                    item_id=room_id,
                    item_name=room_name,
                    expected_in=f"Section finitions ({room_type})",
                    message=f"Local {room_id} non trouvé explicitement dans le devis"
                ))
            else:
                # Local technique ou spécial
                report.matches.append(Match(
                    room_id=room_id,
                    room_name=room_name,
                    devis_section="(spécifications génériques)",
                    match_type="inferred",
                    confidence=0.4,
                    details="Pas de mention explicite, applique specs génériques"
                ))
    
    # Vérifier les types de finitions cohérents
    finish_sections = ["09", "096"]  # Sections CSI pour finitions
    for room in rooms:
        room_type = extract_room_type(room.get("name", ""))
        expected = get_expected_finishes(room_type)
        
        if expected and room.get("id") in rooms_found_in_devis:
            # Vérifier que les finitions attendues sont dans le devis
            # (simplification - en réalité, il faudrait parser le contenu détaillé)
            pass
    
    # Statistiques
    total_rooms = len(rooms)
    matched_rooms = len([m for m in report.matches if m.match_type in ["direct", "name"]])
    
    report.stats = {
        "total_rooms": total_rooms,
        "rooms_checked": total_rooms,
        "matched_rooms": matched_rooms,
        "match_rate": matched_rooms / total_rooms if total_rooms > 0 else 0,
        "devis_sections": len(devis_json.get("sections", [])),
        "rooms_by_type": {k: len(v) for k, v in rooms_by_type.items()},
        "critical_mismatches": len([m for m in report.mismatches if m.severity == "critical"]),
        "missing_count": len(report.missing)
    }
    
    return report


def validate_dimensions(rooms_json: dict, devis_json: dict) -> list:
    """Vérifie que les dimensions correspondent entre plans et devis."""
    mismatches = []
    
    # Extraire les dimensions mentionnées dans le devis
    # Format typique: "Local A-101: 25'-0\" x 30'-0\""
    dimension_pattern = re.compile(
        r'([A-C]-\d{3})\s*[:\-]\s*(\d+[\'\-]\d*[\"]*)\s*[xX×]\s*(\d+[\'\-]\d*[\"]*)',
        re.IGNORECASE
    )
    
    devis_dimensions = {}
    for section in devis_json.get("sections", []):
        content = section.get("content", "")
        for match in dimension_pattern.finditer(content):
            room_id = match.group(1).upper()
            width = match.group(2)
            length = match.group(3)
            devis_dimensions[room_id] = {"width": width, "length": length}
    
    # Comparer avec les plans (si dimensions disponibles)
    for room in rooms_json.get("rooms", []):
        room_id = room.get("id", "").upper()
        if room_id in devis_dimensions:
            plan_dims = room.get("dimensions", {})
            devis_dims = devis_dimensions[room_id]
            
            if plan_dims and plan_dims != devis_dims:
                mismatches.append(Mismatch(
                    room_id=room_id,
                    field="dimensions",
                    plan_value=str(plan_dims),
                    devis_value=str(devis_dims),
                    severity="warning",
                    message=f"Dimensions différentes pour {room_id}"
                ))
    
    return mismatches


def main():
    """Point d'entrée CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Cross-validation plans vs devis")
    parser.add_argument("--rooms", "-r", required=True, help="Fichier JSON des locaux (rooms_complete.json)")
    parser.add_argument("--devis", "-d", required=True, help="Fichier JSON du devis")
    parser.add_argument("--output", "-o", help="Fichier de sortie JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Mode verbeux")
    
    args = parser.parse_args()
    
    # Charger les données
    with open(args.rooms) as f:
        rooms_data = json.load(f)
    
    with open(args.devis) as f:
        devis_data = json.load(f)
    
    # Exécuter la validation
    report = cross_validate(rooms_data, devis_data)
    
    # Ajouter validation des dimensions
    dim_mismatches = validate_dimensions(rooms_data, devis_data)
    report.mismatches.extend(dim_mismatches)
    
    # Afficher le résumé
    print(report.summary())
    
    # Sauvegarder si demandé
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"\nRapport sauvegardé: {output_path}")
    
    if args.verbose:
        print("\n--- Détails des matches ---")
        for m in report.matches[:10]:
            print(f"  {m.room_id}: {m.devis_section} ({m.match_type}, {m.confidence:.0%})")


if __name__ == "__main__":
    main()
