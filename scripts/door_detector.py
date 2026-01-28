#!/usr/bin/env python3
"""
Door detector for blueprint vector data.
Detects doors by analyzing arc patterns (curves) in PDF vector paths.
A door typically consists of an arc (~90°) + a line representing the door swing.
"""

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Optional


def calculate_arc_angle(curve: dict) -> float:
    """
    Calculate the angle of an arc from a bezier curve.
    For a door swing arc, this is typically ~90°.

    Args:
        curve: Dict with start, control1, control2, end points

    Returns:
        Angle in degrees
    """
    start = curve.get("start", {})
    end = curve.get("end", {})

    # Calculate center approximation from endpoints
    # For door arcs, the center is typically at the hinge point
    sx, sy = start.get("x", 0), start.get("y", 0)
    ex, ey = end.get("x", 0), end.get("y", 0)

    # Vector from start to end
    dx = ex - sx
    dy = ey - sy

    # Calculate angle between start and end vectors from origin approximation
    # For a quarter circle arc, this gives ~90°
    if "center" in curve:
        cx, cy = curve["center"].get("x", 0), curve["center"].get("y", 0)
        # Vectors from center to start and end
        v1x, v1y = sx - cx, sy - cy
        v2x, v2y = ex - cx, ey - cy

        dot = v1x * v2x + v1y * v2y
        mag1 = math.sqrt(v1x**2 + v1y**2)
        mag2 = math.sqrt(v2x**2 + v2y**2)

        if mag1 > 0 and mag2 > 0:
            cos_angle = max(-1, min(1, dot / (mag1 * mag2)))
            return math.degrees(math.acos(cos_angle))

    # Fallback: estimate from bezier control points
    if "control1" in curve and "control2" in curve:
        c1 = curve["control1"]
        c2 = curve["control2"]

        # For a ~90° arc, the control points form a specific pattern
        # Approximate radius from chord length
        chord = math.sqrt(dx**2 + dy**2)

        # Control point distances suggest arc curvature
        c1x, c1y = c1.get("x", 0), c1.get("y", 0)
        c2x, c2y = c2.get("x", 0), c2.get("y", 0)

        # Heuristic: for 90° bezier, control points are ~0.552 * radius from endpoints
        ctrl_dist1 = math.sqrt((c1x - sx)**2 + (c1y - sy)**2)
        ctrl_dist2 = math.sqrt((c2x - ex)**2 + (c2y - ey)**2)
        avg_ctrl_dist = (ctrl_dist1 + ctrl_dist2) / 2

        # For 90° arc: chord = radius * sqrt(2), ctrl_dist ≈ 0.552 * radius
        if chord > 0:
            estimated_radius = chord / math.sqrt(2)
            if estimated_radius > 0:
                ratio = avg_ctrl_dist / estimated_radius
                # ratio ~0.552 → 90°, lower → smaller angle
                if ratio > 0.4 and ratio < 0.7:
                    return 90.0
                elif ratio > 0.2 and ratio <= 0.4:
                    return 45.0
                elif ratio >= 0.7:
                    return 120.0

    # Default fallback based on chord length heuristic
    chord = math.sqrt(dx**2 + dy**2)
    if chord > 0:
        return 90.0  # Default assumption for door arcs

    return 0.0


def calculate_arc_radius(curve: dict) -> float:
    """
    Calculate the radius of an arc (door width estimate).

    Args:
        curve: Dict with curve points

    Returns:
        Estimated radius in document units
    """
    start = curve.get("start", {})
    end = curve.get("end", {})

    sx, sy = start.get("x", 0), start.get("y", 0)
    ex, ey = end.get("x", 0), end.get("y", 0)

    # Chord length
    chord = math.sqrt((ex - sx)**2 + (ey - sy)**2)

    # For 90° arc: chord = radius * sqrt(2)
    return chord / math.sqrt(2)


def determine_swing_direction(curve: dict, line: Optional[dict] = None) -> str:
    """
    Determine door swing direction (left/right).
    Based on the arc orientation and any associated line.

    Args:
        curve: The arc curve data
        line: Optional associated line segment

    Returns:
        "left", "right", or "unknown"
    """
    start = curve.get("start", {})
    end = curve.get("end", {})

    sx, sy = start.get("x", 0), start.get("y", 0)
    ex, ey = end.get("x", 0), end.get("y", 0)

    # Check control points to determine arc direction
    if "control1" in curve and "control2" in curve:
        c1 = curve["control1"]
        c2 = curve["control2"]
        c1x, c1y = c1.get("x", 0), c1.get("y", 0)

        # Cross product to determine which side the arc curves to
        # Vector from start to end
        dx = ex - sx
        dy = ey - sy

        # Vector from start to control1
        dcx = c1x - sx
        dcy = c1y - sy

        cross = dx * dcy - dy * dcx

        if cross > 0:
            return "left"
        elif cross < 0:
            return "right"

    return "unknown"


