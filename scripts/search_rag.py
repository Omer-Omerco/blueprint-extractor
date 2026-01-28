#!/usr/bin/env python3
"""
Search the Unified RAG Index for Construction Projects.
École Enfant-Jésus - Sorel-Tracy

Supports queries like:
- "matériaux classe A-201"
- "peinture gymnase"
- "plancher corridors bloc A"
- "céramique toilettes"
- "quincaillerie portes"

Usage:
    python search_rag.py "quels matériaux pour la classe A-201?"
    python search_rag.py --room A-101
    python search_rag.py --type peinture
    python search_rag.py --csi "09 91 00"
"""

import argparse
import json
import re
from pathlib import Path
from typing import Optional


class RAGSearcher:
    """Search the unified RAG index."""
    
    def __init__(self, index_path: str = "output/rag/unified_rag.json", 
                 chunks_path: str = "output/rag/chunks.json"):
        self.index = self._load_json(index_path)
        self.chunks_data = self._load_json(chunks_path)
        self.chunks = {c["id"]: c for c in self.chunks_data.get("chunks", [])}
    
    def _load_json(self, path: str) -> dict:
        p = Path(path)
        if not p.exists():
            return {}
        with open(p) as f:
            return json.load(f)
    
    def search_room(self, room_id: str) -> dict:
        """Get all specs for a specific room."""
        room_id = room_id.upper()
        
        room_info = self.index.get("room_index", {}).get(room_id)
        if not room_info:
            # Try fuzzy match
            for rid in self.index.get("room_index", {}):
                if room_id in rid or rid in room_id:
                    room_info = self.index["room_index"][rid]
                    room_id = rid
                    break
        
        if not room_info:
            return {"error": f"Local {room_id} non trouvé", "suggestions": list(self.index.get("room_index", {}).keys())[:10]}
        
        # Get chunk content for required CSI
        csi_details = []
        for csi_item in room_info.get("csi_required", []):
            csi_code = csi_item["code"]
            chunk_samples = []
            for chunk_id, chunk in self.chunks.items():
                if chunk["metadata"].get("csi_code") == csi_code:
                    chunk_samples.append({
                        "chunk_id": chunk_id,
                        "preview": chunk["text"][:300] + "..."
                    })
                    if len(chunk_samples) >= 2:
                        break
            
            csi_details.append({
                "code": csi_code,
                "title": csi_item["title"],
                "samples": chunk_samples
            })
        
        return {
            "room_id": room_id,
            "room_name": room_info["room_info"].get("name"),
            "room_type": room_info["room_type"],
            "type_description": room_info["type_description"],
            "floor": room_info["room_info"].get("floor"),
            "block": room_info["room_info"].get("block"),
            "specifications": {
                "required": csi_details,
                "common": room_info.get("csi_common", [])
            },
            "direct_mentions_in_devis": room_info.get("direct_mentions", [])
        }
    
    def search_type(self, material_type: str) -> dict:
        """Get all sections for a material type."""
        type_index = self.index.get("type_index", {})
        
        # Normalize type
        mat_type = material_type.lower()
        
        # Try exact match
        if mat_type in type_index:
            type_info = type_index[mat_type]
        else:
            # Fuzzy match
            for t in type_index:
                if mat_type in t or t in mat_type:
                    type_info = type_index[t]
                    mat_type = t
                    break
            else:
                return {
                    "error": f"Type '{material_type}' non trouvé",
                    "available_types": list(type_index.keys())
                }
        
        # Get sample chunks
        samples = []
        for csi_code in type_info.get("csi_sections", []):
            for chunk_id, chunk in self.chunks.items():
                if chunk["metadata"].get("csi_code") == csi_code:
                    samples.append({
                        "csi_code": csi_code,
                        "chunk_id": chunk_id,
                        "preview": chunk["text"][:400]
                    })
                    break
        
        # Find applicable room types
        room_types = []
        for rt, mapping in self.index.get("mappings", {}).get("room_type_csi", {}).items():
            for csi in type_info.get("csi_sections", []):
                if csi in mapping.get("required", []) + mapping.get("common", []):
                    room_types.append(rt)
                    break
        
        return {
            "material_type": mat_type,
            "csi_sections": [
                {"code": c, "title": self.index.get("mappings", {}).get("csi_descriptions", {}).get(c, "")}
                for c in type_info.get("csi_sections", [])
            ],
            "chunk_count": type_info.get("chunk_count", 0),
            "room_types_applicable": room_types,
            "sample_specs": samples[:3]
        }
    
    def search_csi(self, csi_code: str) -> dict:
        """Get all info for a CSI section."""
        csi_index = self.index.get("csi_index", {})
        
        # Normalize
        csi_code = csi_code.strip()
        
        if csi_code not in csi_index:
            # Try fuzzy
            for c in csi_index:
                if csi_code.replace(" ", "") in c.replace(" ", ""):
                    csi_code = c
                    break
            else:
                return {
                    "error": f"Section CSI {csi_code} non trouvée",
                    "available": sorted(csi_index.keys())[:20]
                }
        
        csi_info = csi_index[csi_code]
        
        # Get chunks
        chunk_samples = []
        for chunk_id, chunk in self.chunks.items():
            if chunk["metadata"].get("csi_code") == csi_code:
                chunk_samples.append({
                    "chunk_id": chunk_id,
                    "preview": chunk["text"][:500]
                })
                if len(chunk_samples) >= 3:
                    break
        
        return {
            "csi_code": csi_code,
            "title": csi_info.get("title"),
            "chunk_count": csi_info.get("chunk_count"),
            "rooms_applicable": csi_info.get("room_types", []),
            "rooms_mentioned": csi_info.get("rooms_applicable", []),
            "sample_content": chunk_samples
        }
    
    def natural_query(self, query: str) -> dict:
        """Process natural language query."""
        query_lower = query.lower()
        
        # Extract room reference
        room_match = re.search(r'\b([A-D]-?\d{3})\b', query, re.IGNORECASE)
        if room_match:
            room_id = room_match.group(1).upper()
            if "-" not in room_id:
                room_id = f"{room_id[0]}-{room_id[1:]}"
        else:
            room_id = None
        
        # Extract material type
        material_types = self.index.get("type_index", {}).keys()
        found_type = None
        for mt in material_types:
            if mt in query_lower:
                found_type = mt
                break
        
        # Check for room type keywords
        room_type_keywords = {
            "classe": "CLASSE",
            "corridor": "CORRIDOR",
            "gymnase": "GYMNASE",
            "toilette": "TOILETTE",
            "wc": "WC",
            "vestiaire": "VESTIAIRE",
            "bureau": "BUREAU",
            "conciergerie": "CONCIERGERIE",
            "escalier": "ESCALIER"
        }
        found_room_type = None
        for kw, rt in room_type_keywords.items():
            if kw in query_lower:
                found_room_type = rt
                break
        
        # Extract CSI code
        csi_match = re.search(r'\b(\d{2}\s?\d{2}\s?\d{2})\b', query)
        csi_code = csi_match.group(1) if csi_match else None
        
        # Build response based on what we found
        results = {
            "query": query,
            "interpreted": {
                "room_id": room_id,
                "material_type": found_type,
                "room_type": found_room_type,
                "csi_code": csi_code
            },
            "results": []
        }
        
        # If specific room requested
        if room_id:
            room_result = self.search_room(room_id)
            if "error" not in room_result:
                # If also looking for specific material
                if found_type:
                    room_result["filtered_for"] = found_type
                    # Filter specs for this type
                    type_csi = set(self.index.get("type_index", {}).get(found_type, {}).get("csi_sections", []))
                    room_result["specifications"]["required"] = [
                        s for s in room_result["specifications"]["required"]
                        if s["code"] in type_csi
                    ]
                results["results"].append({"type": "room_specs", "data": room_result})
        
        # If room type but no specific room
        elif found_room_type and not room_id:
            # Find all rooms of this type
            matching_rooms = []
            for rid, rinfo in self.index.get("room_index", {}).items():
                if rinfo["room_type"] == found_room_type:
                    matching_rooms.append(rid)
            
            # Get specs for this room type
            mapping = self.index.get("mappings", {}).get("room_type_csi", {}).get(found_room_type, {})
            
            results["results"].append({
                "type": "room_type_specs",
                "data": {
                    "room_type": found_room_type,
                    "matching_rooms": matching_rooms,
                    "required_csi": [
                        {"code": c, "title": self.index.get("mappings", {}).get("csi_descriptions", {}).get(c, "")}
                        for c in mapping.get("required", [])
                    ],
                    "common_csi": [
                        {"code": c, "title": self.index.get("mappings", {}).get("csi_descriptions", {}).get(c, "")}
                        for c in mapping.get("common", [])
                    ]
                }
            })
        
        # If material type search
        if found_type and not room_id:
            type_result = self.search_type(found_type)
            results["results"].append({"type": "material_specs", "data": type_result})
        
        # If CSI code search
        if csi_code:
            csi_result = self.search_csi(csi_code)
            results["results"].append({"type": "csi_section", "data": csi_result})
        
        # If no specific query matched, do text search
        if not results["results"]:
            results["results"].append(self._text_search(query))
        
        return results
    
    def _text_search(self, query: str) -> dict:
        """Simple text search across chunks."""
        query_lower = query.lower()
        keywords = query_lower.split()
        
        matches = []
        for chunk_id, chunk in self.chunks.items():
            text_lower = chunk["text"].lower()
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                matches.append({
                    "chunk_id": chunk_id,
                    "csi_code": chunk["metadata"].get("csi_code"),
                    "csi_title": chunk["metadata"].get("csi_title"),
                    "score": score,
                    "preview": chunk["text"][:300]
                })
        
        matches.sort(key=lambda x: -x["score"])
        
        return {
            "type": "text_search",
            "data": {
                "query": query,
                "match_count": len(matches),
                "top_results": matches[:5]
            }
        }


