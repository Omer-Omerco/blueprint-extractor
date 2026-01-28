#!/usr/bin/env python3
"""
Detect room numbers and names from extracted PDF vectors.
Uses pattern matching and proximity search.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


# Room number patterns
ROOM_PATTERNS = [
    (re.compile(r"^(\d{3})$"), 1.0),                      # 101, 204, etc.
    (re.compile(r"^([A-Z])-?(\d{3})$"), 1.0),             # A-101, B204
    (re.compile(r"^(\d{3}[A-Z])$"), 0.95),                # 101A, 204B
    (re.compile(r"^([A-Z]\d{3}[A-Z]?)$"), 0.95),          # A101, B204A
    (re.compile(r"^(\d{2,4})$"), 0.8),                    # 2-4 digit numbers
]

# Quebec room name patterns
ROOM_NAME_PATTERNS = [
    re.compile(r"^(CLASSE|CLASS)$", re.IGNORECASE),
    re.compile(r"^(CORRIDOR|CORR\.?)$", re.IGNORECASE),
    re.compile(r"^(S\.?D\.?B\.?|SALLE DE BAIN)$", re.IGNORECASE),
    re.compile(r"^(W\.?C\.?|TOILETTE?S?)$", re.IGNORECASE),
    re.compile(r"^(RANG\.?|RANGEMENT)$", re.IGNORECASE),
    re.compile(r"^(MÉC\.?|MÉCANIQUE)$", re.IGNORECASE),
    re.compile(r"^(ÉLEC\.?|ÉLECTRIQUE)$", re.IGNORECASE),
    re.compile(r"^(CONCIERGERIE|CONC\.?)$", re.IGNORECASE),
    re.compile(r"^(BUREAU|BUR\.?)$", re.IGNORECASE),
    re.compile(r"^(SECRÉTARIAT|SECR\.?)$", re.IGNORECASE),
    re.compile(r"^(DIRECTION|DIR\.?)$", re.IGNORECASE),
    re.compile(r"^(VESTIAIRE|VEST\.?)$", re.IGNORECASE),
    re.compile(r"^(CUISINE|CUIS\.?)$", re.IGNORECASE),
    re.compile(r"^(GYMNASE|GYM\.?)$", re.IGNORECASE),
    re.compile(r"^(BIBLIOTHÈQUE|BIBLIO\.?)$", re.IGNORECASE),
    re.compile(r"^(SALLE)$", re.IGNORECASE),
    re.compile(r"^(LOCAL)$", re.IGNORECASE),
    re.compile(r"^(ENTRÉE)$", re.IGNORECASE),
    re.compile(r"^(HALL)$", re.IGNORECASE),
    re.compile(r"^(ESCALIER|ESC\.?)$", re.IGNORECASE),
    re.compile(r"^(ASCENSEUR|ASC\.?)$", re.IGNORECASE),
]


def match_room_number(text: str) -> tuple[str | None, float]:
    """
    Check if text matches a room number pattern.
    Returns (matched_number, confidence) or (None, 0).
    """
    text = text.strip()
    if not text:
        return None, 0.0

    for pattern, confidence in ROOM_PATTERNS:
        match = pattern.match(text)
        if match:
            return text, confidence

    return None, 0.0


def is_room_name(text: str) -> bool:
    """Check if text is a known room name."""
    text = text.strip()
    if not text:
        return False

    for pattern in ROOM_NAME_PATTERNS:
        if pattern.match(text):
            return True

    return False


def calculate_distance(bbox1: dict, bbox2: dict) -> float:
    """Calculate distance between two bbox centers."""
    cx1 = bbox1["x"] + bbox1["width"] / 2
    cy1 = bbox1["y"] + bbox1["height"] / 2
    cx2 = bbox2["x"] + bbox2["width"] / 2
    cy2 = bbox2["y"] + bbox2["height"] / 2

    return math.sqrt((cx2 - cx1) ** 2 + (cy2 - cy1) ** 2)


def find_nearby_name(room_block: dict, text_blocks: list[dict],
                     max_distance: float = 200) -> str | None:
    """
    Find the room name by proximity search.
    Looks for text above or to the left of the room number.
    """
    room_bbox = room_block["bbox"]
    room_cx = room_bbox["x"] + room_bbox["width"] / 2
    room_cy = room_bbox["y"] + room_bbox["height"] / 2

    candidates = []

    for block in text_blocks:
        if block["text"] == room_block["text"]:
            continue

        if not is_room_name(block["text"]):
            continue

        block_bbox = block["bbox"]
        block_cx = block_bbox["x"] + block_bbox["width"] / 2
        block_cy = block_bbox["y"] + block_bbox["height"] / 2

        # Prefer text that is above or to the left
        # Above: block_cy < room_cy
        # Left: block_cx < room_cx

        distance = calculate_distance(room_bbox, block_bbox)

        if distance > max_distance:
            continue

        # Calculate direction preference score
        # Prefer above, then left
        direction_score = 0
        if block_cy < room_cy:  # Above
            direction_score += 2
        if block_cx < room_cx:  # Left
            direction_score += 1

        # Combined score: lower distance is better, higher direction score is better
        score = distance - (direction_score * 50)

        candidates.append({
            "text": block["text"],
            "distance": distance,
            "direction_score": direction_score,
            "score": score
        })

    if not candidates:
        return None

    # Sort by score (lower is better)
    candidates.sort(key=lambda x: x["score"])
    return candidates[0]["text"]


def calculate_expanded_bbox(room_block: dict, name_block: dict | None = None,
                           padding: float = 20) -> dict:
    """
    Calculate an expanded bbox that includes both room number and name.
    """
    room_bbox = room_block["bbox"]

    if name_block:
        name_bbox = name_block["bbox"]
        x_min = min(room_bbox["x"], name_bbox["x"]) - padding
        y_min = min(room_bbox["y"], name_bbox["y"]) - padding
        x_max = max(room_bbox["x"] + room_bbox["width"],
                   name_bbox["x"] + name_bbox["width"]) + padding
        y_max = max(room_bbox["y"] + room_bbox["height"],
                   name_bbox["y"] + name_bbox["height"]) + padding
    else:
        x_min = room_bbox["x"] - padding
        y_min = room_bbox["y"] - padding
        x_max = room_bbox["x"] + room_bbox["width"] + padding
        y_max = room_bbox["y"] + room_bbox["height"] + padding

    return {
        "x": max(0, x_min),
        "y": max(0, y_min),
        "width": x_max - x_min,
        "height": y_max - y_min
    }


def detect_rooms_in_page(page_data: dict, max_distance: float = 200) -> list[dict]:
    """
    Detect rooms in a single page.

    Args:
        page_data: Page data from extract_pdf_vectors
        max_distance: Maximum distance to search for room names

    Returns:
        List of detected rooms
    """
    text_blocks = page_data.get("text_blocks", [])
    rooms = []

    for block in text_blocks:
        text = block.get("text", "")
        room_number, confidence = match_room_number(text)

        if not room_number:
            continue

        # Find nearby room name
        room_name = find_nearby_name(block, text_blocks, max_distance)

        # Find the name block for bbox calculation
        name_block = None
        if room_name:
            for b in text_blocks:
                if b["text"] == room_name:
                    name_block = b
                    break

        # Calculate expanded bbox
        expanded_bbox = calculate_expanded_bbox(block, name_block)

        rooms.append({
            "number": room_number,
            "name": room_name,
            "confidence": confidence,
            "bbox": expanded_bbox,
            "number_bbox": block["bbox"],
            "name_bbox": name_block["bbox"] if name_block else None,
            "page": page_data.get("page_number")
        })

    return rooms


def detect_rooms(vectors_data: dict, max_distance: float = 200) -> dict:
    """
    Detect rooms in all pages.

    Args:
        vectors_data: Output from extract_pdf_vectors
        max_distance: Maximum distance to search for room names

    Returns:
        Dictionary with detected rooms
    """
    result = {
        "source": vectors_data.get("source"),
        "total_pages": vectors_data.get("total_pages"),
        "rooms": [],
        "stats": {
            "total_rooms": 0,
            "with_names": 0,
            "by_page": {}
        }
    }

    for page_data in vectors_data.get("pages", []):
        page_num = page_data.get("page_number")
        page_rooms = detect_rooms_in_page(page_data, max_distance)

        for room in page_rooms:
            result["rooms"].append(room)

        result["stats"]["by_page"][str(page_num)] = len(page_rooms)

    result["stats"]["total_rooms"] = len(result["rooms"])
    result["stats"]["with_names"] = sum(1 for r in result["rooms"] if r["name"])

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Detect room numbers and names from extracted PDF vectors"
    )
    parser.add_argument("vectors_json", help="Path to vectors JSON from extract_pdf_vectors")
    parser.add_argument(
        "-o", "--output",
        help="Output JSON file path"
    )
    parser.add_argument(
        "--max-distance",
        type=float,
        default=200,
        help="Maximum distance to search for room names (default: 200 pixels)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON to stdout"
    )

    args = parser.parse_args()

    vectors_path = Path(args.vectors_json).expanduser().resolve()

    if not vectors_path.exists():
        print(f"Error: File not found: {vectors_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(vectors_path, "r", encoding="utf-8") as f:
            vectors_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    result = detect_rooms(vectors_data, max_distance=args.max_distance)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"✓ Detected {result['stats']['total_rooms']} rooms")
        print(f"  With names: {result['stats']['with_names']}")
        print(f"  Output: {output_path}")

    if args.json or not args.output:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