def find_nearby_line(curve: dict, lines: list, tolerance: float = 5.0) -> Optional[dict]:
    """
    Find a line segment near the arc that could be the door frame.

    Args:
        curve: The arc curve
        lines: List of line segments
        tolerance: Distance tolerance for matching

    Returns:
        Matching line or None
    """
    start = curve.get("start", {})
    end = curve.get("end", {})

    arc_points = [
        (start.get("x", 0), start.get("y", 0)),
        (end.get("x", 0), end.get("y", 0))
    ]

    for line in lines:
        line_start = line.get("start", {})
        line_end = line.get("end", {})

        line_points = [
            (line_start.get("x", 0), line_start.get("y", 0)),
            (line_end.get("x", 0), line_end.get("y", 0))
        ]

        # Check if any arc endpoint is near any line endpoint
        for ax, ay in arc_points:
            for lx, ly in line_points:
                dist = math.sqrt((ax - lx)**2 + (ay - ly)**2)
                if dist < tolerance:
                    return line

    return None


def find_nearby_door_number(curve: dict, texts: list, max_distance: float = 50.0) -> Optional[str]:
    """
    Find door number text (P-XX or PXX pattern) near the arc.

    Args:
        curve: The arc curve
        texts: List of text elements with position and content
        max_distance: Maximum distance to search

    Returns:
        Door number string or None
    """
    import re

    # Get arc center position
    start = curve.get("start", {})
    end = curve.get("end", {})

    center_x = (start.get("x", 0) + end.get("x", 0)) / 2
    center_y = (start.get("y", 0) + end.get("y", 0)) / 2

    # Door number patterns
    door_patterns = [
        r"^P-?\d{1,3}$",      # P-01, P01, P-123
        r"^P\.?\d{1,3}$",     # P.01, P1
        r"^PORTE\s*\d+$",     # PORTE 1
    ]

    best_match = None
    best_distance = max_distance

    for text in texts:
        content = text.get("text", "").strip().upper()

        # Check if matches door pattern
        for pattern in door_patterns:
            if re.match(pattern, content):
                # Calculate distance to text
                text_bbox = text.get("bbox", {})
                text_x = (text_bbox.get("x0", 0) + text_bbox.get("x1", 0)) / 2
                text_y = (text_bbox.get("y0", 0) + text_bbox.get("y1", 0)) / 2

                dist = math.sqrt((center_x - text_x)**2 + (center_y - text_y)**2)

                if dist < best_distance:
                    best_distance = dist
                    # Normalize to P-XX format
                    match = re.search(r"(\d+)", content)
                    if match:
                        num = match.group(1).zfill(2)
                        best_match = f"P-{num}"
                break

    return best_match


def is_door_arc(curve: dict, min_radius: float = 10.0, max_radius: float = 500.0) -> bool:
    """
    Determine if a curve is likely a door arc.

    Args:
        curve: Curve data
        min_radius: Minimum door width in units
        max_radius: Maximum door width in units

    Returns:
        True if likely a door arc
    """
    angle = calculate_arc_angle(curve)
    radius = calculate_arc_radius(curve)

    # Door arcs are typically 80-100° (close to 90°)
    # and have reasonable radius (door widths)
    angle_ok = 70 <= angle <= 110
    radius_ok = min_radius <= radius <= max_radius

    return angle_ok and radius_ok


def calculate_confidence(curve: dict, has_line: bool, has_number: bool) -> float:
    """
    Calculate confidence score for door detection.

    Args:
        curve: The detected arc
        has_line: Whether a door line was found nearby
        has_number: Whether a door number was found

    Returns:
        Confidence score 0.0-1.0
    """
    score = 0.5  # Base score for arc detection

    # Angle quality
    angle = calculate_arc_angle(curve)
    angle_diff = abs(angle - 90)
    if angle_diff < 5:
        score += 0.2
    elif angle_diff < 15:
        score += 0.1

    # Associated line
    if has_line:
        score += 0.15

    # Door number
    if has_number:
        score += 0.15

    return min(1.0, score)


