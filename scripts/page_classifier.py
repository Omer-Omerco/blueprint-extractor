#!/usr/bin/env python3
"""
Classify pages from a blueprint PDF by type (LEGEND, PLAN, DETAIL, ELEVATION, OTHER).
Uses token scoring based on keyword matching.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Literal

PageType = Literal["LEGEND", "PLAN", "DETAIL", "ELEVATION", "OTHER"]

# Keywords and their weights for each page type
KEYWORDS: dict[PageType, dict[str, int]] = {
    "LEGEND": {
        "légende": 10,
        "legend": 10,
        "symboles": 8,
        "symbols": 8,
        "nomenclature": 6,
        "abréviations": 5,
        "abbreviations": 5,
    },
    "PLAN": {
        "étage": 8,
        "etage": 8,
        "niveau": 8,
        "floor": 8,
        "level": 7,
        "sous-sol": 6,
        "rez-de-chaussée": 6,
        "rdc": 5,
        "mezzanine": 5,
        "toiture": 4,
        "roof": 4,
    },
    "DETAIL": {
        "détail": 10,
        "detail": 10,
        "coupe": 8,
        "section": 8,
        "assemblage": 6,
        "assembly": 6,
        "agrandissement": 5,
        "enlargement": 5,
    },
    "ELEVATION": {
        "élévation": 10,
        "elevation": 10,
        "façade": 8,
        "facade": 8,
        "vue": 4,
        "view": 4,
        "nord": 3,
        "sud": 3,
        "est": 3,
        "ouest": 3,
    },
}

# Pattern for 3-digit room numbers (strong indicator of PLAN pages)
ROOM_NUMBER_PATTERN = re.compile(r"\b[1-9]\d{2}\b")
ROOM_NUMBER_WEIGHT = 2  # Weight per room number found (capped)
ROOM_NUMBER_MAX_SCORE = 20  # Cap the room number contribution


def get_page_count(pdf_path: Path) -> int:
    """Get the number of pages in a PDF using pdfinfo."""
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        capture_output=True,
        text=True
    )

    for line in result.stdout.split("\n"):
        if line.startswith("Pages:"):
            return int(line.split(":")[1].strip())
    return 0


def extract_page_text(pdf_path: Path, page_num: int) -> str:
    """Extract text from a single PDF page using pdftotext."""
    result = subprocess.run(
        ["pdftotext", "-f", str(page_num), "-l", str(page_num), str(pdf_path), "-"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return ""

    return result.stdout


def compute_scores(text: str) -> dict[PageType, int]:
    """Compute keyword scores for each page type."""
    text_lower = text.lower()
    scores: dict[PageType, int] = {
        "LEGEND": 0,
        "PLAN": 0,
        "DETAIL": 0,
        "ELEVATION": 0,
        "OTHER": 0,
    }

    for page_type, keywords in KEYWORDS.items():
        for keyword, weight in keywords.items():
            count = text_lower.count(keyword)
            scores[page_type] += count * weight

    # Add room number contribution to PLAN score
    room_numbers = ROOM_NUMBER_PATTERN.findall(text)
    room_score = min(len(room_numbers) * ROOM_NUMBER_WEIGHT, ROOM_NUMBER_MAX_SCORE)
    scores["PLAN"] += room_score

    return scores


def classify_page(text: str) -> tuple[PageType, dict[PageType, int]]:
    """Classify a page based on its text content."""
    scores = compute_scores(text)

    # Find the type with the highest score
    max_score = 0
    best_type: PageType = "OTHER"

    for page_type in ["LEGEND", "PLAN", "DETAIL", "ELEVATION"]:
        if scores[page_type] > max_score:
            max_score = scores[page_type]
            best_type = page_type

    return best_type, scores


def classify_pdf(pdf_path: str, verbose: bool = False) -> dict:
    """Classify all pages in a PDF."""
    pdf_path = Path(pdf_path).expanduser().resolve()

    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    page_count = get_page_count(pdf_path)

    if page_count == 0:
        print("Error: Could not determine page count", file=sys.stderr)
        sys.exit(1)

    if verbose:
        print(f"Classifying {page_count} pages...")

    pages = []
    type_counts: dict[PageType, int] = {
        "LEGEND": 0,
        "PLAN": 0,
        "DETAIL": 0,
        "ELEVATION": 0,
        "OTHER": 0,
    }

    for page_num in range(1, page_count + 1):
        if verbose:
            print(f"  [{page_num}/{page_count}]", end=" ", flush=True)

        text = extract_page_text(pdf_path, page_num)
        page_type, scores = classify_page(text)

        pages.append({
            "page": page_num,
            "type": page_type,
            "scores": scores,
        })

        type_counts[page_type] += 1

        if verbose:
            print(f"{page_type}")

    result = {
        "source_pdf": str(pdf_path),
        "page_count": page_count,
        "summary": type_counts,
        "pages": pages,
    }

    if verbose:
        print(f"\nSummary: {type_counts}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Classify PDF pages by type (LEGEND, PLAN, DETAIL, ELEVATION, OTHER)"
    )
    parser.add_argument("pdf", help="Path to PDF file")
    parser.add_argument(
        "-o", "--output",
        help="Output JSON file (default: stdout)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show progress"
    )

    args = parser.parse_args()

    result = classify_pdf(args.pdf, verbose=args.verbose)

    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_json)
        if args.verbose:
            print(f"\nOutput saved to: {output_path}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
