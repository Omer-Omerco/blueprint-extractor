#!/usr/bin/env python3
"""
Build Unified RAG Index for Construction Projects.
École Enfant-Jésus - Sorel-Tracy

Creates a comprehensive search index linking:
- Rooms/Locaux ↔ CSI Specifications
- Material types ↔ Sections
- Products ↔ Manufacturers
- Room types → Applicable finishes

Supports queries like:
- "Quels matériaux pour la classe A-201?"
- "Quelle peinture pour le gymnase?"
- "Spécifications plancher corridors"
"""

import argparse
import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Optional


# ==============================================================================
# Room Type → CSI Mappings (typical finishes by room type)
# ==============================================================================

ROOM_TYPE_CSI_MAPPING = {
    "CLASSE": {
        "required": ["09 91 00", "09 51 13", "09 65 19"],  # peinture, plafond, plancher
        "common": ["09 21 16", "08 11 14", "08 71 00", "12 21 23"],  # cloisons, portes, quincaillerie, stores
        "description": "Classe - finis standard école"
    },
    "CORRIDOR": {
        "required": ["09 91 00", "09 65 19", "03 54 01"],
        "common": ["09 51 13", "10 26 10", "10 14 24"],  # plafond, protection murale, signalisation
        "description": "Corridor - durabilité élevée"
    },
    "GYMNASE": {
        "required": ["09 65 19", "09 91 00", "09 51 13"],
        "common": ["06 10 00", "10 21 13", "10 26 10"],  # charpenterie, panneaux, protection
        "description": "Gymnase - plancher sportif, acoustique"
    },
    "TOILETTE": {
        "required": ["09 30 13", "09 91 00", "10 21 20"],  # céramique, peinture, accessoires WC
        "common": ["09 51 13", "08 11 14", "08 71 00"],
        "description": "Toilette - résistance humidité"
    },
    "WC": {
        "required": ["09 30 13", "09 91 00", "10 21 20"],
        "common": ["09 51 13", "08 11 14", "08 71 00"],
        "description": "WC - résistance humidité"
    },
    "CONCIERGERIE": {
        "required": ["09 30 13", "09 91 00", "09 65 19"],
        "common": ["10 28 13", "08 11 14"],
        "description": "Conciergerie - plancher résistant"
    },
    "RANGEMENT": {
        "required": ["09 91 00", "09 65 19"],
        "common": ["06 40 00", "08 11 14"],  # menuiserie, portes
        "description": "Rangement - finis économiques"
    },
    "BUREAU": {
        "required": ["09 91 00", "09 51 13", "09 65 19"],
        "common": ["09 21 16", "08 11 14", "12 21 23"],
        "description": "Bureau - finis confort"
    },
    "VESTIAIRE": {
        "required": ["09 30 13", "09 91 00", "10 51 13"],  # céramique, peinture, casiers
        "common": ["09 51 13", "10 21 20"],
        "description": "Vestiaire - durabilité, casiers"
    },
    "ESCALIER": {
        "required": ["09 91 00", "03 54 01", "05 50 00"],
        "common": ["09 65 19", "10 14 24"],
        "description": "Escalier - sécurité, antidérapant"
    },
    "LOCAL TECHNIQUE": {
        "required": ["09 91 00", "03 54 01"],
        "common": ["08 11 14", "09 65 19"],
        "description": "Local technique - finis utilitaires"
    },
    "LOCAL MÉCANIQUE": {
        "required": ["09 91 00", "03 54 01"],
        "common": ["08 11 14", "07 21 16"],
        "description": "Local mécanique - isolation acoustique"
    },
    "CHAUFFERIE": {
        "required": ["09 91 00", "03 54 01"],
        "common": ["07 21 16", "08 11 14"],
        "description": "Chaufferie - résistance chaleur"
    },
    "ÉLECTRIQUE": {
        "required": ["09 91 00", "03 54 01"],
        "common": ["08 11 14"],
        "description": "Local électrique - accès maintenance"
    },
    "VESTIBULE": {
        "required": ["09 65 19", "09 91 00", "12 48 16"],  # plancher, peinture, gratte-pieds
        "common": ["08 44 13", "09 51 13"],  # mur-rideau, plafond
        "description": "Vestibule - entrée, gratte-pieds"
    }
}

