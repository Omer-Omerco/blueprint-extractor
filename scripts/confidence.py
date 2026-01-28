#!/usr/bin/env python3
"""
Confidence Score Calculator for Blueprint Extraction.

Calculates confidence scores based on:
- Number of source pages (more = higher confidence)
- Extraction method reliability
- Data completeness
- Cross-validation across sources

Usage:
    python confidence.py --input rooms.json --output rooms_with_confidence.json
"""

import argparse
import json
from pathlib import Path
from typing import Optional


# Extraction method reliability weights
METHOD_WEIGHTS = {
    "ocr": 0.85,           # Direct OCR from plans
    "table": 0.90,         # From structured tables (schedules)
    "cross_ref": 0.80,     # Cross-referenced from multiple sources
    "inferred": 0.60,      # Inferred from context
    "manual": 1.00,        # Manually verified
    "unknown": 0.50        # Unknown method
}

# Base confidence by data type
BASE_CONFIDENCE = {
    "room_id": 0.95,       # Room IDs are usually clear
    "room_name": 0.85,     # Names can be abbreviated
    "floor": 0.90,         # Usually clear from plans
    "block": 0.90,         # Usually clear
    "dimensions": 0.75,    # Can be hard to read
    "area": 0.70           # Often calculated, may have errors
}


def calculate_room_confidence(room: dict) -> tuple[float, str, list[str]]:
    """
    Calculate confidence score for a room extraction.
    
    Args:
        room: Room dictionary with extraction data
    
    Returns:
        tuple: (confidence_score, extraction_method, notes)
    """
    notes = []
    
    # Get source pages
    source_pages = room.get("source_pages", room.get("pages", []))
    num_sources = len(source_pages)
    
    # Determine extraction method
    extraction_method = room.get("extraction_method", "unknown")
    if extraction_method == "unknown":
        # Infer method from source count
        if num_sources >= 3:
            extraction_method = "cross_ref"
            notes.append("Méthode inférée: cross-référence multi-sources")
        elif num_sources >= 1:
            extraction_method = "ocr"
            notes.append("Méthode inférée: OCR directe")
        else:
            extraction_method = "inferred"
            notes.append("Méthode inférée: données incomplètes")
    
    # Base confidence from method
    base_confidence = METHOD_WEIGHTS.get(extraction_method, 0.5)
    
    # Adjust for number of sources
    if num_sources == 0:
        source_factor = 0.3
        notes.append("ATTENTION: Aucune page source identifiée")
    elif num_sources == 1:
        source_factor = 0.7
        notes.append("Source unique - validation recommandée")
    elif num_sources == 2:
        source_factor = 0.85
    elif num_sources >= 3:
        source_factor = 1.0
        notes.append("Multiples sources - haute fiabilité")
    else:
        source_factor = 0.5
    
    # Adjust for data completeness
    completeness_score = 1.0
    
    if not room.get("name") or room.get("name") == "LOCAL":
        completeness_score -= 0.1
        notes.append("Nom générique ou manquant")
    
    if not room.get("id"):
        completeness_score -= 0.2
        notes.append("ID manquant")
    
    if not room.get("floor") and not room.get("block"):
        completeness_score -= 0.1
        notes.append("Localisation incomplète")
    
    # Calculate final confidence
    confidence = base_confidence * source_factor * completeness_score
    
    # Clamp to valid range
    confidence = max(0.1, min(1.0, confidence))
    
    return round(confidence, 3), extraction_method, notes


def calculate_primary_source(source_pages: list[int]) -> Optional[int]:
    """
    Determine primary source page.
    
    Heuristic: The page that appears in multiple room extractions
    or the middle page in the range is often the main floor plan.
    """
    if not source_pages:
        return None
    
    # Sort pages
    sorted_pages = sorted(source_pages)
    
    # For now, prefer lower page numbers (usually main floor plans)
    # Page 30-31 are often room schedules (tables)
    non_schedule_pages = [p for p in sorted_pages if p < 30]
    
    if non_schedule_pages:
        return non_schedule_pages[0]
    
    return sorted_pages[0]


