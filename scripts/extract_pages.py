#!/usr/bin/env python3
"""
Extract pages from a PDF as high-resolution images.
Uses pdftoppm (poppler) for quality extraction.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
import json


def get_page_count(pdf_path: Path) -> int:
    """Get total page count from PDF."""
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        capture_output=True,
        text=True
    )
    
    for line in result.stdout.split("\n"):
        if line.startswith("Pages:"):
            return int(line.split(":")[1].strip())
    return 0


def parse_page_range(page_spec: str, total_pages: int) -> list[int]:
    """Parse page specification like '1-5', '1,3,5', or '1-3,7-9'."""
    if not page_spec:
        return list(range(1, total_pages + 1))
    
    pages = set()
    for part in page_spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start = int(start) if start else 1
            end = int(end) if end else total_pages
            pages.update(range(start, min(end, total_pages) + 1))
        else:
            page = int(part)
            if 1 <= page <= total_pages:
                pages.add(page)
    
    return sorted(pages)


def extract_pages(
    pdf_path: str,
    output_dir: str,
    dpi: int = 300,
    pages: str = None,
    verbose: bool = True
) -> dict:
    """Extract PDF pages to PNG images using pdftoppm."""
    
    pdf_path = Path(pdf_path).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    
    if not pdf_path.exists():
        print(f"❌ Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get page count
    total_pages = get_page_count(pdf_path)
    if total_pages == 0:
        print("❌ Error: Could not determine page count", file=sys.stderr)
        sys.exit(1)
    
    # Parse page range
    page_list = parse_page_range(pages, total_pages)
    
    if verbose:
        print(f"📄 Source: {pdf_path.name}")
        print(f"📊 Total pages in PDF: {total_pages}")
        print(f"🎯 Pages to extract: {len(page_list)} ({page_list[0]}-{page_list[-1]})")
        print(f"🔍 Resolution: {dpi} DPI")
        print(f"📁 Output: {output_dir}")
        print("-" * 50)
    
    extracted = []
    start_time = time.time()
    
    for i, page_num in enumerate(page_list):
        page_start = time.time()
        
        # Output filename with zero-padded number
        output_file = output_dir / f"page-{page_num:03d}.png"
        
        # Extract single page with pdftoppm
        cmd = [
            "pdftoppm",
            "-png",
            "-r", str(dpi),
            "-f", str(page_num),
            "-l", str(page_num),
            "-singlefile",
            str(pdf_path),
            str(output_dir / f"page-{page_num:03d}")
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Failed page {page_num}: {result.stderr}", file=sys.stderr)
            continue
        
        # Check if file was created
        if output_file.exists():
            file_size = output_file.stat().st_size
            page_time = time.time() - page_start
            
            extracted.append({
                "number": page_num,
                "filename": output_file.name,
                "path": str(output_file),
                "size_bytes": file_size
            })
            
            if verbose:
                progress = (i + 1) / len(page_list) * 100
                size_mb = file_size / (1024 * 1024)
                print(f"  [{progress:5.1f}%] Page {page_num:3d} → {output_file.name} ({size_mb:.1f}MB, {page_time:.1f}s)")
        else:
            print(f"⚠️  Warning: Page {page_num} not created", file=sys.stderr)
    
    total_time = time.time() - start_time
    total_size = sum(p["size_bytes"] for p in extracted)
    
    # Create manifest
    manifest = {
        "source_pdf": str(pdf_path),
        "source_name": pdf_path.name,
        "total_pages_in_pdf": total_pages,
        "extracted_count": len(extracted),
        "dpi": dpi,
        "total_size_bytes": total_size,
        "extraction_time_seconds": round(total_time, 1),
        "pages": extracted
    }
    
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    if verbose:
        print("-" * 50)
        print(f"✅ Extracted {len(extracted)}/{len(page_list)} pages")
        print(f"📦 Total size: {total_size / (1024*1024):.1f} MB")
        print(f"⏱️  Time: {total_time:.1f}s ({total_time/len(page_list):.1f}s/page)")
        print(f"📋 Manifest: {manifest_path}")
    
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
        "-p", "--pages",
        help="Page range to extract (e.g., '1-5', '1,3,5', '1-3,7-9')"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output manifest as JSON to stdout"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress output"
    )
    
    args = parser.parse_args()
    
    manifest = extract_pages(
        args.pdf,
        args.output,
        dpi=args.dpi,
        pages=args.pages,
        verbose=not args.quiet
    )
    
    if args.json:
        print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