# CSI Code descriptions
CSI_DESCRIPTIONS = {
    "03 54 01": "Sous-finition truellée des planchers",
    "06 10 00": "Charpenterie",
    "06 20 00": "Menuiserie de finition",
    "06 40 00": "Menuiserie architecturale",
    "07 21 16": "Isolant en matelas",
    "07 42 13": "Panneaux muraux métalliques",
    "07 53 00": "Membrane de toiture",
    "07 62 00": "Solins et accessoires",
    "07 84 00": "Coupe-feu",
    "07 92 00": "Calfeutrage et scellants",
    "08 11 14": "Portes en acier",
    "08 14 16": "Portes en bois",
    "08 44 13": "Murs-rideaux vitrés",
    "08 51 13": "Fenêtres en aluminium",
    "08 71 00": "Quincaillerie de porte",
    "08 80 00": "Vitrerie",
    "08 80 50": "Vitrerie intérieure",
    "09 21 16": "Cloisons en panneaux de gypse",
    "09 22 16": "Doublages non structuraux",
    "09 30 13": "Carrelage de céramique",
    "09 51 13": "Plafonds acoustiques",
    "09 53 00": "Plafonds spéciaux",
    "09 65 19": "Revêtements de sol résilients",
    "09 91 00": "Peinture",
    "10 12 20": "Tableaux d'affichage",
    "10 14 24": "Signalisation",
    "10 21 13": "Panneaux spécialisés",
    "10 21 20": "Accessoires de toilettes",
    "10 26 10": "Protection murale",
    "10 28 10": "Accessoires de toilettes",
    "10 28 13": "Accessoires de conciergerie",
    "10 51 13": "Armoires-vestiaires",
    "12 21 23": "Stores déroulants",
    "12 48 16": "Grilles gratte-pieds"
}

# Material type keywords for text search
TYPE_KEYWORDS = {
    "peinture": ["peinture", "latex", "apprêt", "primer", "couche", "benjamin moore", "sherwin", "alkyde"],
    "plancher": ["plancher", "revêtement de sol", "VCT", "époxy", "vinyle", "linoleum", "résilient", "tuile"],
    "plafond": ["plafond", "suspendu", "acoustique", "armstrong", "tuile", "dalle"],
    "céramique": ["céramique", "carrelage", "carreau", "tuile", "porcelaine", "mosaïque"],
    "porte": ["porte", "cadre", "dormant", "battant", "coupe-feu"],
    "fenêtre": ["fenêtre", "vitrage", "double vitrage", "châssis", "aluminium"],
    "cloison": ["gypse", "cloison", "mur", "panneau", "drywall"],
    "isolation": ["isolant", "isolation", "pare-vapeur", "laine", "polystyrène"],
    "quincaillerie": ["serrure", "penture", "ferme-porte", "barre panique", "poignée"],
    "accessoires": ["distributeur", "sèche-mains", "miroir", "crochet", "barre d'appui"],
}


