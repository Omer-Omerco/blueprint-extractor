#!/usr/bin/env python3
"""
Fix room bounding boxes using PyMuPDF text extraction.
Uses precise PDF text coordinates to locate rooms on the rendered images.
"""

import json
import shutil
import sys
from pathlib import Path
from datetime import datetime

import fitz  # PyMuPDF


WORKSPACE = Path(__file__).parent.parent
PDF_PATH = WORKSPACE / "output" / "C25-256 _Architecture_plan_Construction.pdf"
ROOMS_JSON = WORKSPACE / "output" / "rooms_complete.json"

# Image dimensions (both pages are identical)
IMG_W, IMG_H = 4967, 3509

# Page filename -> PDF page number (0-indexed for fitz)
PAGE_MAP = {
    "page-010.png": 9,   # page 10
    "page-012.png": 11,  # page 12
}

PADDING_PX = 30  # padding around text labels


def get_all_spans(page):
    """Extract all text spans from a page."""
    spans = []
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if text:
                    spans.append({
                        "text": text,
                        "bbox": span["bbox"],  # (x0, y0, x1, y1) in PDF points
                        "size": span.get("size", 0),
                    })
    return spans


def find_room_on_page(room_id, room_name, spans, scale):
    """
    Find a room's text on a page and return pixel bbox.
    Returns [x1, y1, x2, y2] or None.
    """
    parts = room_id.split("-")
    # e.g., "A-100" -> block="A", number="100"
    # "A-102-1" -> block="A", number="102-1"
    # "B-134-2" -> block="B", number="134-2"
    if len(parts) >= 2:
        number_part = "-".join(parts[1:])
        base_number = parts[1]
    else:
        number_part = room_id
        base_number = room_id

    # Find number text candidates
    candidates = []
    for s in spans:
        t = s["text"]
        # Match exact room_id, number, or base number
        if t == room_id or t == number_part or t == base_number:
            candidates.append(s)

    if not candidates:
        # Try without dash: "102.1" for "102-1"
        alt = number_part.replace("-", ".")
        for s in spans:
            if s["text"] == alt:
                candidates.append(s)

    if not candidates:
        return None

    # If multiple candidates, pick the one closest to a matching name
    best_span = candidates[0]
    best_name_span = None

    if room_name and len(candidates) > 1:
        name_spans = [s for s in spans if s["text"].upper() == room_name.upper()]
        if name_spans:
            import math
            best_dist = float("inf")
            for cs in candidates:
                cb = cs["bbox"]
                ccx, ccy = (cb[0]+cb[2])/2, (cb[1]+cb[3])/2
                for ns in name_spans:
                    nb = ns["bbox"]
                    ncx, ncy = (nb[0]+nb[2])/2, (nb[1]+nb[3])/2
                    dist = math.sqrt((ccx-ncx)**2 + (ccy-ncy)**2)
                    if dist < best_dist:
                        best_dist = dist
                        best_span = cs
                        best_name_span = ns

    # If we didn't find name yet, search for closest one
    if best_name_span is None and room_name:
        import math
        cb = best_span["bbox"]
        ccx, ccy = (cb[0]+cb[2])/2, (cb[1]+cb[3])/2
        best_dist = 150  # max PDF points distance
        for s in spans:
            if s["text"].upper() == room_name.upper():
                nb = s["bbox"]
                ncx, ncy = (nb[0]+nb[2])/2, (nb[1]+nb[3])/2
                dist = math.sqrt((ccx-ncx)**2 + (ccy-ncy)**2)
                if dist < best_dist:
                    best_dist = dist
                    best_name_span = s

    # Build pixel bbox
    nb = best_span["bbox"]
    x0 = nb[0] * scale
    y0 = nb[1] * scale
    x1 = nb[2] * scale
    y1 = nb[3] * scale

    if best_name_span:
        nmb = best_name_span["bbox"]
        x0 = min(x0, nmb[0] * scale)
        y0 = min(y0, nmb[1] * scale)
        x1 = max(x1, nmb[2] * scale)
        y1 = max(y1, nmb[3] * scale)

    # Clamp to image bounds
    bbox = [
        max(0, int(x0 - PADDING_PX)),
        max(0, int(y0 - PADDING_PX)),
        min(IMG_W, int(x1 + PADDING_PX)),
        min(IMG_H, int(y1 + PADDING_PX)),
    ]
    return bbox


def main():
    print("=== Fix Room Bounding Boxes ===")

    # Load rooms
    with open(ROOMS_JSON) as f:
        data = json.load(f)
    rooms = data["rooms"]
    print(f"Total rooms: {len(rooms)}")

    # Open PDF
    doc = fitz.open(str(PDF_PATH))

    # Precompute: get spans and scale for each page
    page_data = {}
    for page_file, page_idx in PAGE_MAP.items():
        page = doc[page_idx]
        scale = IMG_W / page.rect.width
        spans = get_all_spans(page)
        page_data[page_file] = {"scale": scale, "spans": spans}
        print(f"  {page_file}: page_pts={page.rect.width:.0f}x{page.rect.height:.0f}, scale={scale:.4f}, spans={len(spans)}")

    doc.close()

    # Process each room
    updated = 0
    not_found = []

    for room in rooms:
        room_id = room["id"]
        room_name = room.get("name", "")
        page_file = room.get("bbox_source", "")

        if page_file not in page_data:
            not_found.append(f"{room_id}: unknown page {page_file}")
            continue

        pd = page_data[page_file]
        new_bbox = find_room_on_page(room_id, room_name, pd["spans"], pd["scale"])

        if new_bbox:
            room["bbox"] = new_bbox
            room["bbox_method"] = "pymupdf_text"
            room["bbox_updated"] = datetime.now().isoformat()
            updated += 1
            if updated <= 5:
                print(f"  {room_id:12s} {room_name:25s} → bbox={new_bbox}")
        else:
            not_found.append(f"{room_id} ({room_name})")

    print(f"\n=== Results ===")
    print(f"Updated: {updated}/{len(rooms)}")
    print(f"Not found: {len(not_found)}")
    if not_found:
        for nf in not_found[:20]:
            print(f"  - {nf}")

    # Save backup and update
    backup = ROOMS_JSON.with_suffix(".json.bak")
    shutil.copy2(ROOMS_JSON, backup)

    data["bbox_extraction"] = {
        "date": datetime.now().isoformat(),
        "method": "pymupdf_text_extraction",
        "plans_analyzed": list(PAGE_MAP.keys()),
        "total_bboxes_extracted": updated,
        "rooms_not_found": len(not_found),
    }

    with open(ROOMS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Saved to {ROOMS_JSON}")
    print(f"✓ Backup: {backup}")


if __name__ == "__main__":
    main()
