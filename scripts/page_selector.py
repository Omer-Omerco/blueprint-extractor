#!/usr/bin/env python3
"""
Select the best pages for blueprint analysis.
Prioritizes LEGEND pages and diversified PLAN pages.
"""

import argparse
import json
import sys
from pathlib import Path


def load_page_types(input_path: str) -> dict:
    """Load page classification results."""
    path = Path(input_path).expanduser().resolve()

    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def select_pages(page_types: dict, n: int = 5) -> dict:
    """
    Select the best pages for analysis.

    Strategy:
    1. Take 1 LEGEND page (if available) - highest scoring
    2. Take PLAN pages (diversified by score, up to n-1 or n if no LEGEND)
    3. Fallback: fill with first pages if not enough PLAN pages
    """
    pages = page_types.get("pages", [])

    if not pages:
        return {
            "source_pdf": page_types.get("source_pdf", ""),
            "selection_count": 0,
            "strategy": "empty - no pages to select",
            "selected": [],
        }

    # Group pages by type
    legend_pages = [p for p in pages if p["type"] == "LEGEND"]
    plan_pages = [p for p in pages if p["type"] == "PLAN"]
    other_pages = [p for p in pages if p["type"] not in ("LEGEND", "PLAN")]

    # Sort by score (highest first)
    legend_pages.sort(key=lambda p: p["scores"].get("LEGEND", 0), reverse=True)
    plan_pages.sort(key=lambda p: p["scores"].get("PLAN", 0), reverse=True)

    selected = []
    strategy_parts = []

    # 1. Take best LEGEND page (if available)
    if legend_pages:
        selected.append(legend_pages[0])
        strategy_parts.append("1 LEGEND")
        remaining_slots = n - 1
    else:
        strategy_parts.append("0 LEGEND (none found)")
        remaining_slots = n

    # 2. Take diversified PLAN pages
    if plan_pages:
        # Take up to remaining_slots PLAN pages, diversified
        plans_to_take = min(len(plan_pages), remaining_slots)

        if plans_to_take > 0:
            # Select diversified plans: best score, then spread across the list
            if len(plan_pages) <= plans_to_take:
                selected.extend(plan_pages)
            else:
                # Take best, then evenly spaced others
                indices = _diversify_indices(len(plan_pages), plans_to_take)
                selected.extend(plan_pages[i] for i in indices)

            strategy_parts.append(f"{plans_to_take} PLAN")
            remaining_slots -= plans_to_take
    else:
        strategy_parts.append("0 PLAN (none found)")

    # 3. Fallback: fill with first pages (by page number)
    if remaining_slots > 0:
        # Get pages not already selected
        selected_page_nums = {p["page"] for p in selected}
        fallback_pages = [p for p in pages if p["page"] not in selected_page_nums]
        fallback_pages.sort(key=lambda p: p["page"])  # Sort by page number

        fallback_to_take = min(len(fallback_pages), remaining_slots)
        if fallback_to_take > 0:
            selected.extend(fallback_pages[:fallback_to_take])
            strategy_parts.append(f"{fallback_to_take} FALLBACK")

    # Sort final selection by page number
    selected.sort(key=lambda p: p["page"])

    return {
        "source_pdf": page_types.get("source_pdf", ""),
        "selection_count": len(selected),
        "requested_count": n,
        "strategy": " + ".join(strategy_parts),
        "selected": [
            {
                "page": p["page"],
                "type": p["type"],
                "score": p["scores"].get(p["type"], 0),
            }
            for p in selected
        ],
    }


def _diversify_indices(total: int, count: int) -> list[int]:
    """
    Select diversified indices from a range.
    Always includes first (best), then spreads evenly.
    """
    if count <= 0:
        return []
    if count >= total:
        return list(range(total))
    if count == 1:
        return [0]

    # Always include the first (best score)
    indices = [0]

    # Spread the rest evenly
    step = (total - 1) / (count - 1)
    for i in range(1, count):
        idx = int(round(i * step))
        if idx not in indices:
            indices.append(idx)

    # If we missed some due to rounding, fill with sequential
    while len(indices) < count:
        for i in range(total):
            if i not in indices:
                indices.append(i)
                break

    return sorted(indices)


def main():
    parser = argparse.ArgumentParser(
        description="Select the best pages for blueprint analysis"
    )
    parser.add_argument(
        "page_types",
        help="Path to page_types.json from page_classifier.py"
    )
    parser.add_argument(
        "-n", "--count",
        type=int,
        default=5,
        help="Number of pages to select (default: 5)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output JSON file (default: stdout)"
    )

    args = parser.parse_args()

    page_types = load_page_types(args.page_types)
    result = select_pages(page_types, n=args.count)

    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Selected {result['selection_count']} pages -> {output_path}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
