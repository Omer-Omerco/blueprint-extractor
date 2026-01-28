#!/usr/bin/env python3
"""
Room Crop Extractor

Generates cropped PNG images of detected rooms from PDF pages.
Takes rooms.json and PDF as input, outputs individual PNG files per room.

Usage:
    python scripts/crop_extractor.py rooms.json input.pdf -o output/crops/
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF required. Run: pip install pymupdf", file=sys.stderr)
    sys.exit(1)


def load_rooms(rooms_path: str) -> dict:
    """
    Load rooms from JSON file.
    
    Args:
        rooms_path: Path to rooms.json
    
    Returns:
        Rooms data dict
    """
    rooms_path = Path(rooms_path).expanduser().resolve()
    with open(rooms_path) as f:
        return json.load(f)


def convert_bbox_to_fitz(bbox: dict, page_height: float, scale_factor: float = 1.0) -> fitz.Rect:
    """
    Convert room bbox to fitz.Rect format.
    
    Room bbox format: {x, y, width, height} where y increases downward from top
    fitz.Rect format: (x0, y0, x1, y1) where y increases downward
    
    Args:
        bbox: Room bounding box (may be in scaled coordinates)
        page_height: Height of the page (not used currently, kept for compatibility)
        scale_factor: Scale factor to convert from extraction coords to PDF coords
                     (typically DPI/72, e.g., 300/72 = 4.166)
    
    Returns:
        fitz.Rect object
    """
    x = bbox.get("x", 0) / scale_factor
    y = bbox.get("y", 0) / scale_factor
    width = bbox.get("width", 0) / scale_factor
    height = bbox.get("height", 0) / scale_factor
    
    # Create rect from top-left corner
    return fitz.Rect(x, y, x + width, y + height)


def sanitize_filename(name: str) -> str:
    """
    Sanitize room name for use as filename.
    
    Args:
        name: Room name/number
    
    Returns:
        Safe filename string
    """
    # Replace special characters with underscores
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
    # Remove consecutive underscores
    while "__" in safe:
        safe = safe.replace("__", "_")
    # Strip leading/trailing underscores
    return safe.strip("_")


def extract_room_crop(
    doc: fitz.Document,
    room: dict,
    output_dir: Path,
    dpi: int = 150,
    padding: float = 10.0,
    scale_factor: float = 1.0
) -> Optional[Path]:
    """
    Extract a cropped image of a single room.
    
    Args:
        doc: PyMuPDF document
        room: Room data dict with page, bbox, etc.
        output_dir: Output directory for crops
        dpi: Resolution for rendering
        padding: Padding around room bbox in points
        scale_factor: Scale factor for bbox coordinate conversion
    
    Returns:
        Path to saved PNG or None on failure
    """
    page_num = room.get("page", 1) - 1  # Convert to 0-indexed
    
    if page_num < 0 or page_num >= len(doc):
        print(f"Warning: Page {page_num + 1} out of range for room {room.get('id', '?')}")
        return None
    
    page = doc[page_num]
    page_rect = page.rect
    
    # Get room bbox
    bbox = room.get("bbox", {})
    if not bbox:
        print(f"Warning: No bbox for room {room.get('id', '?')}")
        return None
    
    # Convert bbox (applying scale factor)
    room_rect = convert_bbox_to_fitz(bbox, page_rect.height, scale_factor)
    
    # Add padding (in page coordinate space)
    padded_rect = fitz.Rect(
        max(0, room_rect.x0 - padding),
        max(0, room_rect.y0 - padding),
        min(page_rect.width, room_rect.x1 + padding),
        min(page_rect.height, room_rect.y1 + padding)
    )
    
    # Validate rect dimensions
    if padded_rect.width < 1 or padded_rect.height < 1:
        print(f"Warning: Invalid rect dimensions for room {room.get('id', '?')}: {padded_rect}")
        return None
    
    # Calculate zoom factor from DPI
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    
    # Render crop
    clip = padded_rect
    pix = page.get_pixmap(matrix=mat, clip=clip)
    
    # Generate filename
    room_id = room.get("id", "unknown")
    room_name = room.get("name") or room.get("number") or room_id
    safe_name = sanitize_filename(f"{room_id}_{room_name}")
    output_path = output_dir / f"{safe_name}.png"
    
    # Save
    pix.save(str(output_path))
    
    return output_path


def detect_scale_factor(rooms_data: dict, pdf_path: Path) -> float:
    """
    Detect the scale factor used in room coordinates.
    
    The room detector may output coordinates in a scaled space (e.g., at 300 DPI).
    We need to convert back to PDF page coordinates (72 DPI).
    
    Args:
        rooms_data: Rooms JSON data
        pdf_path: Path to source PDF
    
    Returns:
        Scale factor (1.0 if not scaled, or DPI/72 if scaled)
    """
    # Check if rooms_data has extraction DPI info
    extraction_dpi = rooms_data.get("extraction_dpi") or rooms_data.get("dpi")
    if extraction_dpi:
        return extraction_dpi / 72.0
    
    # Try to detect from room bbox vs page size
    rooms = rooms_data.get("rooms", [])
    if not rooms:
        return 1.0
    
    # Get first room's page and bbox
    room = rooms[0]
    bbox = room.get("bbox", {})
    page_num = room.get("page", 1) - 1
    
    if not bbox or bbox.get("x", 0) == 0:
        return 1.0
    
    # Open PDF to check page dimensions
    try:
        doc = fitz.open(str(pdf_path))
        if page_num < len(doc):
            page = doc[page_num]
            page_width = page.rect.width
            
            # If bbox.x is significantly larger than page width, 
            # coordinates are likely scaled
            bbox_x = bbox.get("x", 0)
            if bbox_x > page_width * 2:
                # Estimate scale factor
                # Common DPIs: 150, 200, 300
                for test_dpi in [300, 200, 150]:
                    scale = test_dpi / 72.0
                    if bbox_x / scale < page_width:
                        doc.close()
                        return scale
        doc.close()
    except Exception:
        pass
    
    return 1.0


def extract_all_rooms(
    rooms_data: dict,
    pdf_path: str,
    output_dir: str,
    dpi: int = 150,
    padding: float = 10.0,
    scale_factor: float = None
) -> dict:
    """
    Extract cropped images for all rooms.
    
    Args:
        rooms_data: Rooms JSON data
        pdf_path: Path to source PDF
        output_dir: Output directory for crops
        dpi: Resolution for rendering
        padding: Padding around room bbox
        scale_factor: Override scale factor (auto-detected if None)
    
    Returns:
        Results dict with extracted files
    """
    pdf_path = Path(pdf_path).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Detect or use provided scale factor
    if scale_factor is None:
        scale_factor = detect_scale_factor(rooms_data, pdf_path)
    
    # Open PDF
    doc = fitz.open(str(pdf_path))
    
    rooms = rooms_data.get("rooms", [])
    extracted = []
    failed = []
    
    for room in rooms:
        try:
            output_path = extract_room_crop(doc, room, output_dir, dpi, padding, scale_factor)
            if output_path:
                extracted.append({
                    "room_id": room.get("id"),
                    "room_name": room.get("name") or room.get("number"),
                    "page": room.get("page", 1),
                    "output_file": str(output_path)
                })
            else:
                failed.append({
                    "room_id": room.get("id"),
                    "reason": "extraction failed"
                })
        except Exception as e:
            failed.append({
                "room_id": room.get("id"),
                "reason": str(e)
            })
    
    doc.close()
    
    return {
        "source_pdf": str(pdf_path),
        "rooms_file": str(rooms_data.get("source", "")),
        "output_dir": str(output_dir),
        "dpi": dpi,
        "scale_factor_used": scale_factor,
        "total_rooms": len(rooms),
        "extracted": len(extracted),
        "failed": len(failed),
        "files": extracted,
        "errors": failed
    }


def run_extraction(
    rooms_path: str,
    pdf_path: str,
    output_dir: str,
    dpi: int = 150,
    padding: float = 10.0,
    scale_factor: float = None
) -> dict:
    """
    Run the complete extraction pipeline.
    
    Args:
        rooms_path: Path to rooms.json
        pdf_path: Path to source PDF
        output_dir: Output directory for crops
        dpi: Resolution for rendering
        padding: Padding around room bbox
        scale_factor: Override coordinate scale factor (auto-detected if None)
    
    Returns:
        Results dict
    """
    rooms_data = load_rooms(rooms_path)
    return extract_all_rooms(rooms_data, pdf_path, output_dir, dpi, padding, scale_factor)


def main():
    parser = argparse.ArgumentParser(
        description="Extract cropped room images from PDF"
    )
    parser.add_argument(
        "rooms",
        help="Path to rooms.json from room_detector"
    )
    parser.add_argument(
        "pdf",
        help="Path to source PDF file"
    )
    parser.add_argument(
        "-o", "--output",
        default="output/crops/",
        help="Output directory for cropped images (default: output/crops/)"
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="Resolution for rendering (default: 150)"
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=10.0,
        help="Padding around room bbox in points (default: 10.0)"
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=None,
        help="Scale factor for coordinates (auto-detected if not specified)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON to stdout"
    )

    args = parser.parse_args()

    results = run_extraction(
        args.rooms,
        args.pdf,
        args.output,
        args.dpi,
        args.padding,
        args.scale
    )

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"Extracted {results['extracted']}/{results['total_rooms']} room crops -> {results['output_dir']}")
        if results['errors']:
            print(f"Errors: {len(results['errors'])}")
            for err in results['errors'][:5]:
                print(f"  - {err['room_id']}: {err['reason']}")


if __name__ == "__main__":
    main()
