#!/usr/bin/env python3
"""
Extract text and vector paths from PDF using PyMuPDF.
Outputs structured JSON with bounding boxes in pixel coordinates.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF


def get_page_dimensions(page: fitz.Page) -> dict:
    """Get page dimensions in PDF points."""
    rect = page.rect
    return {
        "width_pts": rect.width,
        "height_pts": rect.height
    }


def extract_text_blocks(page: fitz.Page, scale: float) -> list[dict]:
    """
    Extract all text with bounding boxes using get_text('dict').
    Scale coordinates to pixel space.
    """
    text_blocks = []
    page_dict = page.get_text("dict")

    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:  # Type 0 = text block
            continue

        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if not text:
                    continue

                bbox = span.get("bbox", [0, 0, 0, 0])
                text_blocks.append({
                    "text": text,
                    "bbox": {
                        "x": bbox[0] * scale,
                        "y": bbox[1] * scale,
                        "width": (bbox[2] - bbox[0]) * scale,
                        "height": (bbox[3] - bbox[1]) * scale
                    },
                    "font": span.get("font", ""),
                    "size": span.get("size", 0),
                    "flags": span.get("flags", 0)
                })

    return text_blocks


def extract_drawings(page: fitz.Page, scale: float) -> list[dict]:
    """
    Extract vector paths using get_drawings().
    Scale coordinates to pixel space.
    """
    drawings = []

    try:
        paths = page.get_drawings()
    except Exception:
        return drawings

    for path in paths:
        items = path.get("items", [])
        if not items:
            continue

        # Get bounding rect
        rect = path.get("rect", fitz.Rect())
        if rect.is_empty or rect.is_infinite:
            continue

        # Convert path items
        path_items = []
        for item in items:
            if not item:
                continue
            cmd = item[0]
            if cmd == "l":  # line
                path_items.append({
                    "type": "line",
                    "p1": {"x": item[1].x * scale, "y": item[1].y * scale},
                    "p2": {"x": item[2].x * scale, "y": item[2].y * scale}
                })
            elif cmd == "re":  # rectangle
                r = item[1]
                path_items.append({
                    "type": "rect",
                    "x": r.x0 * scale,
                    "y": r.y0 * scale,
                    "width": r.width * scale,
                    "height": r.height * scale
                })
            elif cmd == "c":  # curve
                path_items.append({
                    "type": "curve",
                    "p1": {"x": item[1].x * scale, "y": item[1].y * scale},
                    "p2": {"x": item[2].x * scale, "y": item[2].y * scale},
                    "p3": {"x": item[3].x * scale, "y": item[3].y * scale},
                    "p4": {"x": item[4].x * scale, "y": item[4].y * scale}
                })
            elif cmd == "qu":  # quad
                path_items.append({
                    "type": "quad",
                    "points": [
                        {"x": item[1].x * scale, "y": item[1].y * scale}
                        for i in range(1, min(len(item), 5))
                        if hasattr(item[i], 'x')
                    ]
                })

        if path_items:
            stroke_width = path.get("width")
            drawings.append({
                "bbox": {
                    "x": rect.x0 * scale,
                    "y": rect.y0 * scale,
                    "width": rect.width * scale,
                    "height": rect.height * scale
                },
                "items": path_items,
                "fill": path.get("fill"),
                "stroke": path.get("color"),
                "width": (stroke_width or 0) * scale
            })

    return drawings


def calculate_scale_factor(page: fitz.Page, image_width: int = None,
                          image_height: int = None, dpi: int = 300) -> float:
    """
    Calculate scale factor to convert PDF points to image pixels.

    If image dimensions are provided, use them.
    Otherwise, calculate based on DPI (default 300).
    PDF points are 72 per inch.
    """
    page_rect = page.rect

    if image_width and image_height:
        # Use provided image dimensions
        scale_x = image_width / page_rect.width
        scale_y = image_height / page_rect.height
        return (scale_x + scale_y) / 2
    else:
        # Calculate from DPI: points_to_pixels = dpi / 72
        return dpi / 72.0


def extract_page(page: fitz.Page, page_num: int, scale: float) -> dict:
    """Extract all data from a single page."""
    dims = get_page_dimensions(page)

    return {
        "page_number": page_num,
        "dimensions": {
            "width_pts": dims["width_pts"],
            "height_pts": dims["height_pts"],
            "width_px": dims["width_pts"] * scale,
            "height_px": dims["height_pts"] * scale,
            "scale_factor": scale
        },
        "text_blocks": extract_text_blocks(page, scale),
        "drawings": extract_drawings(page, scale)
    }


def extract_pdf_vectors(pdf_path: str, output_path: str = None,
                        pages: list[int] = None, dpi: int = 300,
                        image_width: int = None, image_height: int = None) -> dict:
    """
    Main extraction function.

    Args:
        pdf_path: Path to PDF file
        output_path: Optional path to write JSON output
        pages: Optional list of page numbers (1-indexed) to extract
        dpi: DPI for scale calculation (default 300)
        image_width: Optional image width for scale calculation
        image_height: Optional image height for scale calculation

    Returns:
        Dictionary with extracted data
    """
    pdf_path = Path(pdf_path).expanduser().resolve()

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)

    result = {
        "source": str(pdf_path),
        "total_pages": doc.page_count,
        "dpi": dpi,
        "pages": []
    }

    # Determine which pages to extract
    if pages:
        page_nums = [p for p in pages if 1 <= p <= doc.page_count]
    else:
        page_nums = list(range(1, doc.page_count + 1))

    for page_num in page_nums:
        page = doc[page_num - 1]  # 0-indexed
        scale = calculate_scale_factor(page, image_width, image_height, dpi)
        page_data = extract_page(page, page_num, scale)
        result["pages"].append(page_data)

    doc.close()

    if output_path:
        output_path = Path(output_path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    return result


def parse_page_range(page_arg: str) -> list[int]:
    """Parse page range argument like '1-5,7,10-12'."""
    pages = []
    for part in page_arg.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(part))
    return sorted(set(pages))


def main():
    parser = argparse.ArgumentParser(
        description="Extract text and vector paths from PDF using PyMuPDF"
    )
    parser.add_argument("pdf", help="Path to PDF file")
    parser.add_argument(
        "-o", "--output",
        help="Output JSON file path"
    )
    parser.add_argument(
        "-p", "--pages",
        help="Page range to extract (e.g., '1-5,7,10-12')"
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="DPI for scale calculation (default: 300)"
    )
    parser.add_argument(
        "--image-width",
        type=int,
        help="Image width in pixels for scale calculation"
    )
    parser.add_argument(
        "--image-height",
        type=int,
        help="Image height in pixels for scale calculation"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON to stdout"
    )

    args = parser.parse_args()

    pages = None
    if args.pages:
        pages = parse_page_range(args.pages)

    try:
        result = extract_pdf_vectors(
            args.pdf,
            output_path=args.output,
            pages=pages,
            dpi=args.dpi,
            image_width=args.image_width,
            image_height=args.image_height
        )

        if args.json or not args.output:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"✓ Extracted {len(result['pages'])} pages to {args.output}")
            total_text = sum(len(p['text_blocks']) for p in result['pages'])
            total_drawings = sum(len(p['drawings']) for p in result['pages'])
            print(f"  Text blocks: {total_text}")
            print(f"  Drawings: {total_drawings}")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error processing PDF: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
