#!/usr/bin/env python3
"""
Dimension detector for blueprint vector data.
Detects dimension annotations in Quebec feet-inches format.

Supported formats:
- Standard: 25'-6"
- With fraction: 12'-6 5/8"
- Inches only: 6"
- Feet only: 25'
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional, Tuple


# Regex patterns for Quebec feet-inches dimensions
DIMENSION_PATTERNS = [
    # Full format: 25'-6 5/8" (feet, inches, fraction)
    r"(\d+)'\s*-?\s*(\d+)\s+(\d+)/(\d+)\"",

    # Standard format: 25'-6" (feet and inches)
    r"(\d+)'\s*-?\s*(\d+)\"",

    # Feet only: 25'-0" or 25'
    r"(\d+)'\s*-?\s*0\"",
    r"(\d+)'(?!\s*-?\s*\d)",

    # Inches with fraction: 6 5/8"
    r"(\d+)\s+(\d+)/(\d+)\"",

    # Inches only: 6"
    r"(\d+)\"",
]


def parse_dimension(text: str) -> Optional[Tuple[str, float]]:
    """
    Parse a dimension text into value and total inches.

    Args:
        text: Dimension text (e.g., "25'-6\"", "12'-6 5/8\"")

    Returns:
        Tuple of (original_text, value_inches) or None if not a dimension
    """
    text = text.strip()

    # Full format: 25'-6 5/8"
    match = re.match(r"(\d+)'\s*-?\s*(\d+)\s+(\d+)/(\d+)\"", text)
    if match:
        feet = int(match.group(1))
        inches = int(match.group(2))
        frac_num = int(match.group(3))
        frac_den = int(match.group(4))
        total_inches = feet * 12 + inches + (frac_num / frac_den if frac_den > 0 else 0)
        return (text, total_inches)

    # Standard format: 25'-6"
    match = re.match(r"(\d+)'\s*-?\s*(\d+)\"", text)
    if match:
        feet = int(match.group(1))
        inches = int(match.group(2))
        total_inches = feet * 12 + inches
        return (text, total_inches)

    # Feet only with -0": 25'-0"
    match = re.match(r"(\d+)'\s*-?\s*0\"$", text)
    if match:
        feet = int(match.group(1))
        return (text, feet * 12)

    # Feet only: 25'
    match = re.match(r"(\d+)'$", text)
    if match:
        feet = int(match.group(1))
        return (text, feet * 12)

    # Inches with fraction: 6 5/8"
    match = re.match(r"(\d+)\s+(\d+)/(\d+)\"$", text)
    if match:
        inches = int(match.group(1))
        frac_num = int(match.group(2))
        frac_den = int(match.group(3))
        total_inches = inches + (frac_num / frac_den if frac_den > 0 else 0)
        return (text, total_inches)

    # Inches only: 6"
    match = re.match(r"(\d+)\"$", text)
    if match:
        inches = int(match.group(1))
        return (text, inches)

    return None


def is_dimension_text(text: str) -> bool:
    """
    Check if text looks like a dimension.

    Args:
        text: Text to check

    Returns:
        True if text matches dimension pattern
    """
    text = text.strip()

    for pattern in DIMENSION_PATTERNS:
        if re.match(pattern + r"$", text):
            return True

    return False


def extract_dimensions_from_text(text: str) -> list:
    """
    Extract all dimensions from a text string.

    Args:
        text: Text that may contain multiple dimensions

    Returns:
        List of (match_text, value_inches) tuples
    """
    results = []

    # Try each pattern
    patterns_with_groups = [
        # Full format: 25'-6 5/8"
        (r"(\d+)'\s*-?\s*(\d+)\s+(\d+)/(\d+)\"", "feet_inches_fraction"),
        # Standard format: 25'-6"
        (r"(\d+)'\s*-?\s*(\d+)\"", "feet_inches"),
        # Feet only: 25'-0"
        (r"(\d+)'\s*-?\s*0\"", "feet_zero"),
        # Feet only: 25'
        (r"(\d+)'(?!\s*-?\s*\d)", "feet_only"),
        # Inches with fraction: 6 5/8"
        (r"(\d+)\s+(\d+)/(\d+)\"", "inches_fraction"),
        # Inches only: 6"
        (r"(\d+)\"", "inches_only"),
    ]

    for pattern, ptype in patterns_with_groups:
        for match in re.finditer(pattern, text):
            match_text = match.group(0)

            if ptype == "feet_inches_fraction":
                feet = int(match.group(1))
                inches = int(match.group(2))
                frac_num = int(match.group(3))
                frac_den = int(match.group(4))
                value = feet * 12 + inches + (frac_num / frac_den if frac_den > 0 else 0)
            elif ptype == "feet_inches":
                feet = int(match.group(1))
                inches = int(match.group(2))
                value = feet * 12 + inches
            elif ptype == "feet_zero":
                feet = int(match.group(1))
                value = feet * 12
            elif ptype == "feet_only":
                feet = int(match.group(1))
                value = feet * 12
            elif ptype == "inches_fraction":
                inches = int(match.group(1))
                frac_num = int(match.group(2))
                frac_den = int(match.group(3))
                value = inches + (frac_num / frac_den if frac_den > 0 else 0)
            elif ptype == "inches_only":
                inches = int(match.group(1))
                value = inches
            else:
                continue

            results.append({
                "text": match_text,
                "value_inches": value,
                "start": match.start(),
                "end": match.end()
            })

    # Remove duplicates (overlapping matches) - keep longer matches
    results.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))
    filtered = []
    last_end = -1
    for r in results:
        if r["start"] >= last_end:
            filtered.append(r)
            last_end = r["end"]

    return filtered


def detect_dimensions(vectors: dict) -> list:
    """
    Detect dimensions from vector data.

    Args:
        vectors: Dict from extract_pdf_vectors (text_blocks[] or texts[])

    Returns:
        List of detected dimensions
    """
    dimensions = []
    
    # Support both new format (text_blocks) and old format (texts)
    texts = vectors.get("text_blocks", []) or vectors.get("texts", [])

    dim_id = 0
    seen_texts = set()  # Avoid duplicates

    for text_elem in texts:
        content = text_elem.get("text", "").strip()

        if not content:
            continue

        # Skip if we've seen this exact text at similar position
        bbox = text_elem.get("bbox", {})
        # Handle both bbox formats: {x, y} and {x0, y0}
        x_pos = bbox.get('x', bbox.get('x0', 0))
        y_pos = bbox.get('y', bbox.get('y0', 0))
        pos_key = f"{content}_{int(x_pos)}_{int(y_pos)}"
        if pos_key in seen_texts:
            continue
        seen_texts.add(pos_key)

        # Check if entire text is a dimension
        parsed = parse_dimension(content)
        if parsed:
            dim_id += 1
            value_text, value_inches = parsed

            dimensions.append({
                "id": f"dim-{dim_id:03d}",
                "value_text": value_text,
                "value_inches": round(value_inches, 3),
                "bbox": bbox,
                "confidence": calculate_confidence(content, bbox),
                "page": vectors.get("page", 1)
            })
        else:
            # Check for embedded dimensions in longer text
            extracted = extract_dimensions_from_text(content)
            for ext in extracted:
                dim_id += 1
                dimensions.append({
                    "id": f"dim-{dim_id:03d}",
                    "value_text": ext["text"],
                    "value_inches": round(ext["value_inches"], 3),
                    "bbox": bbox,  # Use parent text bbox
                    "confidence": calculate_confidence(ext["text"], bbox) * 0.9,  # Slightly lower for embedded
                    "page": vectors.get("page", 1)
                })

    return dimensions


def calculate_confidence(text: str, bbox: dict) -> float:
    """
    Calculate confidence score for dimension detection.

    Args:
        text: The dimension text
        bbox: Bounding box of the text

    Returns:
        Confidence score 0.0-1.0
    """
    score = 0.7  # Base score for pattern match

    # Standard format boost
    if re.match(r"^\d+'\s*-\s*\d+\"$", text):
        score += 0.15
    elif re.match(r"^\d+'\s*-\s*\d+\s+\d+/\d+\"$", text):
        score += 0.15  # Fraction format also good

    # Reasonable values boost (typical architectural dimensions)
    parsed = parse_dimension(text)
    if parsed:
        _, inches = parsed
        # Typical room dimensions are 6" to 100' (1200")
        if 6 <= inches <= 1200:
            score += 0.1
        # Very common dimensions
        if inches in [96, 144, 120, 180, 240, 360]:  # 8', 12', 10', 15', 20', 30'
            score += 0.05

    return min(1.0, score)


def run_detection(input_path: str, output_path: Optional[str] = None) -> dict:
    """
    Run dimension detection on vector data file.

    Args:
        input_path: Path to vectors JSON file
        output_path: Optional output path for results

    Returns:
        Detection results dict
    """
    input_path = Path(input_path).expanduser().resolve()

    with open(input_path) as f:
        vectors = json.load(f)

    # Handle multiple pages
    if "pages" in vectors:
        all_dimensions = []
        for page_data in vectors["pages"]:
            page_dims = detect_dimensions(page_data)
            all_dimensions.extend(page_dims)
    else:
        all_dimensions = detect_dimensions(vectors)

    results = {
        "source": str(input_path),
        "total_dimensions": len(all_dimensions),
        "dimensions": all_dimensions
    }

    if output_path:
        output_path = Path(output_path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Detected {len(all_dimensions)} dimensions -> {output_path}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Detect dimensions from PDF vector data"
    )
    parser.add_argument(
        "input",
        help="Path to vectors.json from extract_pdf_vectors"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output path for dimensions.json"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON to stdout"
    )

    args = parser.parse_args()

    results = run_detection(args.input, args.output)

    if args.json:
        print(json.dumps(results, indent=2))
    elif not args.output:
        # Print summary if no output file specified
        print(f"Detected {results['total_dimensions']} dimensions:")
        for dim in results["dimensions"]:
            print(f"  {dim['id']}: {dim['value_text']} = {dim['value_inches']}\" (conf: {dim['confidence']})")


if __name__ == "__main__":
    main()
