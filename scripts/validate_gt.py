#!/usr/bin/env python3
"""
Validation des extractions contre la vérité terrain (Ground Truth).
Compare les données extraites avec les données vérifiées manuellement.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from collections import defaultdict


@dataclass
class GTMatch:
    """Un item qui correspond à la vérité terrain."""
    item_id: str
    item_type: str  # 'room' ou 'product'
    extracted_value: dict
    ground_truth_value: dict
    fields_matched: list
    fields_mismatched: list
    score: float  # 0.0 à 1.0


@dataclass
class GTMismatch:
    """Une différence entre extraction et vérité terrain."""
    item_id: str
    item_type: str
    field: str
    extracted_value: str
    expected_value: str
    severity: str  # 'critical', 'minor'


@dataclass
class GTReport:
    """Rapport de validation contre Ground Truth."""
    matches: list = field(default_factory=list)
    mismatches: list = field(default_factory=list)
    missing_in_extraction: list = field(default_factory=list)
    extra_in_extraction: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "matches": [asdict(m) for m in self.matches],
            "mismatches": [asdict(m) for m in self.mismatches],
            "missing_in_extraction": self.missing_in_extraction,
            "extra_in_extraction": self.extra_in_extraction,
            "metrics": self.metrics
        }
    
    def summary(self) -> str:
        """Résumé textuel du rapport."""
        m = self.metrics
        lines = [
            "=== Rapport de Validation Ground Truth ===",
            "",
            "--- Métriques globales ---",
            f"Accuracy:  {m.get('accuracy', 0):.1%}",
            f"Precision: {m.get('precision', 0):.1%}",
            f"Recall:    {m.get('recall', 0):.1%}",
            f"F1 Score:  {m.get('f1', 0):.1%}",
            "",
            f"Items vérifiés:  {m.get('ground_truth_count', 0)}",
            f"Items extraits:  {m.get('extracted_count', 0)}",
            f"Matches parfaits: {m.get('perfect_matches', 0)}",
            f"Matches partiels: {m.get('partial_matches', 0)}",
            f"Manquants:       {m.get('missing', 0)}",
        ]
        
        if self.mismatches:
            lines.append("\n--- Principales différences ---")
            for mm in self.mismatches[:5]:
                lines.append(f"  • {mm.item_id}.{mm.field}: '{mm.extracted_value}' vs '{mm.expected_value}'")
        
        if self.missing_in_extraction:
            lines.append("\n--- Manquants dans l'extraction ---")
            for item in self.missing_in_extraction[:5]:
                lines.append(f"  • {item}")
        
        return "\n".join(lines)


def normalize_string(s: str) -> str:
    """Normalise une chaîne pour comparaison."""
    if not s:
        return ""
    return s.upper().strip().replace("-", " ").replace("_", " ")


def infer_room_type(name: str) -> str:
    """Infère le type de local à partir du nom."""
    name = normalize_string(name)
    if not name:
        return ""
    if "CLASSE" in name or "MATERNELLE" in name:
        return "CLASSE"
    if "WC" in name or "TOILETTE" in name or "S.D.B" in name or "SALLE DE BAIN" in name:
        return "WC"
    if "CORRIDOR" in name:
        return "CORRIDOR"
    if "GYMNASE" in name:
        return "GYMNASE"
    if "RANGEMENT" in name or "REMISE" in name or "DÉPÔT" in name or "ENTREPOSAGE" in name:
        return "RANGEMENT"
    if "VESTIAIRE" in name:
        return "VESTIAIRE"
    if "ÉLECTRIQUE" in name or "MÉCANIQUE" in name or "CHAUFFERIE" in name or "TECHNIQUE" in name:
        return "TECHNIQUE"
    if "CONCIERGERIE" in name:
        return "SERVICE"
    if "ESCALIER" in name or "VESTIBULE" in name:
        return "CIRCULATION"
    if "BUREAU" in name or "SECRÉTARIAT" in name or "DIRECTION" in name:
        return "BUREAU"
    if "SERVICE DE GARDE" in name:
        return "SERVICE"
    return "AUTRE"


def compare_room(extracted: dict, ground_truth: dict) -> tuple:
    """
    Compare un local extrait avec la vérité terrain.
    
    Returns:
        (score, matched_fields, mismatched_fields)
    """
    fields_to_check = ["id", "name", "block", "floor", "type"]
    matched = []
    mismatched = []
    
    for field in fields_to_check:
        ext_val = extracted.get(field, "")
        gt_val = ground_truth.get(field, "")
        
        # Inférer le type depuis le nom si absent
        if field == "type" and not ext_val:
            ext_val = infer_room_type(extracted.get("name", ""))
        
        # Normaliser pour comparaison
        ext_norm = normalize_string(str(ext_val)) if ext_val else ""
        gt_norm = normalize_string(str(gt_val)) if gt_val else ""
        
        if ext_norm == gt_norm:
            matched.append(field)
        elif field == "name" and gt_norm and ext_norm and (gt_norm in ext_norm or ext_norm in gt_norm):
            # Match partiel pour les noms (bidirectional)
            matched.append(field)
        elif field == "name" and _fuzzy_name_match(ext_norm, gt_norm):
            # Fuzzy match pour synonymes connus
            matched.append(field)
        else:
            mismatched.append({
                "field": field,
                "extracted": ext_val,
                "expected": gt_val
            })
    
    # Calculer le score
    total_fields = len(fields_to_check)
    score = len(matched) / total_fields if total_fields > 0 else 0
    
    return score, matched, mismatched


def _fuzzy_name_match(a: str, b: str) -> bool:
    """Vérifie si deux noms de locaux sont des synonymes connus."""
    synonyms = [
        {"WC", "TOILETTES", "TOILETTE", "W.C.", "SALLE DE BAIN", "S.D.B."},
        {"RANGEMENT", "REMISE", "DÉPÔT", "ENTREPOSAGE"},
        {"TECHNIQUE", "LOCAL TECHNIQUE", "LOCAL MÉCANIQUE", "MÉCANIQUE"},
        {"ÉLECTRIQUE", "LOCAL ÉLECTRIQUE"},
    ]
    for group in synonyms:
        norm_group = {normalize_string(s) for s in group}
        if a in norm_group and b in norm_group:
            return True
    return False


def compare_product(extracted: dict, ground_truth: dict) -> tuple:
    """
    Compare un produit extrait avec la vérité terrain.
    
    Returns:
        (score, matched_fields, mismatched_fields)
    """
    fields_to_check = ["section", "category", "product", "type"]
    matched = []
    mismatched = []
    
    for field in fields_to_check:
        ext_val = extracted.get(field, "")
        gt_val = ground_truth.get(field, "")
        
        ext_norm = normalize_string(str(ext_val)) if ext_val else ""
        gt_norm = normalize_string(str(gt_val)) if gt_val else ""
        
        # Pour les produits, on accepte un match partiel
        if ext_norm == gt_norm:
            matched.append(field)
        elif gt_norm and gt_norm in ext_norm:
            matched.append(field)
        elif ext_norm and ext_norm in gt_norm:
            matched.append(field)
        else:
            mismatched.append({
                "field": field,
                "extracted": ext_val,
                "expected": gt_val
            })
    
    total_fields = len(fields_to_check)
    score = len(matched) / total_fields if total_fields > 0 else 0
    
    return score, matched, mismatched


def validate_against_ground_truth(extracted: dict, ground_truth: dict) -> GTReport:
    """
    Compare les données extraites avec la vérité terrain.
    
    Args:
        extracted: Données extraites (rooms_complete.json ou produits)
        ground_truth: Vérité terrain (ground_truth/emj.json)
    
    Returns:
        GTReport avec accuracy, precision, recall, F1, et détails
    """
    report = GTReport()
    
    # Indexer les données extraites par ID
    extracted_rooms = {r.get("id", ""): r for r in extracted.get("rooms", [])}
    gt_rooms = {r.get("id", ""): r for r in ground_truth.get("verified_rooms", [])}
    
    # Comparer les locaux
    true_positives = 0
    partial_matches = 0
    
    for gt_id, gt_room in gt_rooms.items():
        if gt_id in extracted_rooms:
            ext_room = extracted_rooms[gt_id]
            score, matched, mismatched = compare_room(ext_room, gt_room)
            
            report.matches.append(GTMatch(
                item_id=gt_id,
                item_type="room",
                extracted_value=ext_room,
                ground_truth_value=gt_room,
                fields_matched=matched,
                fields_mismatched=[m["field"] for m in mismatched],
                score=score
            ))
            
            if score == 1.0:
                true_positives += 1
            else:
                partial_matches += 1
                # Ajouter les mismatches
                for mm in mismatched:
                    report.mismatches.append(GTMismatch(
                        item_id=gt_id,
                        item_type="room",
                        field=mm["field"],
                        extracted_value=str(mm["extracted"]),
                        expected_value=str(mm["expected"]),
                        severity="critical" if mm["field"] in ["id", "name"] else "minor"
                    ))
        else:
            report.missing_in_extraction.append(gt_id)
    
    # Identifier les items en trop
    for ext_id in extracted_rooms:
        if ext_id not in gt_rooms:
            # Ce n'est pas forcément une erreur - juste pas dans le ground truth
            report.extra_in_extraction.append(ext_id)
    
    # Valider les produits si disponibles
    gt_products = ground_truth.get("verified_products", [])
    ext_products = extracted.get("products", [])
    
    if gt_products and ext_products:
        # Indexer par section CSI
        ext_by_section = defaultdict(list)
        for p in ext_products:
            section = p.get("section", p.get("csi_code", ""))
            ext_by_section[section].append(p)
        
        for gt_prod in gt_products:
            gt_section = gt_prod.get("section", "")
            found = False
            
            for ext_prod in ext_by_section.get(gt_section, []):
                score, matched, mismatched = compare_product(ext_prod, gt_prod)
                if score > 0.5:
                    found = True
                    report.matches.append(GTMatch(
                        item_id=gt_section,
                        item_type="product",
                        extracted_value=ext_prod,
                        ground_truth_value=gt_prod,
                        fields_matched=matched,
                        fields_mismatched=[m["field"] for m in mismatched],
                        score=score
                    ))
                    break
            
            if not found:
                report.missing_in_extraction.append(f"Product: {gt_section}")
    
    # Calculer les métriques
    gt_count = len(gt_rooms)
    ext_count = len(extracted_rooms)
    matched_count = len([m for m in report.matches if m.item_type == "room"])
    perfect_count = len([m for m in report.matches if m.item_type == "room" and m.score == 1.0])
    
    # Precision = TP / (TP + FP) - combien d'extraits sont corrects
    # Recall = TP / (TP + FN) - combien de GT sont trouvés
    precision = matched_count / ext_count if ext_count > 0 else 0
    recall = matched_count / gt_count if gt_count > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    # Accuracy basée sur les scores moyens
    avg_score = sum(m.score for m in report.matches if m.item_type == "room") / matched_count if matched_count > 0 else 0
    
    report.metrics = {
        "accuracy": avg_score,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "ground_truth_count": gt_count,
        "extracted_count": ext_count,
        "perfect_matches": perfect_count,
        "partial_matches": matched_count - perfect_count,
        "missing": len(report.missing_in_extraction),
        "extra": len(report.extra_in_extraction)
    }
    
    return report


def validate_room_types(extracted: dict, ground_truth: dict) -> dict:
    """Valide la distribution des types de locaux."""
    gt_distribution = ground_truth.get("room_type_distribution", {})
    
    # Calculer la distribution extraite
    extracted_distribution = defaultdict(int)
    for room in extracted.get("rooms", []):
        room_name = room.get("name", "").upper()
        
        # Classifier le type
        if "CLASSE" in room_name:
            extracted_distribution["CLASSE"] += 1
        elif "CORRIDOR" in room_name:
            extracted_distribution["CORRIDOR"] += 1
        elif "WC" in room_name or "TOILETTE" in room_name:
            extracted_distribution["WC"] += 1
        elif "RANGEMENT" in room_name or "REMISE" in room_name:
            extracted_distribution["RANGEMENT"] += 1
        elif "ÉLECTRIQUE" in room_name or "MÉCANIQUE" in room_name or "CHAUFFERIE" in room_name:
            extracted_distribution["TECHNIQUE"] += 1
        elif "CONCIERGERIE" in room_name:
            extracted_distribution["SERVICE"] += 1
        elif "ESCALIER" in room_name or "VESTIBULE" in room_name:
            extracted_distribution["CIRCULATION"] += 1
        elif "VESTIAIRE" in room_name:
            extracted_distribution["VESTIAIRE"] += 1
        elif "GYMNASE" in room_name:
            extracted_distribution["GYMNASE"] += 1
        else:
            extracted_distribution["AUTRE"] += 1
    
    # Comparer
    comparison = {}
    all_types = set(gt_distribution.keys()) | set(extracted_distribution.keys())
    
    for room_type in all_types:
        gt_val = gt_distribution.get(room_type, 0)
        ext_val = extracted_distribution.get(room_type, 0)
        comparison[room_type] = {
            "ground_truth": gt_val,
            "extracted": ext_val,
            "difference": ext_val - gt_val,
            "match": gt_val == ext_val
        }
    
    return comparison


def main():
    """Point d'entrée CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validation contre Ground Truth")
    parser.add_argument("--extracted", "-e", required=True, help="Fichier JSON des données extraites")
    parser.add_argument("--ground-truth", "-g", required=True, help="Fichier JSON de vérité terrain")
    parser.add_argument("--output", "-o", help="Fichier de sortie JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Mode verbeux")
    
    args = parser.parse_args()
    
    # Charger les données
    with open(args.extracted) as f:
        extracted_data = json.load(f)
    
    with open(args.ground_truth) as f:
        gt_data = json.load(f)
    
    # Exécuter la validation
    report = validate_against_ground_truth(extracted_data, gt_data)
    
    # Afficher le résumé
    print(report.summary())
    
    # Validation des types
    if args.verbose:
        print("\n--- Distribution des types de locaux ---")
        type_comparison = validate_room_types(extracted_data, gt_data)
        for room_type, data in sorted(type_comparison.items()):
            status = "✓" if data["match"] else "✗"
            print(f"  {status} {room_type}: {data['extracted']} extraits vs {data['ground_truth']} attendus (diff: {data['difference']:+d})")
    
    # Sauvegarder si demandé
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"\nRapport sauvegardé: {output_path}")


if __name__ == "__main__":
    main()
