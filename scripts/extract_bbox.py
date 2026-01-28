#!/usr/bin/env python3
"""
Extract bounding boxes for room labels from blueprint pages.

Uses OCR (pytesseract) to find room numbers and their coordinates.
Falls back gracefully if OCR is unavailable.
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("Pillow not installed - image processing unavailable")

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not installed - OCR unavailable")


def load_rooms(rooms_path: Path) -> dict:
    """Load rooms from rooms_complete.json."""
    with open(rooms_path) as f:
        data = json.load(f)
    return {room['id']: room for room in data.get('rooms', [])}


def get_room_patterns() -> list[re.Pattern]:
    """Get regex patterns for room IDs (A-101, B-205, etc.)."""
    return [
        re.compile(r'\b([ABC]-?\d{3})\b', re.IGNORECASE),
        re.compile(r'\b(\d{3})\b'),  # Just numbers like 101, 205
    ]


def extract_bbox_from_page(
    image_path: Path,
    room_ids: set[str],
    page_num: int
) -> dict[str, dict]:
    """
    Extract bounding boxes for room IDs found on a page.
    
    Args:
        image_path: Path to the PNG image
        room_ids: Set of room IDs to look for
        page_num: Page number for metadata
        
    Returns:
        Dict mapping room_id to {page, bbox, confidence}
    """
    if not PIL_AVAILABLE:
        logger.error("Pillow required for bbox extraction")
        return {}
    
    if not TESSERACT_AVAILABLE:
        logger.warning("pytesseract not available - using fallback bbox estimation")
        return _fallback_bbox(image_path, room_ids, page_num)
    
    results = {}
    img = Image.open(image_path)
    width, height = img.size
    
    try:
        # Get detailed OCR data with bounding boxes
        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except Exception as e:
        logger.error(f"OCR failed on {image_path}: {e}")
        return _fallback_bbox(image_path, room_ids, page_num)
    
    patterns = get_room_patterns()
    
    # Process each detected text block
    n_boxes = len(ocr_data['text'])
    for i in range(n_boxes):
        text = ocr_data['text'][i].strip()
        conf = int(ocr_data['conf'][i]) if ocr_data['conf'][i] != '-1' else 0
        
        if conf < 30 or not text:  # Skip low confidence or empty
            continue
        
        # Check if text matches any room pattern
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                matched_id = match.group(1).upper()
                
                # Normalize: add dash if missing (101 -> A-101 based on context)
                if matched_id.isdigit() and len(matched_id) == 3:
                    # Try to find which block this belongs to
                    for room_id in room_ids:
                        if room_id.endswith(matched_id):
                            matched_id = room_id
                            break
                
                # Ensure proper format (A-101 not A101)
                if len(matched_id) == 4 and matched_id[1].isdigit():
                    matched_id = f"{matched_id[0]}-{matched_id[1:]}"
                
                if matched_id in room_ids:
                    x = ocr_data['left'][i]
                    y = ocr_data['top'][i]
                    w = ocr_data['width'][i]
                    h = ocr_data['height'][i]
                    
                    # Expand bbox to likely room area (room labels are usually inside rooms)
                    # Estimate room size as 5-10x the label size
                    expand_factor = 8
                    room_w = w * expand_factor
                    room_h = h * expand_factor
                    
                    # Center the bbox on the label
                    x1 = max(0, int(x - room_w / 2))
                    y1 = max(0, int(y - room_h / 2))
                    x2 = min(width, int(x + w + room_w / 2))
                    y2 = min(height, int(y + h + room_h / 2))
                    
                    # Only keep if we haven't found this room yet or this has higher confidence
                    if matched_id not in results or conf / 100 > results[matched_id]['confidence']:
                        results[matched_id] = {
                            'page': page_num,
                            'bbox': [x1, y1, x2, y2],
                            'label_bbox': [x, y, x + w, y + h],  # Original label location
                            'confidence': conf / 100.0
                        }
                        logger.debug(f"Found {matched_id} at bbox {results[matched_id]['bbox']}")
    
    return results


def _fallback_bbox(
    image_path: Path,
    room_ids: set[str],
    page_num: int
) -> dict[str, dict]:
    """
    Fallback when OCR is unavailable.
    Returns estimated center-page bbox for rooms known to be on this page.
    """
    if not PIL_AVAILABLE:
        return {}
    
    img = Image.open(image_path)
    width, height = img.size
    
    # Create a generic center-of-page bbox
    margin = 100
    center_bbox = [margin, margin, width - margin, height - margin]
    
    results = {}
    for room_id in room_ids:
        results[room_id] = {
            'page': page_num,
            'bbox': center_bbox,
            'confidence': 0.1,  # Low confidence for fallback
            'fallback': True
        }
    
    return results


def extract_all_bboxes(
    pages_dir: Path,
    rooms_path: Path,
    output_path: Optional[Path] = None
) -> dict:
    """
    Extract bounding boxes for all rooms from all pages.
    
    Args:
        pages_dir: Directory containing page-XXX.png files
        rooms_path: Path to rooms_complete.json
        output_path: Optional path to save results
        
    Returns:
        Dict mapping room_id to bbox info
    """
    rooms = load_rooms(rooms_path)
    all_room_ids = set(rooms.keys())
    
    # Build page -> room mapping from rooms_complete.json
    page_rooms: dict[int, set[str]] = {}
    for room_id, room_data in rooms.items():
        primary_page = room_data.get('primary_source') or room_data.get('page')
        if primary_page:
            page_rooms.setdefault(primary_page, set()).add(room_id)
    
    results = {}
    
    # Process each page
    for page_path in sorted(pages_dir.glob('page-*.png')):
        # Extract page number from filename (page-004.png -> 4)
        page_num = int(page_path.stem.split('-')[1])
        
        # Get rooms expected on this page
        expected_rooms = page_rooms.get(page_num, set())
        if not expected_rooms:
            continue
        
        logger.info(f"Processing page {page_num} ({len(expected_rooms)} rooms expected)")
        
        page_results = extract_bbox_from_page(page_path, expected_rooms, page_num)
        results.update(page_results)
    
    # Log summary
    found = len(results)
    total = len(all_room_ids)
    logger.info(f"Extracted {found}/{total} room bboxes ({found/total*100:.1f}%)")
    
    # Add rooms without bbox (fallback to page-level)
    for room_id in all_room_ids:
        if room_id not in results:
            room_data = rooms[room_id]
            primary_page = room_data.get('primary_source') or room_data.get('page')
            if primary_page:
                results[room_id] = {
                    'page': primary_page,
                    'bbox': None,  # No bbox available
                    'confidence': 0.0,
                    'fallback': True
                }
    
    # Save results
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Saved bboxes to {output_path}")
    
    return results


def update_rooms_with_bbox(
    rooms_path: Path,
    bbox_path: Path,
    output_path: Optional[Path] = None
) -> None:
    """
    Update rooms_complete.json with bbox data.
    
    Args:
        rooms_path: Path to rooms_complete.json
        bbox_path: Path to room_bboxes.json
        output_path: Optional output path (defaults to overwriting rooms_path)
    """
    with open(rooms_path) as f:
        rooms_data = json.load(f)
    
    with open(bbox_path) as f:
        bboxes = json.load(f)
    
    for room in rooms_data.get('rooms', []):
        room_id = room['id']
        if room_id in bboxes:
            bbox_info = bboxes[room_id]
            room['bbox'] = bbox_info.get('bbox')
            room['bbox_confidence'] = bbox_info.get('confidence', 0.0)
    
    output = output_path or rooms_path
    with open(output, 'w') as f:
        json.dump(rooms_data, f, indent=2)
    
    logger.info(f"Updated {output} with bbox data")


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract room bounding boxes from blueprints')
    parser.add_argument('--pages-dir', type=Path, default=Path('output/pages'),
                        help='Directory containing page images')
    parser.add_argument('--rooms', type=Path, default=Path('output/rooms_complete.json'),
                        help='Path to rooms_complete.json')
    parser.add_argument('--output', '-o', type=Path, default=Path('output/room_bboxes.json'),
                        help='Output path for bboxes')
    parser.add_argument('--update-rooms', action='store_true',
                        help='Also update rooms_complete.json with bbox data')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Extract bboxes
    extract_all_bboxes(args.pages_dir, args.rooms, args.output)
    
    # Optionally update rooms file
    if args.update_rooms:
        update_rooms_with_bbox(args.rooms, args.output)


if __name__ == '__main__':
    main()
