#!/usr/bin/env python3
"""
Sniper Mode Validation - Vision AI-based room extraction validation
Crops specific regions from blueprints and validates room IDs with Vision AI.
"""

import json
import base64
import os
import sys
import re
from datetime import datetime
from pathlib import Path

# Optional PIL import - only needed for image cropping
try:
    from PIL import Image
    import io
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: PIL not available. Image cropping disabled.", file=sys.stderr)

# Add parent dir for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration
OUTPUT_DIR = Path(__file__).parent.parent / "output"
PLANS_DIR = Path("/Users/omer/clawd/projects/ecole-enfants-jesus/visual-analysis")
VALIDATION_LOG = OUTPUT_DIR / "validation_log.json"
ROOMS_FILE = OUTPUT_DIR / "rooms_complete.json"


def load_image(plan_path: str):
    """Load image from plan path."""
    if not PIL_AVAILABLE:
        raise ImportError("PIL required for image operations. Install with: pip install Pillow")
    return Image.open(plan_path)


def crop_region(img: Image.Image, bbox: list, padding: int = 50) -> Image.Image:
    """
    Crop a region from image with padding.
    bbox format: [x1, y1, x2, y2]
    """
    x1, y1, x2, y2 = bbox
    
    # Add padding
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(img.width, x2 + padding)
    y2 = min(img.height, y2 + padding)
    
    return img.crop((x1, y1, x2, y2))


