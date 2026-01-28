#!/usr/bin/env python3
"""
Door detector for blueprint vector data.
Detects doors using multiple methods:
1. Arc patterns (curves) - traditional door swing symbols
2. Text labels (P-XX, PORTE, etc.) - door number annotations
3. Line patterns - parallel lines with gaps indicating door openings
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Optional


# Door number patterns
DOOR_PATTERNS = [
    r"^P-?\d{1,3}[A-Z]?$",        # P-01, P01, P-123, P-01A
    r"^P\.?\d{1,3}[A-Z]?$",       # P.01, P1, P.12B
    r"^PORTE\s*\d+[A-Z]?$",       # PORTE 1, PORTE 12A
    r"^D-?\d{1,3}[A-Z]?$",        # D-01, D01 (English format)
    r"^DOOR\s*\d+[A-Z]?$",        # DOOR 1
]


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

    sx, sy = start.get("x", 0), start.get("y", 0)
    ex, ey = end.get("x", 0), end.get("y", 0)

    dx = ex - sx
    dy = ey - sy

    if "center" in curve:
        cx, cy = curve["center"].get("x", 0), curve["center"].get("y", 0)
        v1x, v1y = sx - cx, sy - cy
        v2x, v2y = ex - cx, ey - cy

        dot = v1x * v2x + v1y * v2y
        mag1 = math.sqrt(v1x**2 + v1y**2)
        mag2 = math.sqrt(v2x**2 + v2y**2)

        if mag1 > 0 and mag2 > 0:
            cos_angle = max(-1, min(1, dot / (mag1 * mag2)))
            return math.degrees(math.acos(cos_angle))

    if "control1" in curve and "control2" in curve:
        c1 = curve["control1"]
        c2 = curve["control2"]

        chord = math.sqrt(dx**2 + dy**2)

        c1x, c1y = c1.get("x", 0), c1.get("y", 0)
        c2x, c2y = c2.get("x", 0), c2.get("y", 0)

        ctrl_dist1 = math.sqrt((c1x - sx)**2 + (c1y - sy)**2)
        ctrl_dist2 = math.sqrt((c2x - ex)**2 + (c2y - ey)**2)
        avg_ctrl_dist = (ctrl_dist1 + ctrl_dist2) / 2

        if chord > 0:
            estimated_radius = chord / math.sqrt(2)
            if estimated_radius > 0:
                ratio = avg_ctrl_dist / estimated_radius
                if ratio > 0.4 and ratio < 0.7:
                    return 90.0
                elif ratio > 0.2 and ratio <= 0.4:
                    return 45.0
                elif ratio >= 0.7:
                    return 120.0

    chord = math.sqrt(dx**2 + dy**2)
    if chord > 0:
        return 90.0

    return 0.0


def calculate_arc_radius(curve: dict) -> float:
    """
    Calculate the radius of an arc (door width estimate).
    """
    start = curve.get("start", {})
    end = curve.get("end", {})

    sx, sy = start.get("x", 0), start.get("y", 0)
    ex, ey = end.get("x", 0), end.get("y", 0)

    chord = math.sqrt((ex - sx)**2 + (ey - sy)**2)
    return chord / math.sqrt(2)


def determine_swing_direction(curve: dict, line: Optional[dict] = None) -> str:
    """
    Determine door swing direction (left/right).
    """
    start = curve.get("start", {})
    end = curve.get("end", {})

    sx, sy = start.get("x", 0), start.get("y", 0)
    ex, ey = end.get("x", 0), end.get("y", 0)

    if "control1" in curve and "control2" in curve:
        c1 = curve["control1"]
        c1x, c1y = c1.get("x", 0), c1.get("y", 0)

        dx = ex - sx
        dy = ey - sy
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

        for ax, ay in arc_points:
            for lx, ly in line_points:
                dist = math.sqrt((ax - lx)**2 + (ay - ly)**2)
                if dist < tolerance:
                    return line

    return None


def is_door_label(text: str) -> bool:
    """
    Check if text matches a door label pattern.

    Args:
        text: Text content to check

    Returns:
        True if matches door pattern
    """
    content = text.strip().upper()
    for pattern in DOOR_PATTERNS:
        if re.match(pattern, content):
            return True
    return False


def normalize_door_number(text: str) -> str:
    """
    Normalize door number to P-XX format.

    Args:
        text: Door label text

    Returns:
        Normalized door number (e.g., "P-01")
    """
    content = text.strip().upper()
    
    # Extract number and optional letter suffix
    match = re.search(r"(\d+)([A-Z])?", content)
    if match:
        num = match.group(1).zfill(2)
        suffix = match.group(2) or ""
        return f"P-{num}{suffix}"
    return None


def find_nearby_door_number(position: dict, texts: list, max_distance: float = 50.0) -> Optional[str]:
    """
    Find door number text near a position.

    Args:
        position: Dict with x, y coordinates
        texts: List of text elements
        max_distance: Maximum distance to search

    Returns:
        Normalized door number or None
    """
    center_x = position.get("x", 0)
    center_y = position.get("y", 0)

    best_match = None
    best_distance = max_distance

    for text in texts:
        content = text.get("text", "").strip()
        
        if not is_door_label(content):
            continue

        # Calculate distance to text
        text_bbox = text.get("bbox", {})
        text_x = (text_bbox.get("x0", 0) + text_bbox.get("x1", 0)) / 2
        text_y = (text_bbox.get("y0", 0) + text_bbox.get("y1", 0)) / 2

        # Also try x, y direct attributes
        if text_x == 0 and text_y == 0:
            text_x = text.get("x", 0)
            text_y = text.get("y", 0)

        dist = math.sqrt((center_x - text_x)**2 + (center_y - text_y)**2)

        if dist < best_distance:
            best_distance = dist
            best_match = normalize_door_number(content)

    return best_match


def is_door_arc(curve: dict, min_radius: float = 10.0, max_radius: float = 500.0) -> bool:
    """
    Determine if a curve is likely a door arc.
    """
    angle = calculate_arc_angle(curve)
    radius = calculate_arc_radius(curve)

    angle_ok = 70 <= angle <= 110
    radius_ok = min_radius <= radius <= max_radius

    return angle_ok and radius_ok


def calculate_confidence(
    source: str,
    has_arc: bool = False,
    has_line: bool = False,
    has_number: bool = False,
    angle_quality: float = 0.0
) -> float:
    """
    Calculate confidence score for door detection.

    Args:
        source: Detection method ("arc", "label", "pattern")
        has_arc: Whether door arc was found
        has_line: Whether door line was found
        has_number: Whether door number was found
        angle_quality: How close to 90° (0-1)

    Returns:
        Confidence score 0.0-1.0
    """
    if source == "arc":
        score = 0.5
        score += angle_quality * 0.2
        if has_line:
            score += 0.15
        if has_number:
            score += 0.15
    elif source == "label":
        # Label-only detection has lower base confidence
        score = 0.4
        if has_number:
            score += 0.2
    elif source == "pattern":
        # Pattern-based detection
        score = 0.35
        if has_number:
            score += 0.25
    else:
        score = 0.3

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
                curves.append({
                    "start": item.get("p1", {}),
                    "control1": item.get("p2", {}),
                    "control2": item.get("p3", {}),
                    "end": item.get("p4", {}),
                    "center": {
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


def detect_doors_from_arcs(curves: list, lines: list, texts: list, page_num: int = 1) -> list:
    """
    Detect doors from arc patterns (traditional method).
    
    Args:
        curves: List of curve elements
        lines: List of line elements
        texts: List of text elements
        page_num: Page number for output
    
    Returns:
        List of detected doors
    """
    doors = []
    door_id = 0

    for curve in curves:
        if not is_door_arc(curve):
            continue

        door_id += 1

        # Find associated elements
        nearby_line = find_nearby_line(curve, lines)
        
        # Get position from arc center
        start = curve.get("start", {})
        end = curve.get("end", {})
        position = {
            "x": (start.get("x", 0) + end.get("x", 0)) / 2,
            "y": (start.get("y", 0) + end.get("y", 0)) / 2
        }
        
        door_number = find_nearby_door_number(position, texts)

        # Calculate properties
        angle = calculate_arc_angle(curve)
        radius = calculate_arc_radius(curve)
        direction = determine_swing_direction(curve, nearby_line)
        
        angle_quality = 1.0 - min(abs(angle - 90) / 20, 1.0)
        confidence = calculate_confidence(
            "arc",
            has_arc=True,
            has_line=nearby_line is not None,
            has_number=door_number is not None,
            angle_quality=angle_quality
        )

        door = {
            "id": f"door-{door_id:03d}",
            "number": door_number,
            "position": position,
            "swing_angle": round(angle, 1),
            "direction": direction,
            "width_estimate": round(radius, 1),
            "confidence": round(confidence, 2),
            "detection_method": "arc",
            "page": page_num
        }

        doors.append(door)

    return doors


def detect_doors_from_labels(texts: list, existing_positions: list, page_num: int = 1, min_distance: float = 50.0) -> list:
    """
    Detect doors from text labels that weren't matched to arcs.
    
    This handles PDFs where doors are labeled but don't have swing arc symbols.
    
    Args:
        texts: List of text elements
        existing_positions: List of (x, y) positions already detected as doors
        page_num: Page number for output
        min_distance: Minimum distance from existing doors to consider
    
    Returns:
        List of detected doors from labels only
    """
    doors = []
    door_id = len(existing_positions)  # Continue numbering

    for text in texts:
        content = text.get("text", "").strip()
        
        if not is_door_label(content):
            continue

        # Get text position
        bbox = text.get("bbox", {})
        text_x = (bbox.get("x0", 0) + bbox.get("x1", 0)) / 2
        text_y = (bbox.get("y0", 0) + bbox.get("y1", 0)) / 2

        # Fallback to direct coordinates
        if text_x == 0 and text_y == 0:
            text_x = text.get("x", 0)
            text_y = text.get("y", 0)

        # Skip if too close to an existing door
        too_close = False
        for ex, ey in existing_positions:
            dist = math.sqrt((text_x - ex)**2 + (text_y - ey)**2)
            if dist < min_distance:
                too_close = True
                break

        if too_close:
            continue

        door_id += 1
        door_number = normalize_door_number(content)
        
        confidence = calculate_confidence("label", has_number=True)

        door = {
            "id": f"door-{door_id:03d}",
            "number": door_number,
            "position": {"x": text_x, "y": text_y},
            "swing_angle": None,  # Unknown without arc
            "direction": "unknown",
            "width_estimate": None,  # Unknown without arc
            "confidence": round(confidence, 2),
            "detection_method": "label",
            "page": page_num
        }

        doors.append(door)
        existing_positions.append((text_x, text_y))

    return doors


def find_door_line_patterns(lines: list, texts: list, min_gap: float = 24.0, max_gap: float = 200.0) -> list:
    """
    Find door openings from line patterns (wall gaps).
    
    Looks for parallel wall lines with gaps that could be door openings.
    This is an advanced detection method for when no arcs or labels are present.
    
    Args:
        lines: List of line elements
        texts: List of text elements
        min_gap: Minimum gap width (typical narrow door ~2')
        max_gap: Maximum gap width (typical wide door ~6')
    
    Returns:
        List of potential door positions
    """
    # This is a placeholder for more advanced line pattern detection
    # Would analyze wall line endpoints to find aligned gaps
    # For now, return empty - this method requires more sophisticated analysis
    return []


def detect_doors(vectors: dict) -> list:
    """
    Detect doors from vector data using multiple methods.

    Args:
        vectors: Dict from extract_pdf_vectors (pages[].drawings[], text_blocks[])

    Returns:
        List of detected doors
    """
    # Extract curves, lines, texts from the format
    curves, lines, texts = extract_curves_lines_texts(vectors)
    page_num = vectors.get("page", vectors.get("page_number", 1))
    
    # Method 1: Arc-based detection (traditional)
    arc_doors = detect_doors_from_arcs(curves, lines, texts, page_num)
    
    # Collect positions of arc-detected doors
    existing_positions = [
        (d["position"]["x"], d["position"]["y"]) 
        for d in arc_doors
    ]
    
    # Method 2: Label-based detection (for PDFs without swing arcs)
    label_doors = detect_doors_from_labels(texts, existing_positions, page_num)
    
    # Combine all detected doors
    all_doors = arc_doors + label_doors
    
    # Re-number doors sequentially
    for i, door in enumerate(all_doors, 1):
        door["id"] = f"door-{i:03d}"

    return all_doors


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

    # Count by detection method
    arc_count = sum(1 for d in all_doors if d.get("detection_method") == "arc")
    label_count = sum(1 for d in all_doors if d.get("detection_method") == "label")

    results = {
        "source": str(input_path),
        "total_doors": len(all_doors),
        "detection_summary": {
            "arc_detected": arc_count,
            "label_detected": label_count
        },
        "doors": all_doors
    }

    if output_path:
        output_path = Path(output_path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Detected {len(all_doors)} doors ({arc_count} arc, {label_count} label) -> {output_path}")

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
        # Print summary
        arc_count = results["detection_summary"]["arc_detected"]
        label_count = results["detection_summary"]["label_detected"]
        print(f"Detected {results['total_doors']} doors ({arc_count} arc, {label_count} label):")
        for door in results["doors"]:
            num = door["number"] or "?"
            method = door.get("detection_method", "unknown")
            if door["swing_angle"]:
                print(f"  {door['id']}: {num} - {door['swing_angle']}° {door['direction']} [{method}] (conf: {door['confidence']})")
            else:
                print(f"  {door['id']}: {num} [{method}] (conf: {door['confidence']})")


if __name__ == "__main__":
    main()
