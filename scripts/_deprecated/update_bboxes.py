#!/usr/bin/env python3
"""
Script to update room bounding boxes in rooms_complete.json
Based on visual analysis of PDF pages
"""
import json
from datetime import datetime

# Image dimensions
WIDTH = 4967
HEIGHT = 3509

# Room data from visual analysis - percentages from image edges
# Format: "ROOM_ID": {"left": %, "top": %, "w": %, "h": %, "page": "page-XXX.png"}

ROOM_DATA = {
    # ====== BLOC A - 2ème étage (page-012.png LEFT side) ======
    "A-200": {"left": 36.5, "top": 57.5, "w": 3.5, "h": 4.0, "page": "page-012.png"},
    "A-201": {"left": 28.5, "top": 36.0, "w": 4.0, "h": 4.5, "page": "page-012.png"},
    "A-202": {"left": 24.0, "top": 36.0, "w": 3.0, "h": 4.5, "page": "page-012.png"},
    "A-203": {"left": 31.0, "top": 31.0, "w": 6.0, "h": 5.5, "page": "page-012.png"},
    "A-204": {"left": 30.0, "top": 74.0, "w": 4.5, "h": 5.0, "page": "page-012.png"},
    "A-205": {"left": 25.5, "top": 52.5, "w": 7.5, "h": 6.5, "page": "page-012.png"},
    "A-206": {"left": 34.0, "top": 52.5, "w": 6.5, "h": 6.5, "page": "page-012.png"},
    "A-207": {"left": 30.0, "top": 45.5, "w": 12.0, "h": 2.5, "page": "page-012.png"},
    "A-208": {"left": 25.5, "top": 67.0, "w": 7.5, "h": 6.5, "page": "page-012.png"},
    "A-209": {"left": 34.0, "top": 67.0, "w": 6.5, "h": 6.5, "page": "page-012.png"},
    "A-210": {"left": 30.0, "top": 60.5, "w": 12.0, "h": 2.5, "page": "page-012.png"},
    "A-211": {"left": 39.0, "top": 67.0, "w": 2.5, "h": 8.0, "page": "page-012.png"},
    "A-212": {"left": 28.5, "top": 80.0, "w": 4.5, "h": 5.0, "page": "page-012.png"},
    "A-213": {"left": 33.0, "top": 53.5, "w": 5.5, "h": 5.0, "page": "page-012.png"},
    "A-214": {"left": 38.5, "top": 53.5, "w": 4.0, "h": 5.0, "page": "page-012.png"},
    "A-215": {"left": 42.0, "top": 53.5, "w": 3.0, "h": 4.0, "page": "page-012.png"},
    
    # ====== BLOC A - 1er étage (page-012.png RIGHT side) ======
    "A-100": {"left": 76.5, "top": 89.0, "w": 4.5, "h": 5.0, "page": "page-012.png"},
    "A-101": {"left": 71.0, "top": 85.0, "w": 3.0, "h": 8.0, "page": "page-012.png"},
    "A-102": {"left": 68.5, "top": 80.5, "w": 2.5, "h": 3.0, "page": "page-012.png"},
    "A-102-1": {"left": 65.0, "top": 80.5, "w": 2.0, "h": 2.5, "page": "page-012.png"},
    "A-102-2": {"left": 65.0, "top": 83.0, "w": 2.0, "h": 2.5, "page": "page-012.png"},
    "A-102-3": {"left": 65.0, "top": 85.5, "w": 2.0, "h": 2.5, "page": "page-012.png"},
    "A-103": {"left": 65.0, "top": 80.5, "w": 3.0, "h": 3.5, "page": "page-012.png"},
    "A-104": {"left": 62.5, "top": 75.0, "w": 5.0, "h": 6.0, "page": "page-012.png"},
    "A-105": {"left": 68.0, "top": 72.0, "w": 2.5, "h": 6.0, "page": "page-012.png"},
    "A-106": {"left": 62.0, "top": 67.0, "w": 6.0, "h": 5.0, "page": "page-012.png"},
    "A-107": {"left": 68.5, "top": 64.0, "w": 2.5, "h": 4.0, "page": "page-012.png"},
    "A-108": {"left": 71.5, "top": 57.5, "w": 3.5, "h": 3.5, "page": "page-012.png"},
    "A-109": {"left": 68.0, "top": 57.5, "w": 3.0, "h": 3.5, "page": "page-012.png"},
    "A-110": {"left": 72.0, "top": 52.0, "w": 3.0, "h": 6.0, "page": "page-012.png"},
    "A-111": {"left": 75.5, "top": 48.5, "w": 3.0, "h": 3.5, "page": "page-012.png"},
    "A-112": {"left": 54.5, "top": 62.0, "w": 6.5, "h": 5.5, "page": "page-012.png"},
    "A-113": {"left": 61.0, "top": 47.0, "w": 3.5, "h": 4.0, "page": "page-012.png"},
    "A-114": {"left": 64.5, "top": 47.0, "w": 5.0, "h": 4.0, "page": "page-012.png"},
    "A-115": {"left": 69.5, "top": 37.0, "w": 3.0, "h": 8.0, "page": "page-012.png"},
    "A-116": {"left": 72.5, "top": 37.0, "w": 6.5, "h": 5.5, "page": "page-012.png"},
    "A-117": {"left": 69.5, "top": 51.0, "w": 3.0, "h": 6.0, "page": "page-012.png"},
    "A-118": {"left": 79.0, "top": 45.0, "w": 5.0, "h": 4.5, "page": "page-012.png"},
    "A-119": {"left": 79.0, "top": 33.0, "w": 4.0, "h": 3.5, "page": "page-012.png"},
    "A-120": {"left": 72.5, "top": 33.0, "w": 6.5, "h": 4.0, "page": "page-012.png"},
    "A-121": {"left": 79.0, "top": 40.0, "w": 5.0, "h": 5.0, "page": "page-012.png"},
    "A-122": {"left": 72.5, "top": 45.0, "w": 6.5, "h": 2.5, "page": "page-012.png"},
    "A-123": {"left": 84.0, "top": 37.0, "w": 2.5, "h": 3.0, "page": "page-012.png"},
    "A-124": {"left": 84.0, "top": 42.0, "w": 2.5, "h": 4.0, "page": "page-012.png"},
    "A-125": {"left": 84.0, "top": 48.0, "w": 2.5, "h": 4.0, "page": "page-012.png"},
    "A-126": {"left": 84.0, "top": 54.0, "w": 2.5, "h": 4.0, "page": "page-012.png"},
    "A-127": {"left": 84.0, "top": 60.0, "w": 2.5, "h": 4.0, "page": "page-012.png"},
    
    # ====== BLOC B - 1er étage (page-010.png) ======
    "B-101": {"left": 73.5, "top": 68.5, "w": 4.5, "h": 8.0, "page": "page-010.png"},
    "B-102": {"left": 68.0, "top": 68.5, "w": 5.0, "h": 8.0, "page": "page-010.png"},
    "B-103": {"left": 52.0, "top": 60.5, "w": 6.5, "h": 4.0, "page": "page-010.png"},
    "B-104": {"left": 46.5, "top": 60.5, "w": 5.0, "h": 7.0, "page": "page-010.png"},
    "B-105": {"left": 60.0, "top": 68.5, "w": 3.5, "h": 4.0, "page": "page-010.png"},
    "B-106": {"left": 38.0, "top": 56.0, "w": 5.0, "h": 8.0, "page": "page-010.png"},
    "B-107": {"left": 43.5, "top": 56.0, "w": 5.0, "h": 8.0, "page": "page-010.png"},
    "B-108": {"left": 49.0, "top": 56.0, "w": 5.0, "h": 8.0, "page": "page-010.png"},
    "B-109": {"left": 54.5, "top": 56.0, "w": 5.0, "h": 8.0, "page": "page-010.png"},
    "B-110": {"left": 60.0, "top": 56.0, "w": 4.5, "h": 8.0, "page": "page-010.png"},
    "B-111": {"left": 38.0, "top": 68.5, "w": 6.0, "h": 8.0, "page": "page-010.png"},
    "B-112": {"left": 44.5, "top": 68.5, "w": 5.0, "h": 8.0, "page": "page-010.png"},
    "B-113": {"left": 50.0, "top": 68.5, "w": 5.0, "h": 8.0, "page": "page-010.png"},
    "B-114": {"left": 55.5, "top": 68.5, "w": 4.5, "h": 8.0, "page": "page-010.png"},
    "B-115": {"left": 65.5, "top": 56.0, "w": 5.0, "h": 8.0, "page": "page-010.png"},
    "B-116": {"left": 71.0, "top": 56.0, "w": 5.0, "h": 8.0, "page": "page-010.png"},
    "B-123": {"left": 32.0, "top": 60.5, "w": 3.5, "h": 4.0, "page": "page-010.png"},
    "B-124": {"left": 32.0, "top": 65.0, "w": 3.5, "h": 4.0, "page": "page-010.png"},
    "B-125": {"left": 32.0, "top": 70.0, "w": 3.5, "h": 4.0, "page": "page-010.png"},
    "B-126": {"left": 28.0, "top": 60.5, "w": 3.5, "h": 4.0, "page": "page-010.png"},
    "B-127": {"left": 28.0, "top": 65.0, "w": 3.5, "h": 4.0, "page": "page-010.png"},
    "B-128": {"left": 28.0, "top": 70.0, "w": 3.5, "h": 4.0, "page": "page-010.png"},
    "B-131": {"left": 24.0, "top": 60.5, "w": 3.5, "h": 4.0, "page": "page-010.png"},
    "B-134": {"left": 24.0, "top": 65.0, "w": 3.5, "h": 4.0, "page": "page-010.png"},
    "B-134-2": {"left": 24.0, "top": 68.0, "w": 2.5, "h": 3.0, "page": "page-010.png"},
    "B-135": {"left": 20.0, "top": 60.5, "w": 4.0, "h": 5.0, "page": "page-010.png"},
    "B-136": {"left": 20.0, "top": 66.5, "w": 4.0, "h": 5.0, "page": "page-010.png"},
    "B-137": {"left": 20.0, "top": 72.5, "w": 4.0, "h": 5.0, "page": "page-010.png"},
    "B-138": {"left": 16.0, "top": 60.5, "w": 4.0, "h": 5.0, "page": "page-010.png"},
    "B-139": {"left": 16.0, "top": 66.5, "w": 4.0, "h": 5.0, "page": "page-010.png"},
    "B-140": {"left": 16.0, "top": 72.5, "w": 4.0, "h": 5.0, "page": "page-010.png"},
    "B-141": {"left": 12.0, "top": 60.5, "w": 4.0, "h": 5.0, "page": "page-010.png"},
    "B-142": {"left": 12.0, "top": 66.5, "w": 4.0, "h": 5.0, "page": "page-010.png"},
    "B-143": {"left": 12.0, "top": 72.5, "w": 4.0, "h": 5.0, "page": "page-010.png"},
    "B-144": {"left": 8.0, "top": 60.5, "w": 4.0, "h": 5.0, "page": "page-010.png"},
    "B-145": {"left": 8.0, "top": 66.5, "w": 4.0, "h": 5.0, "page": "page-010.png"},
    "B-146": {"left": 8.0, "top": 72.5, "w": 4.0, "h": 5.0, "page": "page-010.png"},
    "B-147": {"left": 4.0, "top": 60.5, "w": 4.0, "h": 5.0, "page": "page-010.png"},
    "B-148": {"left": 4.0, "top": 66.5, "w": 4.0, "h": 5.0, "page": "page-010.png"},
    "B-149": {"left": 4.0, "top": 72.5, "w": 4.0, "h": 5.0, "page": "page-010.png"},
    
    # ====== BLOC B - 2ème étage (page-010.png) ======
    "B-201": {"left": 73.5, "top": 28.5, "w": 4.5, "h": 5.0, "page": "page-010.png"},
    "B-202": {"left": 68.0, "top": 28.5, "w": 5.0, "h": 5.0, "page": "page-010.png"},
    "B-203": {"left": 62.5, "top": 28.5, "w": 5.0, "h": 5.0, "page": "page-010.png"},
    "B-204": {"left": 57.0, "top": 28.5, "w": 5.0, "h": 5.0, "page": "page-010.png"},
    "B-205": {"left": 51.5, "top": 28.5, "w": 5.0, "h": 5.0, "page": "page-010.png"},
    "B-206": {"left": 46.0, "top": 28.5, "w": 5.0, "h": 5.0, "page": "page-010.png"},
    "B-207": {"left": 40.5, "top": 28.5, "w": 5.0, "h": 5.0, "page": "page-010.png"},
    "B-208": {"left": 35.0, "top": 28.5, "w": 5.0, "h": 5.0, "page": "page-010.png"},
    "B-209": {"left": 73.5, "top": 36.0, "w": 4.5, "h": 5.0, "page": "page-010.png"},
    "B-210": {"left": 68.0, "top": 36.0, "w": 5.0, "h": 5.0, "page": "page-010.png"},
    "B-211": {"left": 62.5, "top": 36.0, "w": 5.0, "h": 5.0, "page": "page-010.png"},
    "B-212": {"left": 57.0, "top": 36.0, "w": 5.0, "h": 5.0, "page": "page-010.png"},
    "B-213": {"left": 51.5, "top": 36.0, "w": 5.0, "h": 5.0, "page": "page-010.png"},
    
    # ====== BLOC C - 1er étage (page-010.png) ======
    "C-101": {"left": 22.0, "top": 35.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-102": {"left": 18.0, "top": 35.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-103": {"left": 14.0, "top": 35.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-104": {"left": 10.0, "top": 35.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-105": {"left": 22.0, "top": 42.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-106": {"left": 18.0, "top": 42.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-107": {"left": 14.0, "top": 42.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-108": {"left": 10.0, "top": 42.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-109": {"left": 6.0, "top": 35.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-110": {"left": 6.0, "top": 42.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-111": {"left": 26.0, "top": 35.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-112": {"left": 26.0, "top": 42.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-113": {"left": 30.0, "top": 35.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-114": {"left": 30.0, "top": 42.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-115": {"left": 34.0, "top": 35.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-116": {"left": 34.0, "top": 42.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-117": {"left": 38.0, "top": 35.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-118": {"left": 38.0, "top": 42.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-119": {"left": 42.0, "top": 35.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-120": {"left": 42.0, "top": 42.0, "w": 4.0, "h": 4.5, "page": "page-010.png"},
    "C-138": {"left": 15.0, "top": 22.0, "w": 6.0, "h": 5.0, "page": "page-010.png"},
    "C-139": {"left": 15.0, "top": 28.0, "w": 4.0, "h": 4.0, "page": "page-010.png"},
    "C-143": {"left": 20.0, "top": 22.0, "w": 4.0, "h": 4.0, "page": "page-010.png"},
    "C-143-1": {"left": 24.0, "top": 22.0, "w": 3.0, "h": 3.0, "page": "page-010.png"},
    "C-145": {"left": 28.0, "top": 22.0, "w": 4.0, "h": 4.0, "page": "page-010.png"},
    "C-147": {"left": 10.0, "top": 15.0, "w": 10.0, "h": 10.0, "page": "page-010.png"},
    "C-148": {"left": 22.0, "top": 15.0, "w": 4.0, "h": 4.0, "page": "page-010.png"},
    "C-149": {"left": 26.0, "top": 15.0, "w": 4.0, "h": 4.0, "page": "page-010.png"},
    "C-150": {"left": 30.0, "top": 15.0, "w": 4.0, "h": 4.0, "page": "page-010.png"},
}


def pct_to_bbox(left_pct, top_pct, w_pct, h_pct):
    """Convert percentages to pixel bounding box."""
    center_x = WIDTH * left_pct / 100
    center_y = HEIGHT * top_pct / 100
    half_w = WIDTH * w_pct / 200
    half_h = HEIGHT * h_pct / 200
    return [
        int(center_x - half_w),
        int(center_y - half_h),
        int(center_x + half_w),
        int(center_y + half_h)
    ]


def main():
    # Load existing data
    with open('/Users/omer/clawd/skills/blueprint-extractor/output/rooms_complete.json', 'r') as f:
        data = json.load(f)
    
    updated_count = 0
    not_found = []
    
    # Update each room
    for room in data['rooms']:
        room_id = room['id']
        if room_id in ROOM_DATA:
            rd = ROOM_DATA[room_id]
            bbox = pct_to_bbox(rd['left'], rd['top'], rd['w'], rd['h'])
            
            # Update room data
            room['bbox'] = bbox
            room['bbox_confidence'] = 0.85
            room['bbox_source'] = rd['page']
            room['plan_dimensions'] = [WIDTH, HEIGHT]
            room['bbox_updated'] = datetime.now().isoformat()
            
            updated_count += 1
            print(f"Updated {room_id}: {bbox}")
        else:
            not_found.append(room_id)
    
    # Update metadata
    data['bbox_extraction'] = {
        'date': datetime.now().isoformat(),
        'method': 'vision_ai_percentage_analysis',
        'plans_analyzed': ['page-010.png', 'page-012.png'],
        'total_bboxes_extracted': updated_count,
        'rooms_without_update': not_found
    }
    
    # Save updated data
    with open('/Users/omer/clawd/skills/blueprint-extractor/output/rooms_complete.json', 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n=== Summary ===")
    print(f"Updated: {updated_count} rooms")
    print(f"Not found in ROOM_DATA: {len(not_found)}")
    if not_found:
        print(f"Missing: {not_found}")


if __name__ == '__main__':
    main()
