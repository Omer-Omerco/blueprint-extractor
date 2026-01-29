#!/usr/bin/env python3
"""
Build RAG index from VERIFIED gold ground truth only.
Zero hallucination: every entry traces to a source document + page.

Usage:
    python scripts/build_rag_gold.py
    python scripts/build_rag_gold.py -o rag_gold
    python scripts/build_rag_gold.py --json
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Optional


def normalize_text(text: str) -> str:
    """Normalize text for search indexing."""
    return re.sub(r'\s+', ' ', text.lower().strip())


def build_search_text(room: dict) -> str:
    """Build comprehensive search text for a room entry."""
    parts = [
        room.get("name", ""),
        room.get("plan_id", ""),
        room.get("id", ""),
        room.get("type", ""),
        room.get("block", ""),
    ]
    
    # Add synonyms for common room types
    name = room.get("name", "").upper()
    type_ = room.get("type", "").upper()
    
    if "CLASSE" in name or type_ == "CLASSE":
        parts.extend(["classe", "class", "salle de classe"])
    if "CORRIDOR" in name or type_ == "CORRIDOR":
        parts.extend(["corridor", "couloir", "hall", "passage"])
    if "WC" in name or type_ == "WC":
        parts.extend(["toilette", "wc", "salle de bain", "bathroom"])
    if "BUREAU" in name or type_ == "BUREAU":
        parts.extend(["bureau", "office"])
    if "DÉPÔT" in name or type_ == "DÉPÔT":
        parts.extend(["dépôt", "rangement", "storage", "entrepôt"])
    if "VESTIBULE" in name or "SAS" in name or type_ in ("VESTIBULE", "SAS"):
        parts.extend(["vestibule", "entrée", "sas", "entry"])
    if "VESTIAIRE" in name or type_ == "VESTIAIRE":
        parts.extend(["vestiaire", "cloakroom"])
    if "CHAUFFERIE" in name:
        parts.extend(["chaufferie", "mécanique", "mechanical", "boiler"])
    if "BIBLIOTHÈQUE" in name:
        parts.extend(["bibliothèque", "library"])
    if "GYMNASE" in name:
        parts.extend(["gymnase", "gym"])
    if "CONCIERGE" in name:
        parts.extend(["concierge", "janitor"])
    if "ÉLECTRIQUE" in name or "TÉLÉCOM" in name:
        parts.extend(["électrique", "télécom", "technique", "electrical", "telecom"])
    if "MATERNELLE" in name:
        parts.extend(["maternelle", "kindergarten"])
    if "SERVICE DE GARDE" in name:
        parts.extend(["service de garde", "garde", "daycare"])
    if "PROFESSEURS" in name:
        parts.extend(["professeurs", "enseignants", "teachers", "staff"])
    if "GICLEURS" in name:
        parts.extend(["gicleurs", "sprinkler"])
    
    # Add floor info
    floor = room.get("floor")
    if floor == 1:
        parts.extend(["1er étage", "rez-de-chaussée", "premier"])
    elif floor == 2:
        parts.extend(["2e étage", "deuxième", "second"])
    
    # Add notes if present
    if room.get("notes"):
        parts.append(room["notes"])
    
    # Add area if present
    if room.get("area_pica"):
        parts.append(f"{room['area_pica']} pi²")
    
    return normalize_text(" ".join(parts))


def build_gold_index(
    gold_path: str = None,
    output_dir: str = None
) -> dict:
    """
    Build RAG index exclusively from verified gold ground truth.
    
    Args:
        gold_path: Path to emj_gold.json (default: ground_truth/emj_gold.json)
        output_dir: Output directory for RAG files (default: ./rag_gold)
    
    Returns:
        The built index dict
    """
    # Resolve paths
    base_dir = Path(__file__).parent.parent
    
    if gold_path is None:
        gold_path = base_dir / "ground_truth" / "emj_gold.json"
    else:
        gold_path = Path(gold_path).expanduser().resolve()
    
    if output_dir is None:
        output_dir = base_dir / "rag_gold"
    else:
        output_dir = Path(output_dir).expanduser().resolve()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load gold GT
    with open(gold_path) as f:
        gold = json.load(f)
    
    verified_rooms = gold.get("verified_rooms", [])
    fabricated_rooms = set()
    rooms_not_found = gold.get("rooms_NOT_found", {})
    if isinstance(rooms_not_found, dict):
        fabricated_rooms = set(rooms_not_found.get("fabricated_rooms", []))
    
    # Remove verified rooms from fabricated set (verified overrides)
    verified_ids = {r.get("id") for r in verified_rooms}
    fabricated_rooms -= verified_ids
    
    # Build search entries from verified rooms ONLY
    entries = []
    
    for room in verified_rooms:
        # Every entry MUST have source traceability
        source = room.get("source", "")
        if not source:
            # Skip rooms without source citation
            continue
        
        entry = {
            "type": "room",
            "id": room.get("id", ""),
            "plan_id": room.get("plan_id", ""),
            "name": room.get("name", ""),
            "block": room.get("block", ""),
            "floor": room.get("floor"),
            "room_type": room.get("type", ""),
            "confidence": room.get("confidence", "MEDIUM"),
            "source": source,
            "source_document": _extract_source_document(source, gold),
            "source_pages": _extract_source_pages(source),
            "devis_ref": room.get("devis_ref"),
            "door_schedule": room.get("door_schedule"),
            "notes": room.get("notes"),
            "area_pica": room.get("area_pica"),
            "search_text": build_search_text(room),
            "verified": True,
        }
        
        entries.append(entry)
    
    # Build the index
    index = {
        "version": "2.0-gold",
        "project": gold.get("project", ""),
        "project_full_name": gold.get("project_full_name", ""),
        "location": gold.get("location", ""),
        "source_documents": gold.get("source_documents", {}),
        "verification_date": gold.get("verification_date", ""),
        "methodology": gold.get("methodology", ""),
        "building_structure": gold.get("building_structure", {}),
        "numbering_scheme": gold.get("numbering_scheme", {}),
        "stats": {
            "total_verified_rooms": len(entries),
            "high_confidence": sum(1 for e in entries if e["confidence"] == "HIGH"),
            "medium_confidence": sum(1 for e in entries if e["confidence"] == "MEDIUM"),
            "fabricated_rooms_blocked": len(fabricated_rooms),
            "blocks": {
                "A_1er": sum(1 for e in entries if e["block"] == "A" and e["floor"] == 1),
                "A_2e": sum(1 for e in entries if e["block"] == "A" and e["floor"] == 2),
                "B_1er": sum(1 for e in entries if e["block"] == "B" and e["floor"] == 1),
                "C_1er": sum(1 for e in entries if e["block"] == "C" and e["floor"] == 1),
            },
            "room_types": _count_types(entries),
        },
        "fabricated_rooms": sorted(fabricated_rooms),
        "entries": entries,
    }
    
    # Save index
    with open(output_dir / "index.json", "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    
    # Save per-block files
    blocks_dir = output_dir / "blocks"
    blocks_dir.mkdir(exist_ok=True)
    
    block_data = {}
    for entry in entries:
        key = f"{entry['block']}-{entry['floor']}"
        if key not in block_data:
            block_data[key] = []
        block_data[key].append(entry)
    
    for block_key, block_entries in block_data.items():
        with open(blocks_dir / f"bloc-{block_key}.json", "w") as f:
            json.dump({
                "block": block_key,
                "rooms": block_entries,
                "count": len(block_entries)
            }, f, indent=2, ensure_ascii=False)
    
    # Save lookup table (room_id → entry) for fast queries
    lookup = {}
    for entry in entries:
        # Index by multiple keys for flexible lookup
        lookup[entry["id"]] = entry
        lookup[entry["plan_id"]] = entry
        # Also index by lowercase name variants
        name_key = f"{entry['name'].lower()}_{entry['plan_id']}"
        lookup[name_key] = entry
    
    with open(output_dir / "lookup.json", "w") as f:
        json.dump(lookup, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Gold RAG index built: {output_dir / 'index.json'}")
    print(f"  Verified rooms: {len(entries)}")
    print(f"  High confidence: {index['stats']['high_confidence']}")
    print(f"  Medium confidence: {index['stats']['medium_confidence']}")
    print(f"  Fabricated rooms blocked: {len(fabricated_rooms)}")
    print(f"  Blocks indexed: {len(block_data)}")
    
    return index


def _extract_source_document(source: str, gold: dict) -> str:
    """Extract the source document name from source string."""
    docs = gold.get("source_documents", {})
    
    source_docs = []
    if "plan construction" in source.lower() or "p.a-" in source.lower():
        source_docs.append(docs.get("plans", "Plans construction"))
    if "devis" in source.lower():
        source_docs.append(docs.get("devis", "Devis architecture"))
    if "door schedule" in source.lower():
        source_docs.append(docs.get("plans", "Plans construction") + " (door schedule)")
    if "vision" in source.lower():
        source_docs.append("Vision verification")
    
    return " + ".join(source_docs) if source_docs else source


def _extract_source_pages(source: str) -> list[str]:
    """Extract page references from source string."""
    # Match patterns like p.A-150, p.A-900, p.A-950
    pages = re.findall(r'p\.(A-\d+)', source)
    return pages if pages else []


def _count_types(entries: list) -> dict:
    """Count room types."""
    types = {}
    for e in entries:
        t = e.get("room_type", "UNKNOWN")
        types[t] = types.get(t, 0) + 1
    return dict(sorted(types.items(), key=lambda x: -x[1]))


def main():
    parser = argparse.ArgumentParser(
        description="Build RAG index from verified gold ground truth (ZERO hallucination)"
    )
    parser.add_argument(
        "-g", "--gold",
        default=None,
        help="Path to emj_gold.json (default: ground_truth/emj_gold.json)"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory (default: ./rag_gold)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output index as JSON to stdout"
    )
    
    args = parser.parse_args()
    
    index = build_gold_index(
        gold_path=args.gold,
        output_dir=args.output
    )
    
    if args.json:
        print(json.dumps(index, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