class UnifiedRAGBuilder:
    """Build a unified RAG index with bidirectional room↔spec links."""
    
    def __init__(self, rooms_data: dict, chunks_data: dict):
        self.rooms = rooms_data.get("rooms", [])
        self.chunks = chunks_data.get("chunks", [])
        self.rooms_by_id = {r["id"]: r for r in self.rooms}
        self.rooms_by_type = defaultdict(list)
        self.quality_meta = rooms_data.get("quality_meta", {})
        
        # Group rooms by type
        for room in self.rooms:
            room_type = self._normalize_room_type(room.get("name", ""))
            self.rooms_by_type[room_type].append(room)
    
    def _normalize_room_type(self, name: str) -> str:
        """Normalize room name to type."""
        name_upper = name.upper()
        
        # Direct matches
        for type_key in ROOM_TYPE_CSI_MAPPING:
            if type_key in name_upper:
                return type_key
        
        # Special cases
        if "MATERNELLE" in name_upper:
            return "CLASSE"
        if "GARDE" in name_upper:
            return "CLASSE"
        if "BIBLIOTHÈQUE" in name_upper or "INFORMATIQUE" in name_upper:
            return "CLASSE"
        if "PROFESSEUR" in name_upper:
            return "BUREAU"
        if "MÉCANIQUE" in name_upper:
            return "LOCAL MÉCANIQUE"
        if "TECHNIQUE" in name_upper:
            return "LOCAL TECHNIQUE"
        if "WC" in name_upper or "TOILETTE" in name_upper:
            return "TOILETTE"
        
        return "OTHER"
    
    def _extract_room_refs_from_text(self, text: str) -> list[str]:
        """Extract room references from text."""
        refs = set()
        
        # Pattern: A-101, B-106, C-101
        for match in re.finditer(r'\b([A-D]-\d{3})\b', text):
            ref = match.group(1).upper()
            if ref in self.rooms_by_id:
                refs.add(ref)
        
        # Pattern: local 101, salle 204
        for match in re.finditer(r'\b(?:local|salle|pièce|classe)\s+(\d{3})\b', text, re.IGNORECASE):
            num = match.group(1)
            # Try to find matching room
            for block in ['A', 'B', 'C']:
                candidate = f"{block}-{num}"
                if candidate in self.rooms_by_id:
                    refs.add(candidate)
        
        return sorted(refs)
    
    def _get_csi_sections_for_room(self, room: dict) -> dict:
        """Get applicable CSI sections for a room based on type."""
        room_type = self._normalize_room_type(room.get("name", ""))
        mapping = ROOM_TYPE_CSI_MAPPING.get(room_type, {})
        
        return {
            "required": mapping.get("required", []),
            "common": mapping.get("common", []),
            "room_type": room_type,
            "type_description": mapping.get("description", "Type non défini")
        }
    
    def build_room_index(self) -> dict:
        """Build room → specs index."""
        index = {}
        
        for room in self.rooms:
            room_id = room["id"]
            csi_info = self._get_csi_sections_for_room(room)
            
            # Find chunks that mention this room
            related_chunks = []
            for chunk in self.chunks:
                refs = self._extract_room_refs_from_text(chunk["text"])
                if room_id in refs:
                    related_chunks.append({
                        "chunk_id": chunk["id"],
                        "csi_code": chunk["metadata"].get("csi_code"),
                        "csi_title": chunk["metadata"].get("csi_title"),
                        "relevance": "direct_mention"
                    })
            
            # Add chunks from required CSI sections
            required_chunks = []
            for csi_code in csi_info["required"]:
                for chunk in self.chunks:
                    if chunk["metadata"].get("csi_code") == csi_code:
                        if chunk["id"] not in [c["chunk_id"] for c in related_chunks]:
                            required_chunks.append({
                                "chunk_id": chunk["id"],
                                "csi_code": csi_code,
                                "csi_title": CSI_DESCRIPTIONS.get(csi_code, ""),
                                "relevance": "room_type_default"
                            })
            
            index[room_id] = {
                "room_info": room,
                "room_type": csi_info["room_type"],
                "type_description": csi_info["type_description"],
                "confidence": room.get("confidence"),
                "extraction_method": room.get("extraction_method"),
                "source_pages": room.get("source_pages", room.get("pages", [])),
                "primary_source": room.get("primary_source"),
                "csi_required": [
                    {"code": c, "title": CSI_DESCRIPTIONS.get(c, "")}
                    for c in csi_info["required"]
                ],
                "csi_common": [
                    {"code": c, "title": CSI_DESCRIPTIONS.get(c, "")}
                    for c in csi_info["common"]
                ],
                "direct_mentions": related_chunks[:10],
                "applicable_chunks": len(related_chunks) + len(required_chunks)
            }
        
        return index
    
    def build_csi_index(self) -> dict:
        """Build CSI → rooms index."""
        index = defaultdict(lambda: {
            "title": "",
            "chunk_count": 0,
            "rooms_applicable": [],
            "room_types": []
        })
        
        # Count chunks per CSI
        for chunk in self.chunks:
            csi_code = chunk["metadata"].get("csi_code")
            if csi_code:
                index[csi_code]["chunk_count"] += 1
                if not index[csi_code]["title"]:
                    index[csi_code]["title"] = CSI_DESCRIPTIONS.get(
                        csi_code, 
                        chunk["metadata"].get("csi_title", "")
                    )
        
        # Map room types to CSI
        for room_type, mapping in ROOM_TYPE_CSI_MAPPING.items():
            for csi_code in mapping.get("required", []) + mapping.get("common", []):
                if room_type not in index[csi_code]["room_types"]:
                    index[csi_code]["room_types"].append(room_type)
        
        # Find rooms mentioned in chunks
        for chunk in self.chunks:
            csi_code = chunk["metadata"].get("csi_code")
            if csi_code:
                refs = self._extract_room_refs_from_text(chunk["text"])
                for ref in refs:
                    if ref not in index[csi_code]["rooms_applicable"]:
                        index[csi_code]["rooms_applicable"].append(ref)
        
        return dict(index)
    
    def build_type_index(self) -> dict:
        """Build material type → specs index."""
        index = {}
        
        for mat_type, keywords in TYPE_KEYWORDS.items():
            matching_chunks = []
            matching_csi = set()
            
            for chunk in self.chunks:
                text_lower = chunk["text"].lower()
                if any(kw in text_lower for kw in keywords):
                    csi_code = chunk["metadata"].get("csi_code")
                    matching_chunks.append(chunk["id"])
                    if csi_code:
                        matching_csi.add(csi_code)
            
            # Also add by CSI code pattern
            csi_patterns = {
                "peinture": ["09 91"],
                "plancher": ["09 65", "03 54"],
                "plafond": ["09 51", "09 53"],
                "céramique": ["09 30"],
                "porte": ["08 11", "08 14"],
                "fenêtre": ["08 51", "08 44"],
                "cloison": ["09 21", "09 22"],
                "isolation": ["07 21"],
                "quincaillerie": ["08 71"],
                "accessoires": ["10 21", "10 28"]
            }
            
            for pattern in csi_patterns.get(mat_type, []):
                for chunk in self.chunks:
                    csi = chunk["metadata"].get("csi_code") or ""
                    if csi and csi.startswith(pattern):
                        matching_csi.add(csi)
            
            index[mat_type] = {
                "keywords": keywords,
                "csi_sections": sorted(matching_csi),
                "chunk_count": len(matching_chunks),
                "sample_chunks": matching_chunks[:5]
            }
        
        return index
    
    def build_search_entries(self) -> list[dict]:
        """Build flat search entries optimized for simple text search."""
        entries = []
        
        # Entry per room with all applicable info
        for room in self.rooms:
            room_id = room["id"]
            room_type = self._normalize_room_type(room.get("name", ""))
            mapping = ROOM_TYPE_CSI_MAPPING.get(room_type, {})
            
            # Collect all relevant CSI info
            csi_codes = mapping.get("required", []) + mapping.get("common", [])
            csi_text = " ".join([
                f"{code} {CSI_DESCRIPTIONS.get(code, '')}"
                for code in csi_codes
            ])
            
            entries.append({
                "id": f"room_{room_id}",
                "type": "room",
                "room_id": room_id,
                "room_name": room.get("name", ""),
                "room_type": room_type,
                "floor": room.get("floor"),
                "block": room.get("block"),
                "confidence": room.get("confidence"),
                "extraction_method": room.get("extraction_method"),
                "source_pages": room.get("source_pages", room.get("pages", [])),
                "searchable_text": f"{room_id} {room.get('name', '')} {room_type} {csi_text}",
                "csi_codes": csi_codes
            })
        
        # Entry per CSI section
        csi_sections = {}
        for chunk in self.chunks:
            csi = chunk["metadata"].get("csi_code")
            if csi and csi not in csi_sections:
                csi_sections[csi] = {
                    "title": CSI_DESCRIPTIONS.get(csi, chunk["metadata"].get("csi_title", "")),
                    "chunks": [],
                    "rooms": set()
                }
            if csi:
                csi_sections[csi]["chunks"].append(chunk["id"])
                refs = self._extract_room_refs_from_text(chunk["text"])
                csi_sections[csi]["rooms"].update(refs)
        
        for csi_code, data in csi_sections.items():
            # Find applicable room types
            room_types = []
            for rt, mapping in ROOM_TYPE_CSI_MAPPING.items():
                if csi_code in mapping.get("required", []) + mapping.get("common", []):
                    room_types.append(rt)
            
            entries.append({
                "id": f"csi_{csi_code.replace(' ', '_')}",
                "type": "csi_section",
                "csi_code": csi_code,
                "csi_title": data["title"],
                "chunk_count": len(data["chunks"]),
                "rooms_mentioned": sorted(data["rooms"]),
                "room_types_applicable": room_types,
                "searchable_text": f"{csi_code} {data['title']} " + " ".join(room_types)
            })
        
        return entries
    
    def build_unified_index(self) -> dict:
        """Build complete unified index."""
        # Calculate confidence statistics
        confidences = [r.get("confidence") for r in self.rooms if r.get("confidence") is not None]
        avg_confidence = sum(confidences) / len(confidences) if confidences else None
        
        return {
            "meta": {
                "project": "Réhabilitation de l'école Enfant-Jésus",
                "location": "Sorel-Tracy, Québec",
                "created_at": datetime.now().isoformat(),
                "total_rooms": len(self.rooms),
                "total_chunks": len(self.chunks),
                "features": [
                    "bidirectional_room_csi_links",
                    "room_type_defaults",
                    "material_type_index",
                    "text_search_entries",
                    "confidence_scores",
                    "source_traceability"
                ]
            },
            "quality": {
                "average_confidence": round(avg_confidence, 3) if avg_confidence else None,
                "rooms_with_confidence": len(confidences),
                "high_confidence_count": sum(1 for c in confidences if c >= 0.8),
                "low_confidence_count": sum(1 for c in confidences if c < 0.5),
                **self.quality_meta
            },
            "rooms": self.rooms,
            "room_index": self.build_room_index(),
            "csi_index": self.build_csi_index(),
            "type_index": self.build_type_index(),
            "search_entries": self.build_search_entries(),
            "mappings": {
                "room_type_csi": ROOM_TYPE_CSI_MAPPING,
                "csi_descriptions": CSI_DESCRIPTIONS
            }
        }


