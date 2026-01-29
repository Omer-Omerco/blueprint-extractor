#!/usr/bin/env python3
"""
Query the gold-verified RAG index.
100% source-traceable — every answer cites its source document + page.
Returns "Information non trouvée" when data is not in verified sources.

Usage:
    python scripts/query_rag_gold.py "C'est quoi le local A-204?"
    python scripts/query_rag_gold.py "Où est la chaufferie?"
    python scripts/query_rag_gold.py "Combien de classes dans le bloc A?"
    python scripts/query_rag_gold.py --json "corridor 101"
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional


NOT_FOUND_MSG = "Information non trouvée dans les documents vérifiés."
FABRICATED_MSG = "⚠️ Ce numéro de local n'existe PAS sur les plans architecturaux. Il a été identifié comme fabricé (hallucination d'un ancien système)."


def load_index(rag_dir: str = None) -> dict:
    """Load the gold RAG index."""
    if rag_dir is None:
        rag_dir = Path(__file__).parent.parent / "rag_gold"
    else:
        rag_dir = Path(rag_dir).expanduser().resolve()
    
    index_path = rag_dir / "index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"No gold RAG index at {index_path}. Run build_rag_gold.py first.")
    
    with open(index_path) as f:
        return json.load(f)


def normalize_query(query: str) -> list[str]:
    """Normalize query into search terms with synonym expansion."""
    query = query.lower().strip()
    
    # Remove common question words
    query = re.sub(r'\b(c\'est quoi|quel est|où est|combien de|qu\'est-ce que|what is|where is|how many)\b', '', query)
    query = re.sub(r'[?,!.\'\"()]', ' ', query)
    
    terms = [t for t in re.split(r'\s+', query.strip()) if t and len(t) > 1]
    expanded = set(terms)
    
    # Synonym mapping
    synonyms = {
        "room": ["local", "pièce", "salle", "room"],
        "door": ["porte", "door"],
        "corridor": ["corridor", "couloir", "hall", "passage"],
        "bathroom": ["toilette", "wc", "salle de bain"],
        "class": ["classe", "class", "salle de classe"],
        "storage": ["dépôt", "rangement", "storage", "entrepôt"],
        "office": ["bureau", "office"],
        "gym": ["gymnase", "gym"],
        "library": ["bibliothèque", "library"],
        "boiler": ["chaufferie", "mécanique", "mechanical", "boiler"],
        "entry": ["vestibule", "entrée", "sas", "entry"],
        "kindergarten": ["maternelle", "kindergarten"],
        "daycare": ["service de garde", "garde", "daycare"],
        "teachers": ["professeurs", "enseignants", "teachers", "staff"],
        "janitor": ["concierge", "janitor"],
    }
    
    for term in terms:
        for key, syn_list in synonyms.items():
            if term in syn_list:
                expanded.update(syn_list)
    
    return list(expanded)


def extract_room_id(query: str) -> Optional[str]:
    """Try to extract a room ID from the query."""
    query = query.upper().strip()
    
    # Match patterns: A-204, B-131, C-151, 204, 131, etc.
    # Also match sub-rooms: A-102-1, 102-1, 211-1
    patterns = [
        r'([ABC])-(\d{3}(?:-\d+)?(?:-[A-Z])?)',  # A-204, B-131-2, A-111-B
        r'\b(\d{3}(?:-\d+)?(?:-[A-Z])?)\b',       # 204, 131, 102-1, 111-B  
        r'([ABC])-(\d{2,3})\b',                     # A-12, B-13
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            groups = match.groups()
            if len(groups) == 2:
                return f"{groups[0]}-{groups[1]}"
            elif len(groups) == 1:
                return groups[0]
    
    return None


def detect_aggregate_query(query: str) -> Optional[dict]:
    """Detect aggregate queries like 'combien de classes dans le bloc A'."""
    query_lower = query.lower()
    
    # "Combien de X dans le bloc Y"
    match = re.search(r'combien\s+de\s+(\w+).*bloc\s+([abc])', query_lower)
    if match:
        return {
            "type": "count",
            "room_type": match.group(1),
            "block": match.group(2).upper()
        }
    
    # "Liste des X" or "tous les X"
    match = re.search(r'(?:liste|tous)\s+(?:des|les)\s+(\w+)', query_lower)
    if match:
        return {
            "type": "list",
            "room_type": match.group(1)
        }
    
    return None


def search_entries(
    index: dict,
    query: str,
    entry_type: Optional[str] = None,
    block: Optional[str] = None,
    floor: Optional[int] = None,
    min_confidence: str = None,
    limit: int = 20
) -> list[dict]:
    """
    Search the gold RAG index.
    Returns only verified entries with full source traceability.
    """
    # First check if query references a fabricated room
    room_id = extract_room_id(query)
    fabricated = set(index.get("fabricated_rooms", []))
    
    if room_id and room_id in fabricated:
        return [{
            "type": "fabricated_warning",
            "queried_id": room_id,
            "message": FABRICATED_MSG,
            "explanation": "Ce numéro n'existe pas sur les plans de construction."
        }]
    
    terms = normalize_query(query)
    results = []
    
    for entry in index.get("entries", []):
        # Filter by block
        if block and entry.get("block") != block:
            continue
        
        # Filter by floor
        if floor is not None and entry.get("floor") != floor:
            continue
        
        # Filter by confidence
        if min_confidence == "HIGH" and entry.get("confidence") != "HIGH":
            continue
        
        # Score matching
        search_text = entry.get("search_text", "")
        score = 0
        
        for term in terms:
            if term in search_text:
                score += 1
        
        # Boost exact ID/plan_id matches
        entry_id = entry.get("id", "").lower()
        plan_id = entry.get("plan_id", "").lower()
        name = entry.get("name", "").lower()
        
        if room_id:
            room_id_lower = room_id.lower()
            if room_id_lower == entry_id or room_id_lower == plan_id:
                score += 10  # Strong exact match
            # Also try without block prefix
            bare_id = room_id_lower.split("-", 1)[-1] if "-" in room_id_lower else room_id_lower
            if bare_id == plan_id:
                score += 10
        
        for term in terms:
            if term == name:
                score += 3
            elif term in name:
                score += 2
            if term == plan_id:
                score += 5
            elif term in plan_id:
                score += 2
        
        if score > 0:
            results.append({"entry": entry, "score": score})
    
    results.sort(key=lambda x: x["score"], reverse=True)
    return [r["entry"] for r in results[:limit]]


def format_room_result(entry: dict) -> str:
    """Format a room result with FULL source traceability."""
    lines = []
    
    # Header
    name = entry.get("name", "?")
    plan_id = entry.get("plan_id", "?")
    room_id = entry.get("id", "?")
    block = entry.get("block", "?")
    floor = entry.get("floor", "?")
    
    lines.append(f"📍 {name} ({room_id})")
    lines.append(f"   Numéro plan: {plan_id}")
    lines.append(f"   Bloc: {block}, Étage: {floor}")
    lines.append(f"   Type: {entry.get('room_type', '?')}")
    
    # Area if available
    if entry.get("area_pica"):
        lines.append(f"   Superficie: {entry['area_pica']} pi²")
    
    # Door schedule
    if entry.get("door_schedule"):
        lines.append(f"   Portes: {entry['door_schedule']}")
    
    # Notes
    if entry.get("notes"):
        lines.append(f"   Note: {entry['notes']}")
    
    # Devis reference
    if entry.get("devis_ref"):
        lines.append(f"   Devis: {entry['devis_ref']}")
    
    # SOURCE TRACEABILITY (mandatory)
    lines.append(f"   📄 Source: {entry.get('source', 'N/A')}")
    confidence = entry.get("confidence", "?")
    lines.append(f"   ✅ Confiance: {confidence}")
    
    if entry.get("source_pages"):
        lines.append(f"   📑 Pages: {', '.join(entry['source_pages'])}")
    
    return "\n".join(lines)


def format_fabricated_warning(entry: dict) -> str:
    """Format a fabricated room warning."""
    return (
        f"⚠️ LOCAL {entry.get('queried_id', '?')} — N'EXISTE PAS\n"
        f"   {entry.get('message', '')}\n"
        f"   {entry.get('explanation', '')}"
    )


def format_result(entry: dict) -> str:
    """Format any result entry."""
    if entry.get("type") == "fabricated_warning":
        return format_fabricated_warning(entry)
    return format_room_result(entry)


def handle_aggregate_query(index: dict, agg: dict) -> str:
    """Handle aggregate queries (counting, listing)."""
    entries = index.get("entries", [])
    
    # Map query terms to room types
    type_map = {
        "classes": "CLASSE",
        "classe": "CLASSE",
        "corridors": "CORRIDOR",
        "corridor": "CORRIDOR",
        "bureaux": "BUREAU",
        "bureau": "BUREAU",
        "toilettes": "WC",
        "wc": "WC",
        "dépôts": "DÉPÔT",
        "dépôt": "DÉPÔT",
        "vestibules": "VESTIBULE",
        "vestibule": "VESTIBULE",
        "vestiaires": "VESTIAIRE",
        "vestiaire": "VESTIAIRE",
    }
    
    room_type = type_map.get(agg.get("room_type", "").lower())
    
    if agg["type"] == "count":
        block = agg.get("block")
        matching = [
            e for e in entries
            if e.get("room_type") == room_type
            and (block is None or e.get("block") == block)
        ]
        
        if not matching:
            return f"Aucun(e) {agg['room_type']} trouvé(e) dans le bloc {block}. {NOT_FOUND_MSG}"
        
        lines = [f"📊 {len(matching)} {agg['room_type']}(s) dans le Bloc {block}:\n"]
        for entry in matching:
            area = f" — {entry['area_pica']} pi²" if entry.get("area_pica") else ""
            lines.append(f"  • {entry['name']} ({entry['id']}){area}")
            lines.append(f"    📄 {entry['source']}")
        
        return "\n".join(lines)
    
    elif agg["type"] == "list":
        matching = [
            e for e in entries
            if e.get("room_type") == room_type
        ]
        
        if not matching:
            return f"Aucun(e) {agg['room_type']} trouvé(e). {NOT_FOUND_MSG}"
        
        lines = [f"📋 {len(matching)} {agg['room_type']}(s) dans le bâtiment:\n"]
        for entry in sorted(matching, key=lambda x: (x.get("block", ""), x.get("floor", 0), x.get("plan_id", ""))):
            area = f" — {entry['area_pica']} pi²" if entry.get("area_pica") else ""
            lines.append(f"  • {entry['name']} ({entry['id']}){area}")
        
        return "\n".join(lines)
    
    return NOT_FOUND_MSG


def query_gold_rag(
    query: str,
    rag_dir: str = None,
    output_format: str = "text",
    limit: int = 20
) -> dict:
    """
    Query the gold RAG. Returns structured response with source traceability.
    
    Returns:
        dict with keys: query, results, formatted, found, source_info
    """
    index = load_index(rag_dir)
    
    # Check for aggregate queries first
    agg = detect_aggregate_query(query)
    if agg:
        formatted = handle_aggregate_query(index, agg)
        return {
            "query": query,
            "type": "aggregate",
            "found": True,
            "formatted": formatted,
            "results": [],
            "source_info": {
                "verified_by": index.get("methodology", ""),
                "verification_date": index.get("verification_date", ""),
                "source_documents": index.get("source_documents", {})
            }
        }
    
    # Standard search
    results = search_entries(index, query, limit=limit)
    
    if not results:
        return {
            "query": query,
            "type": "search",
            "found": False,
            "formatted": f"🔍 Recherche: {query}\n\n{NOT_FOUND_MSG}",
            "results": [],
            "source_info": {
                "note": "Aucune correspondance dans les 80 locaux vérifiés du gold ground truth.",
                "source_documents": index.get("source_documents", {})
            }
        }
    
    # Format results
    formatted_lines = [f"🔍 {len(results)} résultat(s) pour: {query}\n"]
    for i, entry in enumerate(results, 1):
        formatted_lines.append(f"[{i}] {format_result(entry)}\n")
    
    return {
        "query": query,
        "type": "search",
        "found": True,
        "formatted": "\n".join(formatted_lines),
        "results": results,
        "source_info": {
            "verified_by": index.get("methodology", ""),
            "verification_date": index.get("verification_date", ""),
            "source_documents": index.get("source_documents", {})
        }
    }


def main():
    parser = argparse.ArgumentParser(
        description="Query gold-verified RAG (zero hallucination)"
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Search query"
    )
    parser.add_argument(
        "-d", "--dir",
        default=None,
        help="RAG directory (default: rag_gold/)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "-n", "--limit",
        type=int,
        default=10,
        help="Max results (default: 10)"
    )
    
    args = parser.parse_args()
    
    if not args.query:
        # Interactive mode
        try:
            index = load_index(args.dir)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
        
        print(f"📚 Gold RAG: {index['stats']['total_verified_rooms']} locaux vérifiés")
        print(f"   Source: {index.get('project_full_name', '?')}")
        print(f"   Vérifié: {index.get('verification_date', '?')}")
        print("   Tapez 'quit' pour sortir\n")
        
        while True:
            try:
                q = input("🔍 Query: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nAu revoir!")
                break
            
            if not q or q.lower() == "quit":
                break
            
            result = query_gold_rag(q, rag_dir=args.dir)
            print(f"\n{result['formatted']}\n")
    else:
        result = query_gold_rag(args.query, rag_dir=args.dir, limit=args.limit)
        
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(result["formatted"])


if __name__ == "__main__":
    main()
