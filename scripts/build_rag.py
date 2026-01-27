#!/usr/bin/env python3
"""
Build RAG (Retrieval-Augmented Generation) index from extracted data.
Creates searchable JSON structure for querying blueprint data.
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any


def parse_dimension(dim_text: str) -> dict:
    """Parse dimension text like 25'-6" into structured data."""
    
    # Pattern: X'-Y" or X'-Y 1/2" or X' or Y"
    pattern = r"(\d+)'[-\s]?(\d+)?(?:\s*(\d+)/(\d+))?\s*\"?"
    
    match = re.match(pattern, dim_text.strip())
    if not match:
        return {"raw": dim_text, "inches": None}
    
    feet = int(match.group(1))
    inches = int(match.group(2)) if match.group(2) else 0
    frac_num = int(match.group(3)) if match.group(3) else 0
    frac_den = int(match.group(4)) if match.group(4) else 1
    
    total_inches = (feet * 12) + inches + (frac_num / frac_den if frac_den else 0)
    
    return {
        "raw": dim_text,
        "feet": feet,
        "inches": inches,
        "total_inches": total_inches,
        "decimal_feet": total_inches / 12
    }


def normalize_text(text: str) -> str:
    """Normalize text for search."""
    return re.sub(r'\s+', ' ', text.lower().strip())


def build_index(source_dir: str, output_dir: str) -> dict:
    """Build searchable RAG index from extracted data."""
    
    source_dir = Path(source_dir).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load all data files
    rooms = []
    doors = []
    windows = []
    dimensions = []
    legend = []
    guide = {}
    
    if (source_dir / "rooms.json").exists():
        with open(source_dir / "rooms.json") as f:
            rooms = json.load(f)
    
    if (source_dir / "doors.json").exists():
        with open(source_dir / "doors.json") as f:
            doors = json.load(f)
    
    if (source_dir / "windows.json").exists():
        with open(source_dir / "windows.json") as f:
            windows = json.load(f)
    
    if (source_dir / "dimensions.json").exists():
        with open(source_dir / "dimensions.json") as f:
            dimensions = json.load(f)
    
    if (source_dir / "legend.json").exists():
        with open(source_dir / "legend.json") as f:
            legend = json.load(f)
    
    if (source_dir / "guide.json").exists():
        with open(source_dir / "guide.json") as f:
            guide = json.load(f)
    
    # Build search entries
    search_entries = []
    
    # Index rooms
    for room in rooms:
        entry = {
            "type": "room",
            "id": room.get("id", ""),
            "name": room.get("name", ""),
            "number": room.get("number", ""),
            "page": room.get("page"),
            "dimensions": room.get("dimensions", {}),
            "confidence": room.get("confidence", 0),
            "search_text": normalize_text(
                f"{room.get('name', '')} {room.get('number', '')} "
                f"local pièce salle {room.get('dimensions', {}).get('area_sqft', '')} pi²"
            )
        }
        
        # Parse dimensions for search
        if room.get("dimensions"):
            dims = room["dimensions"]
            if dims.get("width"):
                entry["width_parsed"] = parse_dimension(dims["width"])
            if dims.get("depth"):
                entry["depth_parsed"] = parse_dimension(dims["depth"])
        
        search_entries.append(entry)
    
    # Index doors
    for door in doors:
        entry = {
            "type": "door",
            "id": door.get("id", ""),
            "number": door.get("number", ""),
            "page": door.get("page"),
            "swing_angle": door.get("swing_angle"),
            "confidence": door.get("confidence", 0),
            "search_text": normalize_text(
                f"porte {door.get('number', '')} door"
            )
        }
        search_entries.append(entry)
    
    # Index windows
    for window in windows:
        entry = {
            "type": "window",
            "id": window.get("id", ""),
            "width": window.get("width", ""),
            "page": window.get("page"),
            "confidence": window.get("confidence", 0),
            "search_text": normalize_text(
                f"fenêtre window {window.get('width', '')}"
            )
        }
        search_entries.append(entry)
    
    # Index dimensions
    for dim in dimensions:
        parsed = parse_dimension(dim.get("value_text", ""))
        entry = {
            "type": "dimension",
            "id": dim.get("id", ""),
            "value_text": dim.get("value_text", ""),
            "value_inches": dim.get("value_inches") or parsed.get("total_inches"),
            "context": dim.get("context", ""),
            "page": dim.get("page"),
            "confidence": dim.get("confidence", 0),
            "parsed": parsed,
            "search_text": normalize_text(
                f"dimension cote {dim.get('value_text', '')} {dim.get('context', '')}"
            )
        }
        search_entries.append(entry)
    
    # Index legend
    for symbol in legend:
        entry = {
            "type": "symbol",
            "symbol": symbol.get("symbol", ""),
            "meaning": symbol.get("meaning", ""),
            "category": symbol.get("category", ""),
            "page": symbol.get("page"),
            "search_text": normalize_text(
                f"symbole légende {symbol.get('symbol', '')} {symbol.get('meaning', '')}"
            )
        }
        search_entries.append(entry)
    
    # Build main index
    index = {
        "version": "1.0",
        "project": guide.get("source_pdf") if isinstance(guide, dict) else "",
        "stats": {
            "rooms": len(rooms),
            "doors": len(doors),
            "windows": len(windows),
            "dimensions": len(dimensions),
            "symbols": len(legend),
            "total_entries": len(search_entries)
        },
        "entries": search_entries
    }
    
    # Save index
    with open(output_dir / "index.json", "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    
    # Save per-page data
    pages_dir = output_dir / "pages"
    pages_dir.mkdir(exist_ok=True)
    
    pages_data = {}
    for entry in search_entries:
        page = entry.get("page")
        if page is not None:
            if page not in pages_data:
                pages_data[page] = {
                    "page": page,
                    "rooms": [],
                    "doors": [],
                    "windows": [],
                    "dimensions": [],
                    "symbols": []
                }
            
            entry_type = entry["type"]
            if entry_type == "room":
                pages_data[page]["rooms"].append(entry)
            elif entry_type == "door":
                pages_data[page]["doors"].append(entry)
            elif entry_type == "window":
                pages_data[page]["windows"].append(entry)
            elif entry_type == "dimension":
                pages_data[page]["dimensions"].append(entry)
            elif entry_type == "symbol":
                pages_data[page]["symbols"].append(entry)
    
    for page_num, data in pages_data.items():
        with open(pages_dir / f"page-{page_num:03d}.json", "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Copy guide if exists
    if guide:
        with open(output_dir / "guide.json", "w") as f:
            json.dump(guide, f, indent=2, ensure_ascii=False)
        
        if guide.get("stable_guide"):
            with open(output_dir / "guide.md", "w") as f:
                f.write(guide["stable_guide"])
    
    print(f"✓ RAG index built: {output_dir / 'index.json'}")
    print(f"  Total entries: {len(search_entries)}")
    print(f"  Pages indexed: {len(pages_data)}")
    
    return index


def main():
    parser = argparse.ArgumentParser(
        description="Build RAG index from extracted blueprint data"
    )
    parser.add_argument("source", help="Source directory with extracted data")
    parser.add_argument(
        "-o", "--output",
        default="./rag",
        help="Output directory for RAG"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output index as JSON"
    )
    
    args = parser.parse_args()
    
    index = build_index(args.source, args.output)
    
    if args.json:
        print(json.dumps(index, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
