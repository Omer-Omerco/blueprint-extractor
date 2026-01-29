#!/usr/bin/env python3
"""
Cross-validation entre plans (locaux) et devis (spécifications).
Vérifie la cohérence des données extraites.

Approach:
- Le devis ne référence PAS les locaux par ID (A-101, B-205, etc.)
- Il référence des TYPES de locaux (toilettes, classes, corridors, gymnase, etc.)
  et leur assigne des systèmes de finition (peinture P01-P08, céramique, VCT, etc.)
- La cross-validation vérifie que chaque type de local dans les plans
  a une couverture dans le devis, et vice versa.
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
    match_type: str  # 'direct', 'type_match', 'inferred'
    confidence: float
    details: str = ""


@dataclass
class Mismatch:
    """Une incohérence détectée."""
    room_id: str
    field: str  # 'dimensions', 'finition', 'type', 'coverage'
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
            lines.append("\n--- Incohérences ---")
            for m in self.mismatches[:10]:
                lines.append(f"  • [{m.severity}] {m.room_id}: {m.message}")
        
        if self.missing:
            lines.append("\n--- Éléments manquants ---")
            for m in self.missing[:10]:
                lines.append(f"  • {m.item_id} ({m.source}): {m.message}")
        
        return "\n".join(lines)
    
    def to_markdown(self) -> str:
        """Génère un rapport markdown détaillé."""
        lines = [
            "# Rapport de Cross-Validation Plans ↔ Devis",
            "",
            "## Résumé",
            "",
            f"| Métrique | Valeur |",
            f"|----------|--------|",
            f"| Locaux dans les plans | {self.stats.get('total_rooms', 0)} |",
            f"| Locaux vérifiés | {self.stats.get('rooms_checked', 0)} |",
            f"| Correspondances trouvées | {len(self.matches)} |",
            f"| Incohérences | {len(self.mismatches)} |",
            f"| Éléments manquants | {len(self.missing)} |",
            f"| **Taux de correspondance** | **{self.stats.get('match_rate', 0):.1%}** |",
            f"| Sections CSI analysées | {self.stats.get('devis_sections', 0)} |",
            "",
        ]
        
        # Room types coverage
        if self.stats.get('room_type_coverage'):
            lines.append("## Couverture par type de local")
            lines.append("")
            lines.append("| Type | Plans | Devis CSI | Couvert? |")
            lines.append("|------|-------|-----------|----------|")
            for rt, info in sorted(self.stats['room_type_coverage'].items()):
                count = info.get('count', 0)
                csi = ', '.join(info.get('csi_sections', [])) or '—'
                covered = '✅' if info.get('covered') else '❌'
                lines.append(f"| {rt} | {count} | {csi} | {covered} |")
            lines.append("")
        
        # CSI sections that reference rooms
        if self.stats.get('csi_room_refs'):
            lines.append("## Sections CSI avec références aux locaux")
            lines.append("")
            for code, info in sorted(self.stats['csi_room_refs'].items()):
                title = info.get('title', '')
                room_types = ', '.join(info.get('room_types_referenced', []))
                lines.append(f"- **{code}** {title}: {room_types}")
            lines.append("")
        
        # Matches
        if self.matches:
            lines.append("## Correspondances")
            lines.append("")
            lines.append("| Local | Nom | Section devis | Type | Confiance |")
            lines.append("|-------|-----|---------------|------|-----------|")
            for m in self.matches:
                lines.append(f"| {m.room_id} | {m.room_name} | {m.devis_section} | {m.match_type} | {m.confidence:.0%} |")
            lines.append("")
        
        # Mismatches
        if self.mismatches:
            lines.append("## Incohérences")
            lines.append("")
            for m in self.mismatches:
                emoji = '🔴' if m.severity == 'critical' else '🟡' if m.severity == 'warning' else 'ℹ️'
                lines.append(f"- {emoji} **{m.room_id}** ({m.field}): {m.message}")
            lines.append("")
        
        # Missing
        if self.missing:
            lines.append("## Éléments manquants")
            lines.append("")
            for m in self.missing:
                lines.append(f"- **{m.item_id}** ({m.item_name}): {m.message} [source: {m.source}]")
            lines.append("")
        
        return "\n".join(lines)


def normalize_room_name(name: str) -> str:
    """Normalise un nom de local pour comparaison."""
    name = name.upper().strip()
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
    
    if "CLASSE" in name:
        return "CLASSE"
    if "WC" in name or "TOILETTE" in name:
        return "WC"
    if "CORRIDOR" in name:
        return "CORRIDOR"
    if "GYMNASE" in name:
        return "GYMNASE"
    if "RANGEMENT" in name or "REMISE" in name or "DÉPÔT" in name:
        return "RANGEMENT"
    if "BUREAU" in name or "SECRÉTARIAT" in name:
        return "BUREAU"
    if "VESTIAIRE" in name:
        return "VESTIAIRE"
    if "ÉLECTRIQUE" in name:
        return "TECHNIQUE"
    if "MÉCANIQUE" in name or "CHAUFFERIE" in name:
        return "TECHNIQUE"
    if "TECHNIQUE" in name:
        return "TECHNIQUE"
    if "CONCIERGERIE" in name or "ENTRETIEN" in name:
        return "SERVICE"
    if "SERVICE DE GARDE" in name:
        return "SERVICE"
    if "ESCALIER" in name:
        return "CIRCULATION"
    if "VESTIBULE" in name:
        return "CIRCULATION"
    if "MULTIFONCTIONNELLE" in name:
        return "SALLE"
    if "SALLE" in name:
        return "SALLE"
    if "CONSULTATION" in name or "ORTHO" in name or "PSYCHO" in name:
        return "BUREAU"
    if "ALCÔVE" in name:
        return "CLASSE"
    
    return "AUTRE"


# ============================================================
# Devis parsing: extract room type references from devis text
# ============================================================

# Room type keywords in French devis text
ROOM_TYPE_KEYWORDS = {
    "CLASSE": [
        r"classe[s]?", r"salle[s]?\s+de\s+classe",
        r"local\s+d['\u2019]enseignement",
    ],
    "WC": [
        r"toilette[s]?", r"salle[s]?\s+de\s+(?:bain|toilette)",
        r"douche[s]?", r"w\.?c\.?",
    ],
    "CORRIDOR": [
        r"corridor[s]?", r"couloir[s]?",
    ],
    "GYMNASE": [
        r"gymnase[s]?", r"sport",
    ],
    "RANGEMENT": [
        r"rangement[s]?", r"dépôt[s]?", r"remise[s]?",
        r"entreposage", r"entrepôt",
    ],
    "BUREAU": [
        r"bureau[x]?", r"administration",
        r"secrétariat",
    ],
    "VESTIAIRE": [
        r"vestiaire[s]?",
    ],
    "TECHNIQUE": [
        r"mécanique[s]?", r"électrique[s]?",
        r"technique[s]?", r"chaufferie",
        r"salle[s]?\s+mécanique", r"salle[s]?\s+électrique",
    ],
    "SERVICE": [
        r"conciergerie[s]?", r"entretien",
        r"service\s+de\s+garde",
    ],
    "CIRCULATION": [
        r"escalier[s]?", r"vestibule[s]?",
        r"hall[s]?", r"entrée[s]?",
    ],
    "SALLE": [
        r"salle[s]?\s+(?:multifonctionnelle|polyvalente|communautaire|des?\s+professeur)",
        r"multifonctionnelle",
    ],
}

# Compiled patterns for room type detection
_ROOM_TYPE_PATTERNS = {}
for rtype, keywords in ROOM_TYPE_KEYWORDS.items():
    combined = "|".join(keywords)
    _ROOM_TYPE_PATTERNS[rtype] = re.compile(
        r"(?i)\b(?:" + combined + r")\b"
    )


def detect_room_types_in_text(text: str) -> dict:
    """
    Detect room type references in a text block.
    Returns {room_type: [list of context snippets]}.
    """
    results = defaultdict(list)
    for rtype, pattern in _ROOM_TYPE_PATTERNS.items():
        for m in pattern.finditer(text):
            start = max(0, m.start() - 40)
            end = min(len(text), m.end() + 40)
            context = text[start:end].replace('\n', ' ').strip()
            results[rtype].append(context)
    return dict(results)


# ============================================================
# Devis CSI section extraction from raw text
# ============================================================

def parse_devis_sections_from_text(devis_text: str) -> list:
    """
    Parse CSI sections from devis full text.
    Returns list of dicts with code, title, pages, room_types_referenced.
    """
    pages = devis_text.split('--- Page ')
    
    sections = {}
    current_code = None
    
    for i in range(1, len(pages)):
        page = pages[i]
        # Find section header
        m = re.search(r'Section\s+(\d{2}\s+\d{2}\s+\d{2})', page)
        if m:
            code = m.group(1)
            # Extract title from context
            title = _extract_section_title(page, code)
            
            if code not in sections:
                sections[code] = {
                    'code': code,
                    'title': title,
                    'pages': [],
                    'text': '',
                    'room_types': {},
                }
            sections[code]['pages'].append(i)
            sections[code]['text'] += page
    
    # Detect room types in each section
    for code, sec in sections.items():
        sec['room_types'] = detect_room_types_in_text(sec['text'])
    
    return list(sections.values())


def _extract_section_title(page_text: str, code: str) -> str:
    """Extract section title from page text."""
    lines = page_text.split('\n')
    for j, line in enumerate(lines):
        if f'Section {code}' in line:
            # Title is typically 1-2 lines before the Section line
            if j > 0:
                candidate = lines[j - 1].strip()
                # Skip page numbers and project headers
                if candidate and not re.match(r'^(?:Page|Centre|Réhabilitation|CSSST|\d)', candidate):
                    return candidate
            break
    return ""


# ============================================================
# Finish system mapping (from devis Section 09 91 00)
# ============================================================

# Paint systems extracted from devis pages 319-321
PAINT_SYSTEMS = {
    "P01": {
        "desc": "murs intérieurs en blocs de béton et en béton coulé",
        "room_types": ["TECHNIQUE", "SERVICE"],
        "finish": "perle",
    },
    "P02": {
        "desc": "murs et plafonds intérieurs en panneaux de gypse",
        "room_types": ["CLASSE", "BUREAU", "SALLE", "AUTRE"],
        "finish": "perle",
    },
    "P03": {
        "desc": "surfaces intérieures en métal ferreux apprêtées",
        "room_types": [],  # generic
        "finish": "semi-brillant",
    },
    "P04": {
        "desc": "métal galvanisé ou zingué et tuyaux en cuivre",
        "room_types": [],  # generic
        "finish": "semi-brillant",
    },
    "P05": {
        "desc": "salles mécaniques/électriques, locaux techniques, corridors, escaliers, vestibules, dépôts",
        "room_types": ["TECHNIQUE", "CORRIDOR", "CIRCULATION", "RANGEMENT"],
        "finish": "satiné",
    },
    "P06": {
        "desc": "planchers intérieurs en béton",
        "room_types": ["TECHNIQUE"],
        "finish": "lustré",
    },
    "P07": {
        "desc": "surfaces intérieures en bois",
        "room_types": [],  # generic
        "finish": "semi-brillant",
    },
    "P08": {
        "desc": "toilettes et douches",
        "room_types": ["WC"],
        "finish": "semi-lustré",
    },
}

# CSI sections relevant to room finishes
FINISH_CSI_SECTIONS = {
    "09 21 16": {"title": "Revêtement en plaques de plâtre", "room_types": ["CLASSE", "BUREAU", "SALLE", "CORRIDOR", "CIRCULATION", "AUTRE"]},
    "09 22 16": {"title": "Ossatures métalliques non-porteuses", "room_types": ["CLASSE", "BUREAU", "SALLE", "CORRIDOR", "CIRCULATION"]},
    "09 30 13": {"title": "Carrelages de céramique", "room_types": ["WC", "SERVICE"]},
    "09 51 13": {"title": "Éléments acoustiques pour plafonds", "room_types": ["CLASSE", "BUREAU", "SALLE", "CORRIDOR"]},
    "09 53 00": {"title": "Plafonds suspendus", "room_types": ["CLASSE", "BUREAU", "SALLE", "CORRIDOR", "CIRCULATION"]},
    "09 65 19": {"title": "Revêtements de sols souples (VCT)", "room_types": ["CLASSE", "BUREAU", "CORRIDOR", "CIRCULATION", "SALLE"]},
    "09 91 00": {"title": "Peinturage", "room_types": ["CLASSE", "BUREAU", "SALLE", "CORRIDOR", "CIRCULATION", "WC", "TECHNIQUE", "SERVICE", "RANGEMENT", "GYMNASE"]},
    "10 21 20": {"title": "Compartiments pour salles de toilettes", "room_types": ["WC"]},
    "10 28 13": {"title": "Accessoires de salles de toilettes", "room_types": ["WC"]},
    "10 51 13": {"title": "Armoires-vestiaires métalliques", "room_types": ["VESTIAIRE", "GYMNASE"]},
}


def get_expected_finishes(room_type: str) -> dict:
    """Retourne les finitions attendues par type de local."""
    finishes = {
        "CLASSE": {
            "mur": ["gypse", "peinture P02"],
            "plancher": ["VCT (09 65 19)"],
            "plafond": ["acoustique (09 51 13)"],
        },
        "WC": {
            "mur": ["céramique (09 30 13)", "peinture P08"],
            "plancher": ["céramique (09 30 13)"],
            "plafond": ["gypse peint"],
        },
        "CORRIDOR": {
            "mur": ["peinture P05"],
            "plancher": ["VCT (09 65 19)"],
            "plafond": ["acoustique (09 51 13)"],
        },
        "GYMNASE": {
            "mur": ["peinture P01/P05"],
            "plancher": ["spécifique sport"],
            "plafond": ["acoustique ou structure apparente"],
        },
        "TECHNIQUE": {
            "mur": ["peinture P05"],
            "plancher": ["béton peint P06"],
            "plafond": ["structure apparente"],
        },
        "BUREAU": {
            "mur": ["gypse", "peinture P02"],
            "plancher": ["VCT (09 65 19)"],
            "plafond": ["acoustique (09 51 13)"],
        },
        "SERVICE": {
            "mur": ["céramique ou peinture"],
            "plancher": ["céramique ou VCT"],
            "plafond": ["gypse peint"],
        },
        "RANGEMENT": {
            "mur": ["peinture P05"],
            "plancher": ["béton ou VCT"],
            "plafond": ["gypse peint ou structure"],
        },
        "CIRCULATION": {
            "mur": ["peinture P05"],
            "plancher": ["VCT (09 65 19)"],
            "plafond": ["acoustique (09 51 13)"],
        },
        "SALLE": {
            "mur": ["gypse", "peinture P02"],
            "plancher": ["VCT (09 65 19)"],
            "plafond": ["acoustique (09 51 13)"],
        },
    }
    return finishes.get(room_type, {})


# ============================================================
# Main cross-validation
# ============================================================

def find_room_in_devis(room_id: str, room_name: str, devis_data: dict) -> list:
    """Cherche un local dans les données du devis (structured JSON)."""
    matches = []
    room_id_pattern = re.compile(re.escape(room_id), re.IGNORECASE)
    
    sections = devis_data.get("sections", [])
    for section in sections:
        content = section.get("content", "")
        title = section.get("title", "")
        
        if room_id_pattern.search(content) or room_id_pattern.search(title):
            matches.append({
                "section": title,
                "csi_code": section.get("csi_code"),
                "page": section.get("page_num"),
                "match_type": "direct"
            })
        
        if room_name.upper() in content.upper():
            matches.append({
                "section": title,
                "csi_code": section.get("csi_code"),
                "page": section.get("page_num"),
                "match_type": "name"
            })
        
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


def cross_validate_by_type(rooms_json: dict, devis_sections: list) -> ValidationReport:
    """
    Cross-validate plans vs devis using room TYPE matching.
    
    This is the primary validation method since the devis references
    room types (toilettes, classes, corridors) not room IDs (A-101, B-205).
    
    Args:
        rooms_json: GT data with verified_rooms
        devis_sections: Parsed CSI sections from devis text
    
    Returns:
        ValidationReport
    """
    report = ValidationReport()
    
    # Handle both GT format (verified_rooms) and extracted format (rooms)
    rooms = rooms_json.get("verified_rooms", rooms_json.get("rooms", []))
    
    # Index rooms by type
    rooms_by_type = defaultdict(list)
    for room in rooms:
        name = room.get("name", "")
        rtype = room.get("type") or extract_room_type(name)
        rooms_by_type[rtype].append(room)
    
    # Build CSI section coverage map
    # Which room types are mentioned in which CSI sections?
    csi_coverage = defaultdict(set)  # room_type -> set of CSI codes
    csi_room_refs = {}
    
    for section in devis_sections:
        code = section['code']
        room_types_found = section.get('room_types', {})
        
        if room_types_found:
            csi_room_refs[code] = {
                'title': section['title'],
                'room_types_referenced': list(room_types_found.keys()),
            }
            for rtype in room_types_found:
                csi_coverage[rtype].add(code)
    
    # Also add known finish section mappings
    for csi_code, info in FINISH_CSI_SECTIONS.items():
        for rtype in info['room_types']:
            csi_coverage[rtype].add(csi_code)
    
    # Validate each room
    room_type_coverage = {}
    for rtype, type_rooms in rooms_by_type.items():
        covered_by = csi_coverage.get(rtype, set())
        is_covered = len(covered_by) > 0
        
        room_type_coverage[rtype] = {
            'count': len(type_rooms),
            'csi_sections': sorted(covered_by),
            'covered': is_covered,
        }
        
        for room in type_rooms:
            room_id = room.get("id", "")
            room_name = room.get("name", "")
            
            if is_covered:
                # Room type has devis coverage
                csi_list = sorted(covered_by)
                primary_csi = csi_list[0]
                
                # Determine match confidence
                # Higher if room type is explicitly in devis text
                if rtype in csi_coverage and any(
                    rtype in sec.get('room_types', {})
                    for sec in devis_sections
                    if sec['code'] in covered_by
                ):
                    confidence = 0.85
                    match_type = "type_match"
                else:
                    confidence = 0.70
                    match_type = "inferred"
                
                csi_desc = ', '.join(csi_list[:3])
                report.matches.append(Match(
                    room_id=room_id,
                    room_name=room_name,
                    devis_section=csi_desc,
                    match_type=match_type,
                    confidence=confidence,
                    details=f"Type {rtype} couvert par {len(covered_by)} sections CSI",
                ))
            else:
                # Room type has no devis coverage
                report.missing.append(Missing(
                    source="devis",
                    item_id=room_id,
                    item_name=room_name,
                    expected_in=f"Sections pour type {rtype}",
                    message=f"Aucune section CSI ne couvre le type {rtype}",
                ))
    
    # Check for devis sections that reference room types not in plans
    plan_types = set(rooms_by_type.keys())
    for section in devis_sections:
        for rtype in section.get('room_types', {}):
            if rtype not in plan_types:
                # This is informational, not necessarily an error
                report.mismatches.append(Mismatch(
                    room_id="—",
                    field="coverage",
                    plan_value="absent",
                    devis_value=f"Section {section['code']}",
                    severity="info",
                    message=f"Type {rtype} référencé dans devis ({section['code']}) mais absent des plans",
                ))
    
    # Check expected finishes
    for rtype, type_rooms in rooms_by_type.items():
        expected = get_expected_finishes(rtype)
        if expected:
            covered_by = csi_coverage.get(rtype, set())
            
            # Check floor coverage
            if "plancher" in expected:
                has_floor = any(
                    code.startswith("09 65") or code.startswith("09 30")
                    for code in covered_by
                )
                if not has_floor and rtype not in ("TECHNIQUE", "GYMNASE", "RANGEMENT"):
                    report.mismatches.append(Mismatch(
                        room_id=f"type:{rtype}",
                        field="finition",
                        plan_value=f"{len(type_rooms)} locaux de type {rtype}",
                        devis_value="Pas de section plancher",
                        severity="warning",
                        message=f"Type {rtype}: revêtement de sol attendu ({expected['plancher']}) mais pas de section CSI spécifique trouvée",
                    ))
            
            # Check ceiling coverage
            if "plafond" in expected:
                has_ceiling = any(
                    code.startswith("09 51") or code.startswith("09 53")
                    for code in covered_by
                )
                if not has_ceiling and rtype not in ("TECHNIQUE", "WC", "RANGEMENT", "GYMNASE"):
                    report.mismatches.append(Mismatch(
                        room_id=f"type:{rtype}",
                        field="finition",
                        plan_value=f"{len(type_rooms)} locaux de type {rtype}",
                        devis_value="Pas de section plafond",
                        severity="warning",
                        message=f"Type {rtype}: plafond attendu ({expected['plafond']}) mais pas de section CSI spécifique trouvée",
                    ))
    
    # Stats
    total_rooms = len(rooms)
    matched = len(report.matches)
    
    report.stats = {
        "total_rooms": total_rooms,
        "rooms_checked": total_rooms,
        "matched_rooms": matched,
        "match_rate": matched / total_rooms if total_rooms > 0 else 0,
        "devis_sections": len(devis_sections),
        "room_types_in_plans": dict(sorted(
            {k: len(v) for k, v in rooms_by_type.items()}.items(),
            key=lambda x: -x[1]
        )),
        "room_type_coverage": room_type_coverage,
        "csi_room_refs": csi_room_refs,
        "critical_mismatches": len([m for m in report.mismatches if m.severity == "critical"]),
        "warning_mismatches": len([m for m in report.mismatches if m.severity == "warning"]),
        "missing_count": len(report.missing),
    }
    
    return report


def cross_validate(rooms_json: dict, devis_json: dict) -> ValidationReport:
    """
    Cross-validate plans vs devis using structured devis JSON.
    
    Legacy interface that works with devis_final.json format.
    For better results, use cross_validate_by_type() with parsed devis text.
    """
    report = ValidationReport()
    
    rooms = rooms_json.get("verified_rooms", rooms_json.get("rooms", []))
    rooms_by_type = defaultdict(list)
    rooms_found_in_devis = set()
    
    for room in rooms:
        name = room.get("name", "")
        room_type = room.get("type") or extract_room_type(name)
        rooms_by_type[room_type].append(room)
    
    for room in rooms:
        room_id = room.get("id", "")
        room_name = room.get("name", "")
        room_type = room.get("type") or extract_room_type(room_name)
        
        devis_matches = find_room_in_devis(room_id, room_name, devis_json)
        
        if devis_matches:
            rooms_found_in_devis.add(room_id)
            best_match = max(devis_matches, key=lambda m: 1 if m["match_type"] == "direct" else 0.5)
            
            report.matches.append(Match(
                room_id=room_id,
                room_name=room_name,
                devis_section=best_match["section"],
                match_type=best_match["match_type"],
                confidence=0.9 if best_match["match_type"] == "direct" else 0.6,
                details=f"Page {best_match.get('page', '?')}",
            ))
        else:
            # Try type-based matching via known CSI sections
            covered_by = []
            for csi_code, info in FINISH_CSI_SECTIONS.items():
                if room_type in info['room_types']:
                    covered_by.append(csi_code)
            
            if covered_by:
                report.matches.append(Match(
                    room_id=room_id,
                    room_name=room_name,
                    devis_section=', '.join(covered_by[:3]),
                    match_type="inferred",
                    confidence=0.70,
                    details=f"Type {room_type} couvert par CSI {', '.join(covered_by[:3])}",
                ))
            else:
                expected_finishes = get_expected_finishes(room_type)
                if expected_finishes:
                    report.missing.append(Missing(
                        source="devis",
                        item_id=room_id,
                        item_name=room_name,
                        expected_in=f"Section finitions ({room_type})",
                        message=f"Local {room_id} non trouvé dans le devis",
                    ))
                else:
                    report.matches.append(Match(
                        room_id=room_id,
                        room_name=room_name,
                        devis_section="(spécifications génériques)",
                        match_type="inferred",
                        confidence=0.4,
                        details="Pas de mention explicite, applique specs génériques",
                    ))
    
    total_rooms = len(rooms)
    matched_rooms = len(report.matches)
    
    rooms_by_type_counts = {k: len(v) for k, v in rooms_by_type.items()}
    report.stats = {
        "total_rooms": total_rooms,
        "rooms_checked": total_rooms,
        "matched_rooms": matched_rooms,
        "match_rate": matched_rooms / total_rooms if total_rooms > 0 else 0,
        "devis_sections": len(devis_json.get("sections", [])),
        "rooms_by_type": rooms_by_type_counts,
        "room_types_in_plans": rooms_by_type_counts,
        "critical_mismatches": len([m for m in report.mismatches if m.severity == "critical"]),
        "missing_count": len(report.missing),
    }
    
    return report


def validate_dimensions(rooms_json: dict, devis_json: dict) -> list:
    """Vérifie que les dimensions correspondent entre plans et devis."""
    mismatches = []
    
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
    
    rooms = rooms_json.get("verified_rooms", rooms_json.get("rooms", []))
    for room in rooms:
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
                    message=f"Dimensions différentes pour {room_id}",
                ))
    
    return mismatches


def main():
    """Point d'entrée CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Cross-validation plans vs devis")
    parser.add_argument("--rooms", "-r", required=True, help="Fichier JSON des locaux (GT ou rooms_complete.json)")
    parser.add_argument("--devis", "-d", help="Fichier JSON du devis (devis_final.json)")
    parser.add_argument("--devis-text", "-t", help="Fichier texte brut du devis (devis_full_text.txt)")
    parser.add_argument("--output", "-o", help="Fichier de sortie JSON")
    parser.add_argument("--markdown", "-m", help="Fichier de sortie Markdown")
    parser.add_argument("--verbose", "-v", action="store_true", help="Mode verbeux")
    
    args = parser.parse_args()
    
    # Load rooms
    with open(args.rooms) as f:
        rooms_data = json.load(f)
    
    # Run validation
    if args.devis_text:
        # Use text-based validation (better)
        with open(args.devis_text) as f:
            devis_text = f.read()
        
        devis_sections = parse_devis_sections_from_text(devis_text)
        report = cross_validate_by_type(rooms_data, devis_sections)
        
    elif args.devis:
        # Use structured JSON validation (legacy)
        with open(args.devis) as f:
            devis_data = json.load(f)
        
        report = cross_validate(rooms_data, devis_data)
        dim_mismatches = validate_dimensions(rooms_data, devis_data)
        report.mismatches.extend(dim_mismatches)
    else:
        parser.error("Either --devis or --devis-text is required")
    
    # Print summary
    print(report.summary())
    
    # Save JSON
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"\nRapport JSON sauvegardé: {output_path}")
    
    # Save Markdown
    if args.markdown:
        md_path = Path(args.markdown)
        with open(md_path, "w") as f:
            f.write(report.to_markdown())
        print(f"Rapport Markdown sauvegardé: {md_path}")
    
    if args.verbose:
        print("\n--- Détails des matches ---")
        for m in report.matches[:15]:
            print(f"  {m.room_id}: {m.devis_section} ({m.match_type}, {m.confidence:.0%})")
        
        print(f"\n--- Couverture par type ---")
        for rtype, info in sorted(report.stats.get('room_type_coverage', {}).items()):
            covered = '✅' if info.get('covered') else '❌'
            csi = ', '.join(info.get('csi_sections', [])) or '—'
            print(f"  {covered} {rtype}: {info['count']} rooms → {csi}")


if __name__ == "__main__":
    main()