def image_to_base64(img: Image.Image, format: str = "PNG") -> str:
    """Convert PIL Image to base64 string."""
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def parse_vision_response(response_text: str) -> dict:
    """
    Parse Vision AI response to extract room ID and name.
    Expected format: "ID: xxx, NOM: yyy" or variations
    """
    result = {
        "id": None,
        "name": None,
        "raw_response": response_text
    }
    
    # Try various patterns
    patterns = [
        r"ID\s*[:=]\s*([A-Z]?-?\d+[A-Za-z]?)",
        r"Local\s+([A-Z]?-?\d+[A-Za-z]?)",
        r"([A-Z]-\d{3}[A-Za-z]?)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            result["id"] = match.group(1).upper()
            break
    
    # Extract name
    name_patterns = [
        r"NOM\s*[:=]\s*([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s'-]+)",
        r"(?:CLASSE|CORRIDOR|BUREAU|TOILETTE|RANGEMENT|SALLE)[S]?\s*([\w\s'-]*)",
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            name = match.group(0).strip()
            # Clean up
            name = re.sub(r"^NOM\s*[:=]\s*", "", name, flags=re.IGNORECASE)
            result["name"] = name.upper().strip()
            break
    
    # Common room names detection
    common_names = [
        "CLASSE", "CORRIDOR", "BUREAU", "TOILETTE", "TOILETTES",
        "RANGEMENT", "SALLE DE CLASSE", "CONCIERGERIE", "VESTIBULE",
        "GYMNASE", "BIBLIOTHÈQUE", "SECRÉTARIAT", "DIRECTION",
        "MÉCANIQUE", "ÉLECTRIQUE", "SALLE DES PROFESSEURS",
        "CUISINE", "CAFÉTÉRIA", "ESCALIER", "ASCENSEUR"
    ]
    
    if not result["name"]:
        for name in common_names:
            if name.lower() in response_text.lower():
                result["name"] = name
                break
    
    return result


def sniper_validate(room_id: str, plan_path: str, bbox: list, vision_callback=None) -> dict:
    """
    Validate a room using Vision AI on a cropped region.
    
    Args:
        room_id: Current room ID to validate
        plan_path: Path to the blueprint image
        bbox: Bounding box [x1, y1, x2, y2]
        vision_callback: Function to call Vision AI (receives base64 image, returns text)
    
    Returns:
        {
            confirmed: bool,
            corrected_id: str or None,
            corrected_name: str or None,
            confidence: float,
            validation_date: str,
            raw_response: str
        }
    """
    result = {
        "room_id": room_id,
        "plan_path": plan_path,
        "bbox": bbox,
        "confirmed": False,
        "corrected_id": None,
        "corrected_name": None,
        "confidence": 0.0,
        "validation_date": datetime.now().isoformat(),
        "raw_response": None,
        "error": None
    }
    
    try:
        # Load and crop image
        img = load_image(plan_path)
        cropped = crop_region(img, bbox, padding=80)
        
        # Save cropped image for debugging
        debug_dir = OUTPUT_DIR / "sniper_crops"
        debug_dir.mkdir(exist_ok=True)
        crop_filename = f"{room_id.replace('/', '_')}_crop.png"
        cropped.save(debug_dir / crop_filename)
        
        if vision_callback:
            # Get base64 image
            img_b64 = image_to_base64(cropped)
            
            # Call Vision AI
            prompt = f"""Examine this cropped section of an architectural floor plan.
What is the room number/ID and room name visible in this area?

Format your answer as:
ID: [room number]
NOM: [room name in French]

If you cannot clearly see a room number, say "ID: UNCLEAR"
Current expected ID: {room_id}"""
            
            response = vision_callback(img_b64, prompt)
            result["raw_response"] = response
            
            # Parse response
            parsed = parse_vision_response(response)
            
            if parsed["id"]:
                # Check if confirmed or corrected
                if parsed["id"].upper() == room_id.upper():
                    result["confirmed"] = True
                    result["confidence"] = 0.95
                else:
                    result["corrected_id"] = parsed["id"]
                    result["confidence"] = 0.85
                    
                if parsed["name"]:
                    result["corrected_name"] = parsed["name"]
            else:
                result["confidence"] = 0.3
                result["error"] = "Could not parse room ID from response"
        else:
            result["error"] = "No vision callback provided"
            
    except Exception as e:
        result["error"] = str(e)
        result["confidence"] = 0.0
    
    return result


def batch_validate(rooms: list, plans_mapping: dict, vision_callback=None, 
                   confidence_threshold: float = 0.75) -> list:
    """
    Batch validate all rooms below confidence threshold.
    
    Args:
        rooms: List of room dictionaries
        plans_mapping: Mapping of plan identifiers to file paths
        vision_callback: Vision AI callback function
        confidence_threshold: Only validate rooms below this threshold
    
    Returns:
        List of validation results
    """
    results = []
    
    for room in rooms:
        if room.get("confidence", 1.0) >= confidence_threshold:
            continue
        
        # Find the appropriate plan
        plan_path = None
        block = room.get("block", "")
        floor = room.get("floor", 1)
        
        # Try to find matching plan
        for plan_id, path in plans_mapping.items():
            if f"{block}-{floor}" in plan_id or f"finis-{floor}" in plan_id:
                plan_path = path
                break
        
        if not plan_path:
            results.append({
                "room_id": room["id"],
                "error": "No matching plan found",
                "confidence": room.get("confidence", 0.5)
            })
            continue
        
        bbox = room.get("bbox", [0, 0, 1000, 1000])
        
        result = sniper_validate(
            room_id=room["id"],
            plan_path=plan_path,
            bbox=bbox,
            vision_callback=vision_callback
        )
        
        results.append(result)
    
    return results


def update_rooms_with_validations(rooms_file: Path, validations: list) -> dict:
    """
    Update rooms_complete.json with validation results.
    """
    with open(rooms_file, 'r') as f:
        data = json.load(f)
    
    rooms = data.get("rooms", [])
    updates_count = 0
    
    for validation in validations:
        room_id = validation.get("room_id")
        
        for room in rooms:
            if room["id"] == room_id:
                if validation.get("confirmed"):
                    room["confidence"] = 0.95
                    room["validated_by"] = "sniper_vision"
                    room["validation_date"] = validation["validation_date"]
                    updates_count += 1
                elif validation.get("corrected_id"):
                    room["id"] = validation["corrected_id"]
                    if validation.get("corrected_name"):
                        room["name"] = validation["corrected_name"]
                    room["confidence"] = 0.90
                    room["validated_by"] = "sniper_vision_corrected"
                    room["validation_date"] = validation["validation_date"]
                    room["original_id"] = room_id
                    updates_count += 1
                break
    
    data["last_validation"] = datetime.now().isoformat()
    data["validation_stats"] = {
        "total_validated": len(validations),
        "updates_applied": updates_count
    }
    
    # Save updated data
    with open(rooms_file, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return data


def save_validation_log(results: list, log_file: Path = VALIDATION_LOG):
    """Save validation results to log file."""
    log_data = {
        "validation_date": datetime.now().isoformat(),
        "total_validated": len(results),
        "confirmed": sum(1 for r in results if r.get("confirmed")),
        "corrected": sum(1 for r in results if r.get("corrected_id")),
        "failed": sum(1 for r in results if r.get("error")),
        "results": results
    }
    
    with open(log_file, 'w') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)
    
    return log_data


def get_plans_mapping() -> dict:
    """Build mapping of plan identifiers to file paths."""
    mapping = {}
    
    # Architecture plans (main floor plans)
    arch_dir = PLANS_DIR / "architecture"
    if arch_dir.exists():
        for f in arch_dir.glob("*.png"):
            mapping[f.stem] = str(f)
    
    # Also check root level
    for f in PLANS_DIR.glob("*.png"):
        if "archi" in f.stem.lower() or "finis" in f.stem.lower():
            mapping[f.stem] = str(f)
    
    return mapping


# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Sniper Mode Room Validation")
    parser.add_argument("--room", help="Specific room ID to validate")
    parser.add_argument("--threshold", type=float, default=0.75, 
                        help="Confidence threshold for batch validation")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be validated without doing it")
    parser.add_argument("--list-low-confidence", action="store_true",
                        help="List all rooms below confidence threshold")
    
    args = parser.parse_args()
    
    # Load rooms
    with open(ROOMS_FILE, 'r') as f:
        data = json.load(f)
    rooms = data.get("rooms", [])
    
    if args.list_low_confidence:
        low_conf = [r for r in rooms if r.get("confidence", 1.0) < args.threshold]
        print(f"\nRooms with confidence < {args.threshold}:")
        print("-" * 50)
        for room in sorted(low_conf, key=lambda x: x.get("confidence", 0)):
            print(f"  {room['id']:10} | {room.get('name', 'N/A'):20} | conf: {room.get('confidence', 0):.2f}")
        print(f"\nTotal: {len(low_conf)} rooms need validation")
    
    elif args.dry_run:
        plans = get_plans_mapping()
        print(f"\nAvailable plans: {len(plans)}")
        for name, path in plans.items():
            print(f"  {name}: {path}")
        
        low_conf = [r for r in rooms if r.get("confidence", 1.0) < args.threshold]
        print(f"\n{len(low_conf)} rooms would be validated")
    
    else:
        print("Sniper validation requires Vision AI callback.")
        print("Use --list-low-confidence or --dry-run for testing.")