def extract_curves_lines_texts(vectors: dict) -> tuple[list, list, list]:
    """
    Extract curves, lines, and texts from extract_pdf_vectors format.
    
    Handles both old format (curves, lines, texts at top level)
    and new format (drawings[].items[], text_blocks[]).
    """
    curves = []
    lines = []
    texts = []
    
    # New format: drawings with items
    for drawing in vectors.get("drawings", []):
        for item in drawing.get("items", []):
            item_type = item.get("type", "")
            if item_type == "curve":
                # Transform p1,p2,p3,p4 to start,control1,control2,end format
                curves.append({
                    "start": item.get("p1", {}),
                    "control1": item.get("p2", {}),
                    "control2": item.get("p3", {}),
                    "end": item.get("p4", {}),
                    "center": {  # Approximate center from endpoints
                        "x": (item.get("p1", {}).get("x", 0) + item.get("p4", {}).get("x", 0)) / 2,
                        "y": (item.get("p1", {}).get("y", 0) + item.get("p4", {}).get("y", 0)) / 2
                    }
                })
            elif item_type == "line":
                lines.append({
                    "start": item.get("p1", {}),
                    "end": item.get("p2", {})
                })
    
    # New format: text_blocks
    for block in vectors.get("text_blocks", []):
        bbox = block.get("bbox", {})
        texts.append({
            "text": block.get("text", ""),
            "x": bbox.get("x", 0),
            "y": bbox.get("y", 0),
            "bbox": bbox
        })
    
    # Old format fallback
    curves.extend(vectors.get("curves", []))
    lines.extend(vectors.get("lines", []))
    texts.extend(vectors.get("texts", []))
    
    # Also check paths for curves embedded in path commands
    for path in vectors.get("paths", []):
        for segment in path.get("segments", []):
            if segment.get("type") == "curve":
                curves.append(segment)
            elif segment.get("type") == "line":
                lines.append(segment)
    
    return curves, lines, texts


def detect_doors(vectors: dict) -> list:
    """
    Detect doors from vector data.

    Args:
        vectors: Dict from extract_pdf_vectors (pages[].drawings[], text_blocks[])

    Returns:
        List of detected doors
    """
    doors = []

    # Extract curves, lines, texts from the format
    curves, lines, texts = extract_curves_lines_texts(vectors)

    door_id = 0
    for curve in curves:
        if not is_door_arc(curve):
            continue

        door_id += 1

        # Find associated elements
        nearby_line = find_nearby_line(curve, lines)
        door_number = find_nearby_door_number(curve, texts)

        # Calculate properties
        angle = calculate_arc_angle(curve)
        radius = calculate_arc_radius(curve)
        direction = determine_swing_direction(curve, nearby_line)
        confidence = calculate_confidence(curve, nearby_line is not None, door_number is not None)

        # Get position from arc center
        start = curve.get("start", {})
        end = curve.get("end", {})
        position = {
            "x": (start.get("x", 0) + end.get("x", 0)) / 2,
            "y": (start.get("y", 0) + end.get("y", 0)) / 2
        }

        door = {
            "id": f"door-{door_id:03d}",
            "number": door_number,
            "position": position,
            "swing_angle": round(angle, 1),
            "direction": direction,
            "width_estimate": round(radius, 1),
            "confidence": round(confidence, 2),
            "page": vectors.get("page", 1)
        }

        doors.append(door)

    return doors


def run_detection(input_path: str, output_path: Optional[str] = None) -> dict:
    """
    Run door detection on vector data file.

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
        all_doors = []
        for page_data in vectors["pages"]:
            page_doors = detect_doors(page_data)
            all_doors.extend(page_doors)
    else:
        all_doors = detect_doors(vectors)

    results = {
        "source": str(input_path),
        "total_doors": len(all_doors),
        "doors": all_doors
    }

    if output_path:
        output_path = Path(output_path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Detected {len(all_doors)} doors -> {output_path}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Detect doors from PDF vector data"
    )
    parser.add_argument(
        "input",
        help="Path to vectors.json from extract_pdf_vectors"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output path for doors.json"
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
        print(f"Detected {results['total_doors']} doors:")
        for door in results["doors"]:
            num = door["number"] or "?"
            print(f"  {door['id']}: {num} - {door['swing_angle']}° {door['direction']} (conf: {door['confidence']})")


if __name__ == "__main__":
    main()
