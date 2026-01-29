#!/usr/bin/env python3
"""
Sniper Mode — Crop visuel d'un local à la volée.

Usage:
    python scripts/sniper.py A-204
    python scripts/sniper.py A-204 --plan A-150
    python scripts/sniper.py A-204 --all
    python scripts/sniper.py A-204 --list

Génère des crops haute-résolution directement depuis le PDF d'architecture.
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import fitz
except ImportError:
    print("Error: PyMuPDF required. Run: pip install pymupdf", file=sys.stderr)
    sys.exit(1)

# Plan descriptions pour contexte humain
PLAN_DESCRIPTIONS = {
    "A-000": "Page de garde / index",
    "A-050": "Notes générales / légende",
    "A-060": "Notes et détails portes extérieures",
    "A-100": "Démolition RDC (Bloc A)",
    "A-101": "Démolition 2e étage (Bloc A)",
    "A-102": "Démolition agrandissement",
    "A-110": "Démolition RDC (Bloc B/C)",
    "A-111": "Démolition 2e étage (Bloc B/C)",
    "A-150": "Plan de construction RDC (Bloc A)",
    "A-151": "Plan de construction (Bloc B/C)",
    "A-152": "Plan de construction agrandissement",
    "A-200": "Plafonds démolition RDC",
    "A-201": "Plafonds démolition 2e étage",
    "A-250": "Plafonds construction RDC",
    "A-251": "Plafonds construction 2e étage",
    "A-300": "Agrandissement / détails",
    "A-350": "Détails supplémentaires",
    "A-400": "Détails construction",
    "A-401": "Détails construction (suite)",
    "A-500": "Coupes",
    "A-501": "Coupes (suite)",
    "A-502": "Détails fenêtres",
    "A-550": "Détails en plan",
    "A-600": "Élévations extérieures",
    "A-601": "Élévations extérieures (suite)",
    "A-650": "Plan agrandi",
    "A-651": "Plan agrandi (suite)",
    "A-700": "Plan Bloc B",
    "A-800": "Plan agrandi salles de bain",
    "A-900": "Plan des finis RDC",
    "A-901": "Plan des finis 2e étage",
    "A-910": "Élévations intérieures finis",
    "A-911": "Élévations intérieures finis (suite)",
    "A-912": "Élévations intérieures finis (suite 2)",
    "A-950": "Bordereau des portes",
}

# Page index → plan ID mapping (verified from PDF cartouche 2025-01-23)
PAGE_TO_PLAN = {
    0: "A-000",  1: "A-050",  2: "A-060",
    3: "A-100",  4: "A-101",  5: "A-102",
    6: "A-110",  7: "A-111",
    8: "A-150",  9: "A-151", 10: "A-152",
    11: "A-200", 12: "A-201",
    13: "A-250", 14: "A-251",
    15: "A-300", 16: "A-350",
    17: "A-400", 18: "A-401",
    19: "A-500", 20: "A-501", 21: "A-502",
    22: "A-550",
    23: "A-600", 24: "A-601",
    25: "A-650", 26: "A-651",
    27: "A-700",
    28: "A-800",
    29: "A-900", 30: "A-901",
    31: "A-910", 32: "A-911", 33: "A-912",
    34: "A-950",
}

DEFAULT_PDF = "/Users/omer/Mon disque/Projet Ecole Mario/01_ARCHITECTURE/C25-256 _Architecture_plan_Construction.pdf"
DEFAULT_OUTPUT = "/Users/omer/clawd/skills/blueprint-extractor/output"


def find_room_on_pages(doc, room_id: str) -> list[dict]:
    """Find all pages where a room ID appears, with location info."""
    # Extract just the number part (A-204 → 204)
    parts = room_id.split("-")
    search_term = parts[-1] if len(parts) > 1 else room_id
    
    results = []
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        instances = page.search_for(search_term)
        
        if not instances:
            continue
        
        plan_id = PAGE_TO_PLAN.get(page_idx, f"page-{page_idx}")
        desc = PLAN_DESCRIPTIONS.get(plan_id, "")
        
        # Filter: check context around each instance to confirm it's the right room
        for inst in instances:
            # Get text around the match
            clip = fitz.Rect(
                max(0, inst.x0 - 50),
                max(0, inst.y0 - 50),
                min(page.rect.width, inst.x1 + 50),
                min(page.rect.height, inst.y1 + 50)
            )
            context = page.get_text("text", clip=clip).strip()
            
            results.append({
                "page_idx": page_idx,
                "plan_id": plan_id,
                "description": desc,
                "rect": inst,
                "context": context[:100],
            })
    
    return results


def generate_crop(doc, page_idx: int, rect, room_id: str, plan_id: str,
                  padding: int = 250, zoom: float = 3.0, output_dir: str = DEFAULT_OUTPUT) -> str:
    """Generate a high-res crop around a room location."""
    page = doc[page_idx]
    
    crop_rect = fitz.Rect(
        max(0, rect.x0 - padding),
        max(0, rect.y0 - padding),
        min(page.rect.width, rect.x1 + padding),
        min(page.rect.height, rect.y1 + padding)
    )
    
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, clip=crop_rect)
    
    output_path = Path(output_dir) / f"sniper_{room_id}_{plan_id}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(output_path))
    
    return str(output_path)


def sniper(room_id: str, plan_filter: str = None, list_only: bool = False,
           all_plans: bool = False, pdf_path: str = DEFAULT_PDF,
           output_dir: str = DEFAULT_OUTPUT, padding: int = 250, zoom: float = 3.0) -> list[dict]:
    """
    Main sniper function. Returns list of generated crops with metadata.
    
    Args:
        room_id: Room ID (e.g., "A-204")
        plan_filter: Specific plan to crop (e.g., "A-150")
        list_only: Just list pages, don't generate crops
        all_plans: Generate crops for all pages where room appears
        pdf_path: Path to architecture PDF
        output_dir: Output directory for crops
        padding: Padding around room label in PDF units
        zoom: Zoom factor for rendering
    
    Returns:
        List of dicts with: plan_id, description, output_path, context
    """
    doc = fitz.open(pdf_path)
    
    try:
        hits = find_room_on_pages(doc, room_id)
        
        if not hits:
            return []
        
        # Deduplicate by page (keep first hit per page)
        seen_pages = set()
        unique_hits = []
        for h in hits:
            if h["page_idx"] not in seen_pages:
                seen_pages.add(h["page_idx"])
                unique_hits.append(h)
        
        if list_only:
            return [{"plan_id": h["plan_id"], "description": h["description"], 
                     "context": h["context"]} for h in unique_hits]
        
        # Filter by plan if specified
        if plan_filter:
            unique_hits = [h for h in unique_hits if h["plan_id"] == plan_filter]
            if not unique_hits:
                return []
        elif not all_plans:
            # Default: just the construction plan (A-150 or A-151)
            preferred = [h for h in unique_hits if h["plan_id"] in ("A-150", "A-151")]
            if preferred:
                unique_hits = preferred[:1]
            else:
                unique_hits = unique_hits[:1]
        
        results = []
        for h in unique_hits:
            output_path = generate_crop(
                doc, h["page_idx"], h["rect"], room_id, h["plan_id"],
                padding=padding, zoom=zoom, output_dir=output_dir
            )
            results.append({
                "plan_id": h["plan_id"],
                "description": h["description"],
                "output_path": output_path,
                "context": h["context"],
            })
        
        return results
    
    finally:
        doc.close()


def main():
    parser = argparse.ArgumentParser(description="Sniper Mode — Crop visuel d'un local")
    parser.add_argument("room_id", help="Room ID (e.g., A-204)")
    parser.add_argument("--plan", help="Specific plan (e.g., A-150)")
    parser.add_argument("--all", action="store_true", help="Generate all plans")
    parser.add_argument("--list", action="store_true", help="List pages only")
    parser.add_argument("--pdf", default=DEFAULT_PDF, help="PDF path")
    parser.add_argument("--output", "-o", default=DEFAULT_OUTPUT, help="Output dir")
    parser.add_argument("--padding", type=int, default=250, help="Padding (PDF units)")
    parser.add_argument("--zoom", type=float, default=3.0, help="Zoom factor")
    
    args = parser.parse_args()
    
    results = sniper(
        room_id=args.room_id,
        plan_filter=args.plan,
        list_only=args.list,
        all_plans=args.all,
        pdf_path=args.pdf,
        output_dir=args.output,
        padding=args.padding,
        zoom=args.zoom,
    )
    
    if not results:
        print(f"❌ Local {args.room_id} non trouvé dans les plans.")
        sys.exit(1)
    
    if args.list:
        print(f"📍 {args.room_id} trouvé sur {len(results)} plan(s):\n")
        for r in results:
            print(f"  • {r['plan_id']} — {r['description']}")
    else:
        for r in results:
            print(f"✅ {r['plan_id']} ({r['description']}): {r['output_path']}")


if __name__ == "__main__":
    main()
