#!/usr/bin/env python3
"""
Extract objects (rooms, doors, windows, dimensions) from blueprint pages.
Uses the stable guide from analyze_project.py to inform extraction.
"""

import argparse
import json
import sys
import base64
from pathlib import Path
from typing import Optional

try:
    import anthropic
except ImportError:
    print("Error: anthropic SDK required. Run: pip install anthropic", file=sys.stderr)
    sys.exit(1)


EXTRACTION_PROMPT = """Tu es un expert en extraction de données de plans de construction québécois.

## Guide du projet
{guide}

## Règles d'extraction
{rules}

## Instructions

Analyse cette page de plan et extrais TOUS les objets visibles:

### 1. ROOMS (Locaux)
- Identifie chaque local avec son numéro et nom
- Mesure les dimensions en PIEDS-POUCES (ex: 25'-6" x 30'-0")
- Calcule la superficie en pi²

### 2. DOORS (Portes)
- Identifie chaque porte avec son numéro
- Note l'angle d'ouverture (90°, 180°, etc.)

### 3. WINDOWS (Fenêtres)
- Identifie les fenêtres avec leurs dimensions

### 4. DIMENSIONS (Cotes)
- Extrais toutes les cotes visibles
- Format: X'-Y" (pieds-pouces)

## Format de sortie (JSON strict)

```json
{
  "page_type": "PLAN|LEGEND|OTHER",
  "rooms": [
    {
      "id": "room-XXX",
      "name": "NOM DU LOCAL",
      "number": "XXX",
      "dimensions": {
        "width": "XX'-X\\"",
        "depth": "XX'-X\\"",
        "area_sqft": NNN
      },
      "confidence": 0.0-1.0
    }
  ],
  "doors": [
    {
      "id": "door-XXX",
      "number": "XXX",
      "swing_angle": 90,
      "confidence": 0.0-1.0
    }
  ],
  "windows": [
    {
      "id": "window-XXX",
      "width": "X'-X\\"",
      "confidence": 0.0-1.0
    }
  ],
  "dimensions": [
    {
      "id": "dim-XXX",
      "value_text": "XX'-X\\"",
      "value_inches": NNN,
      "context": "description de ce que mesure cette cote",
      "confidence": 0.0-1.0
    }
  ]
}
```

IMPORTANT: 
- Dimensions TOUJOURS en pieds-pouces, JAMAIS en métrique
- Sois exhaustif, extrais TOUT ce qui est visible
- Si incertain, indique confidence < 0.7
"""


def encode_image(image_path: Path) -> str:
    """Encode image as base64."""
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def get_media_type(image_path: Path) -> str:
    """Get media type from extension."""
    suffix = image_path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg"
    }.get(suffix, "image/png")


def extract_from_page(
    client: anthropic.Anthropic,
    image_path: Path,
    guide: str,
    rules: list,
    model: str = "claude-sonnet-4-20250514"
) -> dict:
    """Extract objects from a single page."""
    
    prompt = EXTRACTION_PROMPT.format(
        guide=guide,
        rules=json.dumps(rules, indent=2, ensure_ascii=False)
    )
    
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": get_media_type(image_path),
                        "data": encode_image(image_path)
                    }
                },
                {"type": "text", "text": prompt}
            ]
        }]
    )
    
    response_text = response.content[0].text
    
    # Parse JSON
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        import re
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    
    return {"error": "Failed to parse response", "raw": response_text}


def run_extraction(
    guide_path: str,
    pages_dir: str,
    output_dir: str,
    model: str = "claude-sonnet-4-20250514",
    max_pages: Optional[int] = None
) -> dict:
    """Extract objects from all pages."""
    
    guide_path = Path(guide_path).expanduser().resolve()
    pages_dir = Path(pages_dir).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load guide
    with open(guide_path) as f:
        guide_data = json.load(f)
    
    guide_text = guide_data.get("stable_guide", "")
    rules = guide_data.get("stable_rules", [])
    
    # Load manifest
    manifest_path = pages_dir / "manifest.json"
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    pages = manifest["pages"]
    if max_pages:
        pages = pages[:max_pages]
    
    print(f"Extracting objects from {len(pages)} pages...")
    
    client = anthropic.Anthropic()
    
    all_rooms = []
    all_doors = []
    all_windows = []
    all_dimensions = []
    page_results = []
    
    for i, page in enumerate(pages):
        page_num = page["number"]
        image_path = Path(page["path"])
        
        print(f"  [{page_num}/{len(pages)}] {image_path.name}...", end=" ", flush=True)
        
        try:
            result = extract_from_page(
                client,
                image_path,
                guide_text,
                rules,
                model
            )
            
            # Add page number to all objects
            for room in result.get("rooms", []):
                room["page"] = page_num
                all_rooms.append(room)
            
            for door in result.get("doors", []):
                door["page"] = page_num
                all_doors.append(door)
            
            for window in result.get("windows", []):
                window["page"] = page_num
                all_windows.append(window)
            
            for dim in result.get("dimensions", []):
                dim["page"] = page_num
                all_dimensions.append(dim)
            
            page_results.append({
                "page": page_num,
                "page_type": result.get("page_type", "UNKNOWN"),
                "rooms_count": len(result.get("rooms", [])),
                "doors_count": len(result.get("doors", [])),
                "dimensions_count": len(result.get("dimensions", []))
            })
            
            print(f"✓ {len(result.get('rooms', []))} rooms, {len(result.get('doors', []))} doors")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            page_results.append({"page": page_num, "error": str(e)})
    
    # Save results
    results = {
        "project": manifest.get("source_pdf", ""),
        "pages_processed": len(pages),
        "summary": {
            "total_rooms": len(all_rooms),
            "total_doors": len(all_doors),
            "total_windows": len(all_windows),
            "total_dimensions": len(all_dimensions)
        },
        "page_results": page_results
    }
    
    # Save individual files
    with open(output_dir / "rooms.json", "w") as f:
        json.dump(all_rooms, f, indent=2, ensure_ascii=False)
    
    with open(output_dir / "doors.json", "w") as f:
        json.dump(all_doors, f, indent=2, ensure_ascii=False)
    
    with open(output_dir / "windows.json", "w") as f:
        json.dump(all_windows, f, indent=2, ensure_ascii=False)
    
    with open(output_dir / "dimensions.json", "w") as f:
        json.dump(all_dimensions, f, indent=2, ensure_ascii=False)
    
    with open(output_dir / "extraction_summary.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Extraction complete!")
    print(f"  Rooms: {len(all_rooms)}")
    print(f"  Doors: {len(all_doors)}")
    print(f"  Windows: {len(all_windows)}")
    print(f"  Dimensions: {len(all_dimensions)}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Extract objects from blueprint pages"
    )
    parser.add_argument("guide", help="Path to guide.json from analyze_project")
    parser.add_argument(
        "--pages",
        required=True,
        help="Directory with extracted pages"
    )
    parser.add_argument(
        "-o", "--output",
        default="./output",
        help="Output directory"
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Claude model"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="Maximum pages to process"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output summary as JSON"
    )
    
    args = parser.parse_args()
    
    result = run_extraction(
        args.guide,
        args.pages,
        args.output,
        args.model,
        args.max_pages
    )
    
    if args.json:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
