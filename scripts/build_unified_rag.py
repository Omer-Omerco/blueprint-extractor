#!/usr/bin/env python3
"""
Build unified RAG index combining Plans + Devis.
Creates a searchable knowledge base for the entire project.
"""

import argparse
import json
from pathlib import Path
from datetime import datetime


def load_json(path: Path) -> dict:
    """Load JSON file safely."""
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def build_unified_index(
    rooms_path: str,
    devis_path: str,
    guide_path: str,
    output_path: str
) -> dict:
    """Build unified RAG index from all sources."""
    
    rooms_path = Path(rooms_path)
    devis_path = Path(devis_path)
    guide_path = Path(guide_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load all sources
    rooms_data = load_json(rooms_path)
    devis_data = load_json(devis_path)
    guide_data = load_json(guide_path)
    
    # Build unified index
    index = {
        "meta": {
            "project": "Réhabilitation de l'école Enfant-Jésus, Sorel-Tracy",
            "client": "Centre de services scolaire de Sorel-Tracy",
            "dossier": "CSSST 23-333 / 24014",
            "created_at": datetime.now().isoformat(),
            "sources": {
                "plans": str(rooms_path) if rooms_path.exists() else None,
                "devis": str(devis_path) if devis_path.exists() else None,
                "guide": str(guide_path) if guide_path.exists() else None
            }
        },
        
        # From Plans
        "rooms": rooms_data.get("rooms", []),
        "extraction_rules": guide_data.get("stable_rules", []) if isinstance(guide_data, dict) else [],
        
        # From Devis  
        "csi_sections": devis_data.get("csi_sections", []),
        "products": devis_data.get("products", []),
        "local_references": devis_data.get("local_references", []),
        
        # Cross-reference index (room -> specs)
        "room_specs": {},
        
        # Search entries (for RAG queries)
        "search_entries": []
    }
    
    # Build room -> specs cross-reference
    rooms_by_id = {r["id"]: r for r in index["rooms"]}
    
    for ref in devis_data.get("local_references", []):
        room_id = ref.get("reference", "")
        if room_id not in index["room_specs"]:
            index["room_specs"][room_id] = []
        index["room_specs"][room_id].append({
            "context": ref.get("context", ""),
            "page": ref.get("page")
        })
    
    # Build search entries for RAG
    
    # 1. Room entries
    for room in index["rooms"]:
        index["search_entries"].append({
            "type": "room",
            "id": room["id"],
            "text": f"Local {room['id']} - {room['name']} (Bloc {room['block']}, étage {room['floor']})",
            "keywords": [room["id"], room["name"].lower(), f"bloc {room['block'].lower()}"],
            "data": room
        })
    
    # 2. Product entries
    for product in index["products"]:
        manufacturer = product.get("manufacturer") or ""
        model = product.get("model") or ""
        csi = product.get("csi_section") or ""
        if manufacturer or model:
            index["search_entries"].append({
                "type": "product",
                "text": f"Produit: {manufacturer} {model} (CSI {csi})",
                "keywords": [manufacturer.lower(), model.lower(), csi],
                "data": product
            })
    
    # 3. CSI section entries
    for csi in index["csi_sections"]:
        code = csi.get("code", "")
        context = csi.get("context", "")[:200]
        index["search_entries"].append({
            "type": "csi_section",
            "id": code,
            "text": f"Section CSI {code}: {context}",
            "keywords": [code, code.replace(" ", "")],
            "data": csi
        })
    
    # Stats
    index["stats"] = {
        "total_rooms": len(index["rooms"]),
        "total_products": len(index["products"]),
        "total_csi_sections": len(index["csi_sections"]),
        "total_search_entries": len(index["search_entries"]),
        "rooms_with_specs": len(index["room_specs"])
    }
    
    # Write output
    with open(output_path, "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Unified RAG index built: {output_path}")
    print(f"  - Rooms: {index['stats']['total_rooms']}")
    print(f"  - Products: {index['stats']['total_products']}")
    print(f"  - CSI Sections: {index['stats']['total_csi_sections']}")
    print(f"  - Search entries: {index['stats']['total_search_entries']}")
    
    return index


def main():
    parser = argparse.ArgumentParser(description="Build unified RAG index")
    parser.add_argument("--rooms", default="output/rooms_extracted.json")
    parser.add_argument("--devis", default="output/devis_parsed.json")
    parser.add_argument("--guide", default="output/stable_rules.json")
    parser.add_argument("-o", "--output", default="output/rag/unified_index.json")
    
    args = parser.parse_args()
    build_unified_index(args.rooms, args.devis, args.guide, args.output)


if __name__ == "__main__":
    main()
