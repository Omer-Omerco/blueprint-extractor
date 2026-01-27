#!/usr/bin/env python3
"""
Extract pages from a PDF as high-resolution images.
Uses pdftoppm (poppler) for quality extraction.
"""

import argparse
import subprocess
import sys
from pathlib import Path
import json


def get_page_count(pdf_path: Path) -> int:
    """Get the number of pages in a PDF."""
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        capture_output=True,
        text=True
    )
    
    for line in result.stdout.split("\n"):
        if line.startswith("Pages:"):
            return int(line.split(":")[1].strip())
    return 0


def extract_single_page(pdf_path: Path, output_dir: Path, page_num: int, dpi: int) -> Path | None:
    """Extract a single page from PDF."""
    output_file = output_dir / f"page-{page_num:03d}"
    
    cmd = [
        "pdftoppm",
        "-png",
        "-r", str(dpi),
        "-f", str(page_num),
        "-l", str(page_num),
        str(pdf_path),
        str(output_file)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        return None
    
    # pdftoppm adds page number suffix
    expected = output_dir / f"page-{page_num:03d}-{page_num}.png"
    target = output_dir / f"page-{page_num:03d}.png"
    
    if expected.exists():
        expected.rename(target)
        return target
    
    # Try alternative naming
    for f in output_dir.glob(f"page-{page_num:03d}*.png"):
        f.rename(target)
        return target
    
    return None


def extract_pages(pdf_path: str, output_dir: str, dpi: int = 300) -> dict:
    """Extract PDF pages to PNG images using pdftoppm."""
    
    pdf_path = Path(pdf_path).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    page_count = get_page_count(pdf_path)
    
    if page_count == 0:
        print("Error: Could not determine page count", file=sys.stderr)
        sys.exit(1)
    
    print(f"Extracting {page_count} pages at {dpi} DPI...")
    
    extracted = []
    failed = []
    
    for page_num in range(1, page_count + 1):
        print(f"  [{page_num}/{page_count}]", end=" ", flush=True)
        
        result = extract_single_page(pdf_path, output_dir, page_num, dpi)
        
        if result and result.exists():
            extracted.append({
                "number": page_num,
                "filename": result.name,
                "path": str(result)
            })
            print("✓")
        else:
            failed.append(page_num)
            print("✗")
    
    # Create manifest
    manifest = {
        "source_pdf": str(pdf_path),
        "page_count": len(extracted),
        "total_pages": page_count,
        "dpi": dpi,
        "pages": extracted,
        "failed_pages": failed
    }
    
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n✓ Extracted {len(extracted)}/{page_count} pages to {output_dir}")
    if failed:
        print(f"⚠️  Failed pages: {failed}")
    print(f"✓ Manifest: {manifest_path}")
    
    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Extract PDF pages as high-resolution images"
    )
    parser.add_argument("pdf", help="Path to PDF file")
    parser.add_argument(
        "-o", "--output",
        default="./pages",
        help="Output directory (default: ./pages)"
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Resolution in DPI (default: 300)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output manifest as JSON to stdout"
    )
    
    args = parser.parse_args()
    
    manifest = extract_pages(args.pdf, args.output, args.dpi)
    
    if args.json:
        print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
