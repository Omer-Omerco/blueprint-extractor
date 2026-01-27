#!/usr/bin/env python3
"""
Query the RAG index for blueprint data.
Supports natural language queries in French and English.
"""

import argparse
import json
import re
from pathlib import Path
from typing import Optional


def normalize_query(query: str) -> list[str]:
    """Normalize query into search terms."""
    # Lowercase and split
    query = query.lower().strip()
    
    # Handle common synonyms
    synonyms = {
        "room": ["local", "pièce", "salle", "room"],
        "door": ["porte", "door"],
        "window": ["fenêtre", "window"],
        "dimension": ["dimension", "cote", "mesure", "taille"],
        "area": ["superficie", "surface", "area", "pi²", "sqft"],
        "class": ["classe", "class"],
        "corridor": ["corridor", "couloir", "hall"],
        "bathroom": ["toilette", "salle de bain", "bathroom", "wc"],
        "storage": ["rangement", "storage", "entrepôt"],
    }
    
    terms = re.split(r'\s+', query)
    expanded = set(terms)
    
    for term in terms:
        for key, syn_list in synonyms.items():
            if term in syn_list:
                expanded.update(syn_list)
    
    return list(expanded)


def search_index(
    index: dict,
    query: str,
    entry_type: Optional[str] = None,
    page: Optional[int] = None,
    min_confidence: float = 0.0,
    limit: int = 20
) -> list[dict]:
    """Search the RAG index."""
    
    terms = normalize_query(query)
    results = []
    
    for entry in index.get("entries", []):
        # Filter by type
        if entry_type and entry.get("type") != entry_type:
            continue
        
        # Filter by page
        if page is not None and entry.get("page") != page:
            continue
        
        # Filter by confidence
        if entry.get("confidence", 1.0) < min_confidence:
            continue
        
        # Score by matching terms
        search_text = entry.get("search_text", "")
        score = sum(1 for term in terms if term in search_text)
        
        # Boost exact matches
        name = entry.get("name", "").lower()
        number = str(entry.get("number", "")).lower()
        
        for term in terms:
            if term == name or term == number:
                score += 3
            elif term in name or term in number:
                score += 2
        
        if score > 0:
            results.append({
                "entry": entry,
                "score": score
            })
    
    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    
    return [r["entry"] for r in results[:limit]]


def format_room(room: dict) -> str:
    """Format a room result for display."""
    dims = room.get("dimensions", {})
    area = dims.get("area_sqft", "?")
    width = dims.get("width", "?")
    depth = dims.get("depth", "?")
    
    return (
        f"📍 {room.get('name', 'Unknown')} #{room.get('number', '?')}\n"
        f"   Dimensions: {width} × {depth}\n"
        f"   Superficie: {area} pi²\n"
        f"   Page: {room.get('page', '?')}"
    )


def format_door(door: dict) -> str:
    """Format a door result."""
    return (
        f"🚪 Porte #{door.get('number', '?')}\n"
        f"   Angle: {door.get('swing_angle', '?')}°\n"
        f"   Page: {door.get('page', '?')}"
    )


def format_dimension(dim: dict) -> str:
    """Format a dimension result."""
    return (
        f"📏 {dim.get('value_text', '?')}\n"
        f"   Contexte: {dim.get('context', '?')}\n"
        f"   Page: {dim.get('page', '?')}"
    )


def format_symbol(sym: dict) -> str:
    """Format a symbol result."""
    return (
        f"🔣 {sym.get('symbol', '?')}\n"
        f"   Signification: {sym.get('meaning', '?')}\n"
        f"   Catégorie: {sym.get('category', '?')}"
    )


def format_result(entry: dict) -> str:
    """Format a search result for display."""
    entry_type = entry.get("type")
    
    formatters = {
        "room": format_room,
        "door": format_door,
        "dimension": format_dimension,
        "symbol": format_symbol,
    }
    
    formatter = formatters.get(entry_type)
    if formatter:
        return formatter(entry)
    
    return json.dumps(entry, indent=2, ensure_ascii=False)


def run_query(
    rag_dir: str,
    query: str,
    entry_type: Optional[str] = None,
    page: Optional[int] = None,
    output_format: str = "text",
    limit: int = 20
) -> list[dict]:
    """Run a query against the RAG."""
    
    rag_dir = Path(rag_dir).expanduser().resolve()
    index_path = rag_dir / "index.json"
    
    if not index_path.exists():
        print(f"Error: No index.json in {rag_dir}", file=sys.stderr)
        sys.exit(1)
    
    with open(index_path) as f:
        index = json.load(f)
    
    results = search_index(
        index,
        query,
        entry_type=entry_type,
        page=page,
        limit=limit
    )
    
    if output_format == "json":
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        if not results:
            print(f"Aucun résultat pour: {query}")
        else:
            print(f"🔍 {len(results)} résultat(s) pour: {query}\n")
            for i, entry in enumerate(results, 1):
                print(f"[{i}] {format_result(entry)}\n")
    
    return results


def interactive_mode(rag_dir: str):
    """Run interactive query mode."""
    
    rag_dir = Path(rag_dir).expanduser().resolve()
    index_path = rag_dir / "index.json"
    
    with open(index_path) as f:
        index = json.load(f)
    
    print(f"📚 RAG chargé: {index['stats']['total_entries']} entrées")
    print("   Tapez 'quit' pour sortir, 'stats' pour les statistiques\n")
    
    while True:
        try:
            query = input("🔍 Query: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAu revoir!")
            break
        
        if not query:
            continue
        
        if query.lower() == "quit":
            break
        
        if query.lower() == "stats":
            print(f"\n📊 Statistiques:")
            for key, value in index["stats"].items():
                print(f"   {key}: {value}")
            print()
            continue
        
        # Parse type filter
        entry_type = None
        for t in ["room", "door", "window", "dimension", "symbol"]:
            if query.lower().startswith(f"{t}:"):
                entry_type = t
                query = query[len(t)+1:].strip()
                break
        
        results = search_index(index, query, entry_type=entry_type)
        
        if not results:
            print("  Aucun résultat\n")
        else:
            print(f"\n  {len(results)} résultat(s):\n")
            for entry in results[:10]:
                print(f"  • {format_result(entry)}\n")


import sys

def main():
    parser = argparse.ArgumentParser(
        description="Query blueprint RAG index"
    )
    parser.add_argument("rag_dir", help="RAG directory with index.json")
    parser.add_argument(
        "query",
        nargs="?",
        help="Search query (omit for interactive mode)"
    )
    parser.add_argument(
        "-t", "--type",
        choices=["room", "door", "window", "dimension", "symbol"],
        help="Filter by entry type"
    )
    parser.add_argument(
        "-p", "--page",
        type=int,
        help="Filter by page number"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "-n", "--limit",
        type=int,
        default=20,
        help="Max results (default: 20)"
    )
    
    args = parser.parse_args()
    
    if args.query:
        run_query(
            args.rag_dir,
            args.query,
            entry_type=args.type,
            page=args.page,
            output_format="json" if args.json else "text",
            limit=args.limit
        )
    else:
        interactive_mode(args.rag_dir)


if __name__ == "__main__":
    main()