def format_result(result: dict, verbose: bool = False) -> str:
    """Format search result for display."""
    output = []
    
    if "error" in result:
        return f"❌ {result['error']}\n" + (f"Suggestions: {result.get('suggestions', [])[:5]}" if result.get('suggestions') else "")
    
    # Handle direct room/csi/type results (not wrapped in "results")
    if "room_id" in result and "specifications" in result:
        # This is a room search result
        data = result
        output.append(f"📍 LOCAL: {data['room_id']} - {data['room_name']}")
        output.append(f"   Type: {data['room_type']} ({data['type_description']})")
        output.append(f"   Bloc: {data['block']}, Étage: {data['floor']}")
        output.append("")
        output.append("   📋 SPÉCIFICATIONS REQUISES:")
        for spec in data["specifications"]["required"]:
            output.append(f"      • {spec['code']}: {spec['title']}")
            if verbose and spec.get("samples"):
                for s in spec["samples"][:1]:
                    output.append(f"        → {s['preview'][:150]}...")
        
        if data["specifications"]["common"]:
            output.append("")
            output.append("   📋 SPÉCIFICATIONS COMMUNES:")
            for spec in data["specifications"]["common"]:
                output.append(f"      • {spec['code']}: {spec['title']}")
        return "\n".join(output)
    
    if "csi_code" in result and "chunk_count" in result:
        # This is a CSI search result
        data = result
        output.append(f"📑 CSI: {data['csi_code']} - {data.get('title', '')}")
        output.append(f"   Chunks: {data['chunk_count']}")
        if data.get("rooms_applicable"):
            output.append(f"   Types de locaux: {', '.join(data['rooms_applicable'])}")
        if data.get("rooms_mentioned"):
            output.append(f"   Locaux mentionnés: {', '.join(data['rooms_mentioned'][:10])}")
        if verbose and data.get("sample_content"):
            output.append("")
            output.append("   📄 CONTENU:")
            for sample in data["sample_content"][:2]:
                output.append(f"      {sample['preview'][:300]}...")
        return "\n".join(output)
    
    if "material_type" in result and "csi_sections" in result:
        # This is a type search result
        data = result
        output.append(f"🎨 MATÉRIAU: {data['material_type']}")
        output.append(f"   Sections CSI: {len(data['csi_sections'])}")
        output.append(f"   Chunks: {data['chunk_count']}")
        output.append("")
        output.append("   📋 SECTIONS PRINCIPALES:")
        for spec in data["csi_sections"][:15]:
            output.append(f"      • {spec['code']}: {spec['title']}")
        if verbose and data.get("sample_specs"):
            output.append("")
            output.append("   📄 EXTRAITS:")
            for sample in data["sample_specs"][:2]:
                output.append(f"      [{sample['csi_code']}]")
                output.append(f"      {sample['preview'][:200]}...")
        return "\n".join(output)
    
    if "results" in result:
        output.append(f"🔍 Query: {result['query']}")
        interpreted = result.get("interpreted", {})
        if any(interpreted.values()):
            output.append(f"   Interprété: {', '.join(f'{k}={v}' for k, v in interpreted.items() if v)}")
        output.append("")
        
        for r in result["results"]:
            rtype = r.get("type")
            data = r.get("data", {})
            
            if rtype == "room_specs":
                output.append(f"📍 LOCAL: {data['room_id']} - {data['room_name']}")
                output.append(f"   Type: {data['room_type']} ({data['type_description']})")
                output.append(f"   Bloc: {data['block']}, Étage: {data['floor']}")
                output.append("")
                output.append("   📋 SPÉCIFICATIONS REQUISES:")
                for spec in data["specifications"]["required"]:
                    output.append(f"      • {spec['code']}: {spec['title']}")
                    if verbose and spec.get("samples"):
                        for s in spec["samples"][:1]:
                            output.append(f"        → {s['preview'][:150]}...")
                
                if data["specifications"]["common"]:
                    output.append("")
                    output.append("   📋 SPÉCIFICATIONS COMMUNES:")
                    for spec in data["specifications"]["common"]:
                        output.append(f"      • {spec['code']}: {spec['title']}")
            
            elif rtype == "room_type_specs":
                output.append(f"📍 TYPE: {data['room_type']}")
                output.append(f"   Locaux: {', '.join(data['matching_rooms'][:10])}...")
                output.append("")
                output.append("   📋 SPÉCIFICATIONS REQUISES:")
                for spec in data["required_csi"]:
                    output.append(f"      • {spec['code']}: {spec['title']}")
            
            elif rtype == "material_specs":
                output.append(f"🎨 MATÉRIAU: {data['material_type']}")
                output.append(f"   Sections CSI: {len(data['csi_sections'])}")
                output.append(f"   Chunks: {data['chunk_count']}")
                output.append("")
                output.append("   📋 SECTIONS:")
                for spec in data["csi_sections"]:
                    output.append(f"      • {spec['code']}: {spec['title']}")
                
                if verbose and data.get("sample_specs"):
                    output.append("")
                    output.append("   📄 EXTRAITS:")
                    for sample in data["sample_specs"][:2]:
                        output.append(f"      [{sample['csi_code']}]")
                        output.append(f"      {sample['preview'][:200]}...")
            
            elif rtype == "csi_section":
                output.append(f"📑 CSI: {data['csi_code']} - {data['title']}")
                output.append(f"   Chunks: {data['chunk_count']}")
                if data.get("rooms_applicable"):
                    output.append(f"   Types de locaux: {', '.join(data['rooms_applicable'])}")
                if data.get("rooms_mentioned"):
                    output.append(f"   Locaux mentionnés: {', '.join(data['rooms_mentioned'][:10])}")
                
                if verbose and data.get("sample_content"):
                    output.append("")
                    output.append("   📄 CONTENU:")
                    for sample in data["sample_content"][:1]:
                        output.append(f"      {sample['preview'][:300]}...")
            
            elif rtype == "text_search":
                sdata = data["data"]
                output.append(f"🔎 Recherche texte: {sdata['query']}")
                output.append(f"   Résultats: {sdata['match_count']}")
                output.append("")
                for match in sdata["top_results"]:
                    output.append(f"   • [{match['csi_code']}] {match['csi_title']}")
                    output.append(f"     {match['preview'][:150]}...")
            
            output.append("")
    
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="Search RAG index")
    parser.add_argument("query", nargs="?", help="Natural language query")
    parser.add_argument("--room", "-r", help="Search by room ID (e.g., A-201)")
    parser.add_argument("--type", "-t", help="Search by material type (e.g., peinture)")
    parser.add_argument("--csi", "-c", help="Search by CSI code (e.g., 09 91 00)")
    parser.add_argument("--index", default="output/rag/unified_rag.json")
    parser.add_argument("--chunks", default="output/rag/chunks.json")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--json", "-j", action="store_true", help="Output raw JSON")
    
    args = parser.parse_args()
    
    searcher = RAGSearcher(args.index, args.chunks)
    
    if args.room:
        result = searcher.search_room(args.room)
    elif args.type:
        result = searcher.search_type(args.type)
    elif args.csi:
        result = searcher.search_csi(args.csi)
    elif args.query:
        result = searcher.natural_query(args.query)
    else:
        # Interactive mode
        print("RAG Search - École Enfant-Jésus")
        print("="*50)
        print("Exemples de queries:")
        print("  - matériaux classe A-201")
        print("  - peinture gymnase")
        print("  - plancher corridors")
        print("  - 09 91 00 (code CSI)")
        print("="*50)
        while True:
            try:
                query = input("\n🔍 Query: ").strip()
                if not query:
                    continue
                if query.lower() in ('q', 'quit', 'exit'):
                    break
                result = searcher.natural_query(query)
                print(format_result(result, verbose=True))
            except (KeyboardInterrupt, EOFError):
                break
        return
    
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_result(result, args.verbose))


if __name__ == "__main__":
    main()