def load_json(path: Path) -> dict:
    """Load JSON safely."""
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Build unified RAG index")
    parser.add_argument("--rooms", default="output/rooms_complete.json")
    parser.add_argument("--chunks", default="output/rag/chunks.json")
    parser.add_argument("-o", "--output", default="output/rag/unified_rag.json")
    args = parser.parse_args()
    
    # Load data
    rooms_data = load_json(Path(args.rooms))
    chunks_data = load_json(Path(args.chunks))
    
    print(f"Loaded {len(rooms_data.get('rooms', []))} rooms")
    print(f"Loaded {len(chunks_data.get('chunks', []))} chunks")
    
    # Build index
    builder = UnifiedRAGBuilder(rooms_data, chunks_data)
    unified = builder.build_unified_index()
    
    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(unified, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "="*60)
    print("UNIFIED RAG INDEX CREATED")
    print("="*60)
    print(f"Rooms indexed: {len(unified['room_index'])}")
    print(f"CSI sections: {len(unified['csi_index'])}")
    print(f"Material types: {len(unified['type_index'])}")
    print(f"Search entries: {len(unified['search_entries'])}")
    print(f"Output: {output_path}")
    print("="*60)
    
    # Sample stats
    print("\nRoom type distribution:")
    type_counts = defaultdict(int)
    for room_id, info in unified['room_index'].items():
        type_counts[info['room_type']] += 1
    for rt, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {rt}: {count}")


if __name__ == "__main__":
    main()
