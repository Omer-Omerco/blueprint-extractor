#!/usr/bin/env python3
"""
Extract and VERIFY bboxes - Double-check system.

For each room:
1. Ask Vision AI to find the bbox
2. Crop that region
3. Ask Vision AI: "What room number do you see?"
4. If match → validated
5. If no match → retry or flag for manual review
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime

try:
    from PIL import Image
    import io
    import base64
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("ERROR: PIL required. pip install Pillow", file=sys.stderr)
    sys.exit(1)

# Paths
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR.parent / "output"
PAGES_DIR = OUTPUT_DIR / "pages"
ROOMS_FILE = OUTPUT_DIR / "rooms_complete.json"
VERIFIED_FILE = OUTPUT_DIR / "rooms_verified.json"
VERIFICATION_LOG = OUTPUT_DIR / "verification_log.json"


def crop_region(img: Image.Image, bbox: list, padding: int = 80) -> Image.Image:
    """Crop region with padding."""
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(img.width, x2 + padding)
    y2 = min(img.height, y2 + padding)
    return img.crop((x1, y1, x2, y2))


def save_crop(crop: Image.Image, room_id: str, suffix: str = "") -> str:
    """Save crop and return path."""
    renders_dir = OUTPUT_DIR / "renders" / "verified"
    renders_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{room_id}{suffix}.png"
    path = renders_dir / filename
    crop.save(path)
    return str(path)


def verify_crop_contains_room(crop_path: str, expected_room_id: str) -> dict:
    """
    CRITICAL: Verify that the crop actually contains the expected room.
    
    This function should call Vision AI to check:
    "What room number/ID do you see in this image?"
    
    Returns:
        {
            "verified": bool,
            "seen_id": str or None,
            "confidence": float,
            "method": "vision_ai"
        }
    """
    # TODO: Integrate with actual Vision AI
    # For now, return unverified status
    return {
        "verified": False,
        "seen_id": None,
        "confidence": 0.0,
        "method": "pending_vision",
        "note": "Needs Vision AI integration"
    }


def extract_and_verify_room(room_id: str, page_path: str, estimated_bbox: list = None) -> dict:
    """
    Extract bbox for a room and VERIFY it contains the right room.
    
    Process:
    1. If no bbox provided, ask Vision AI to find it
    2. Crop the region
    3. Verify the crop contains the expected room ID
    4. If verified → return validated bbox
    5. If not → return error status
    """
    result = {
        "room_id": room_id,
        "page": page_path,
        "timestamp": datetime.now().isoformat(),
        "status": "pending"
    }
    
    # Load page
    if not os.path.exists(page_path):
        result["status"] = "error"
        result["error"] = f"Page not found: {page_path}"
        return result
    
    img = Image.open(page_path)
    result["page_dimensions"] = [img.width, img.height]
    
    # Use provided bbox or need to find it
    if estimated_bbox:
        bbox = estimated_bbox
    else:
        # TODO: Call Vision AI to find bbox
        result["status"] = "error"
        result["error"] = "No bbox provided and Vision AI not integrated"
        return result
    
    result["bbox"] = bbox
    
    # Crop the region
    crop = crop_region(img, bbox)
    crop_path = save_crop(crop, room_id, "_verify")
    result["crop_path"] = crop_path
    result["crop_size"] = [crop.width, crop.height]
    
    # VERIFY the crop contains the right room
    verification = verify_crop_contains_room(crop_path, room_id)
    result["verification"] = verification
    
    if verification["verified"]:
        result["status"] = "verified"
        result["bbox_confidence"] = 0.95
    else:
        result["status"] = "unverified"
        result["bbox_confidence"] = 0.5
        result["needs_review"] = True
    
    return result


def batch_verify_rooms(rooms: list, pages_dir: Path) -> dict:
    """
    Verify all rooms in batch.
    
    Returns summary stats.
    """
    results = {
        "verified": [],
        "unverified": [],
        "errors": [],
        "stats": {}
    }
    
    for room in rooms:
        room_id = room.get("id")
        source_pages = room.get("source_pages", [])
        primary_source = room.get("primary_source")
        bbox = room.get("bbox")
        
        if not source_pages and not primary_source:
            results["errors"].append({
                "room_id": room_id,
                "error": "No source page"
            })
            continue
        
        # Get page path
        page_num = primary_source or source_pages[0]
        page_path = pages_dir / f"page-{page_num:03d}.png"
        
        if not page_path.exists():
            results["errors"].append({
                "room_id": room_id,
                "error": f"Page {page_num} not found"
            })
            continue
        
        # Extract and verify
        result = extract_and_verify_room(room_id, str(page_path), bbox)
        
        if result["status"] == "verified":
            results["verified"].append(result)
        elif result["status"] == "unverified":
            results["unverified"].append(result)
        else:
            results["errors"].append(result)
    
    # Stats
    total = len(rooms)
    results["stats"] = {
        "total": total,
        "verified": len(results["verified"]),
        "unverified": len(results["unverified"]),
        "errors": len(results["errors"]),
        "verification_rate": len(results["verified"]) / total if total > 0 else 0
    }
    
    return results


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract and verify room bboxes")
    parser.add_argument("--room", "-r", help="Verify single room")
    parser.add_argument("--all", "-a", action="store_true", help="Verify all rooms")
    parser.add_argument("--bloc", "-b", help="Verify all rooms in bloc (A, B, C)")
    parser.add_argument("--page", "-p", type=int, help="Page number for single room")
    parser.add_argument("--bbox", nargs=4, type=int, help="Bbox: x1 y1 x2 y2")
    parser.add_argument("--dry-run", action="store_true", help="Don't save results")
    
    args = parser.parse_args()
    
    # Load rooms
    with open(ROOMS_FILE) as f:
        data = json.load(f)
    rooms = data.get("rooms", [])
    
    if args.room:
        # Single room verification
        room = next((r for r in rooms if r["id"] == args.room), None)
        if not room:
            print(f"Room {args.room} not found")
            sys.exit(1)
        
        page_num = args.page or room.get("primary_source") or (room.get("source_pages", [None])[0])
        if not page_num:
            print(f"No page for room {args.room}")
            sys.exit(1)
        
        page_path = PAGES_DIR / f"page-{page_num:03d}.png"
        bbox = args.bbox or room.get("bbox")
        
        result = extract_and_verify_room(args.room, str(page_path), bbox)
        print(json.dumps(result, indent=2))
        
    elif args.all or args.bloc:
        # Batch verification
        if args.bloc:
            rooms = [r for r in rooms if r.get("block") == args.bloc.upper()]
        
        results = batch_verify_rooms(rooms, PAGES_DIR)
        
        print(f"\n{'='*60}")
        print(f"VERIFICATION RESULTS")
        print(f"{'='*60}")
        print(f"Total rooms: {results['stats']['total']}")
        print(f"Verified:    {results['stats']['verified']}")
        print(f"Unverified:  {results['stats']['unverified']}")
        print(f"Errors:      {results['stats']['errors']}")
        print(f"Rate:        {results['stats']['verification_rate']:.1%}")
        
        if not args.dry_run:
            with open(VERIFICATION_LOG, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\nLog saved: {VERIFICATION_LOG}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