def enhance_room_data(room: dict) -> dict:
    """
    Enhance a room dictionary with confidence data.
    
    Args:
        room: Original room dictionary
    
    Returns:
        Enhanced room dictionary
    """
    # Calculate confidence
    confidence, method, notes = calculate_room_confidence(room)
    
    # Get/normalize source pages
    source_pages = room.get("source_pages", room.get("pages", []))
    
    # Determine primary source
    primary_source = room.get("primary_source") or calculate_primary_source(source_pages)
    
    # Build enhanced room
    enhanced = {
        "id": room.get("id"),
        "name": room.get("name"),
        "floor": room.get("floor"),
        "block": room.get("block"),
        "confidence": confidence,
        "source_pages": source_pages,
        "primary_source": primary_source,
        "extraction_method": method,
        "extraction_notes": " | ".join(notes) if notes else None
    }
    
    # Preserve any additional fields
    for key, value in room.items():
        if key not in enhanced:
            enhanced[key] = value
    
    # Remove None values for cleaner output
    enhanced = {k: v for k, v in enhanced.items() if v is not None}
    
    return enhanced


def enhance_rooms_file(input_path: Path, output_path: Optional[Path] = None) -> dict:
    """
    Enhance a rooms JSON file with confidence data.
    
    Args:
        input_path: Path to input JSON
        output_path: Path to output JSON (optional, can be same as input)
    
    Returns:
        Enhanced data dictionary
    """
    with open(input_path) as f:
        data = json.load(f)
    
    # Enhance each room
    rooms = data.get("rooms", [])
    enhanced_rooms = [enhance_room_data(room) for room in rooms]
    
    # Update data
    data["rooms"] = enhanced_rooms
    
    # Add quality metadata
    confidences = [r.get("confidence", 0) for r in enhanced_rooms]
    data["quality_meta"] = {
        "confidence_added": True,
        "average_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0,
        "rooms_high_confidence": sum(1 for c in confidences if c >= 0.8),
        "rooms_medium_confidence": sum(1 for c in confidences if 0.5 <= c < 0.8),
        "rooms_low_confidence": sum(1 for c in confidences if c < 0.5)
    }
    
    # Save if output path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    return data


def main():
    parser = argparse.ArgumentParser(description="Add confidence scores to room data")
    parser.add_argument("--input", "-i", default="output/rooms_complete.json",
                       help="Input rooms JSON file")
    parser.add_argument("--output", "-o", default=None,
                       help="Output JSON file (default: overwrite input)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Print stats without writing")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path
    
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        return 1
    
    # Process
    data = enhance_rooms_file(input_path, None if args.dry_run else output_path)
    
    # Print summary
    meta = data.get("quality_meta", {})
    print("\n" + "="*60)
    print("CONFIDENCE SCORES CALCULATED")
    print("="*60)
    print(f"Total rooms: {data.get('total_rooms', len(data.get('rooms', [])))}")
    print(f"Average confidence: {meta.get('average_confidence', 0):.3f}")
    print(f"High confidence (≥0.8): {meta.get('rooms_high_confidence', 0)}")
    print(f"Medium confidence (0.5-0.8): {meta.get('rooms_medium_confidence', 0)}")
    print(f"Low confidence (<0.5): {meta.get('rooms_low_confidence', 0)}")
    
    if args.dry_run:
        print("\n[DRY RUN - no files modified]")
    else:
        print(f"\nOutput: {output_path}")
    
    print("="*60)
    
    # Show sample
    print("\nSample enhanced rooms:")
    for room in data.get("rooms", [])[:3]:
        print(f"  {room.get('id')}: {room.get('name')} "
              f"(conf={room.get('confidence')}, method={room.get('extraction_method')})")
    
    return 0


if __name__ == "__main__":
    exit(main())
