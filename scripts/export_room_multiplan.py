#!/usr/bin/env python3
"""
Multi-Plan Room Export - Génère une fiche complète pour un local avec tous ses plans.

Usage:
    python3 scripts/export_room_multiplan.py A-204
    python3 scripts/export_room_multiplan.py --all-bloc A
    python3 scripts/export_room_multiplan.py A-204 --output-dir output/exports
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.error("Pillow is required. Install with: pip install Pillow")

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
PLANS_DIR = Path("/Users/omer/clawd/projects/ecole-enfants-jesus/visual-analysis")

# Discipline colors for headers
DISCIPLINE_COLORS = {
    "architecture": (66, 133, 244),   # Blue
    "mecanique": (234, 67, 53),       # Red  
    "electrique": (251, 188, 5),      # Yellow/Orange
    "structure": (52, 168, 83),       # Green
    "gicleurs": (154, 160, 166),      # Gray
    "civil": (103, 58, 183),          # Purple
}

DISCIPLINE_LABELS = {
    "architecture": "ARCHITECTURE",
    "mecanique": "MÉCANIQUE",
    "electrique": "ÉLECTRIQUE",
    "structure": "STRUCTURE",
    "gicleurs": "GICLEURS",
    "civil": "CIVIL",
}


def load_data() -> tuple[dict, dict]:
    """Load rooms and bbox data."""
    rooms_path = OUTPUT_DIR / "rooms_complete.json"
    bbox_path = OUTPUT_DIR / "bboxes_by_plan.json"
    
    rooms_by_id = {}
    bboxes_by_plan = {}
    
    if rooms_path.exists():
        with open(rooms_path) as f:
            data = json.load(f)
            rooms_by_id = {r['id']: r for r in data.get('rooms', [])}
    
    if bbox_path.exists():
        with open(bbox_path) as f:
            bboxes_by_plan = json.load(f).get('plans', {})
    
    return rooms_by_id, bboxes_by_plan


def find_room_on_plans(room_id: str, bboxes_by_plan: dict) -> dict:
    """
    Find all plans where this room appears.
    
    Returns dict: {plan_path: {"bbox": [...], "name": ..., "confidence": ...}}
    """
    found = {}
    
    for plan_path, plan_data in bboxes_by_plan.items():
        locaux = plan_data.get('locaux', {})
        if room_id in locaux:
            found[plan_path] = {
                **locaux[room_id],
                "plan_description": plan_data.get('description', ''),
                "etage": plan_data.get('etage', ''),
                "bloc": plan_data.get('bloc', ''),
            }
    
    return found


def get_discipline_from_path(plan_path: str) -> str:
    """Extract discipline from plan path (architecture/A-1.png -> architecture)."""
    parts = plan_path.split('/')
    if len(parts) >= 2:
        return parts[0].lower()
    return "autre"


def crop_room_from_plan(plan_path: str, bbox: list, padding: int = 50) -> Optional[Image.Image]:
    """
    Crop a room from a plan image with padding.
    
    Args:
        plan_path: Relative path like "architecture/A-1.png"
        bbox: [x1, y1, x2, y2] coordinates
        padding: Extra pixels around the bbox
        
    Returns:
        PIL Image of the cropped area
    """
    full_path = PLANS_DIR / plan_path
    
    if not full_path.exists():
        logger.warning(f"Plan not found: {full_path}")
        return None
    
    try:
        img = Image.open(full_path)
        x1, y1, x2, y2 = bbox
        
        # Add padding, clamped to image bounds
        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(img.width, x2 + padding)
        y2 = min(img.height, y2 + padding)
        
        return img.crop((x1, y1, x2, y2))
    except Exception as e:
        logger.error(f"Error cropping {plan_path}: {e}")
        return None


def get_font(size: int = 24) -> ImageFont.FreeTypeFont:
    """Get a font, falling back to default if needed."""
    try:
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
    except:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except:
            return ImageFont.load_default()


def create_header_image(room_id: str, room_info: dict, width: int = 1200) -> Image.Image:
    """Create a header image with room info."""
    height = 120
    header = Image.new('RGB', (width, height), (30, 30, 30))
    draw = ImageDraw.Draw(header)
    
    # Fonts
    font_title = get_font(36)
    font_subtitle = get_font(20)
    
    # Room ID and name
    room_name = room_info.get('name', 'N/A')
    block = room_info.get('block', 'N/A')
    floor = room_info.get('floor', 'N/A')
    
    title = f"{room_id} — {room_name}"
    subtitle = f"Bloc {block} | Étage {floor}"
    
    # Draw title
    draw.text((20, 20), title, fill=(255, 255, 255), font=font_title)
    draw.text((20, 70), subtitle, fill=(180, 180, 180), font=font_subtitle)
    
    return header


def create_discipline_header(discipline: str, plan_info: dict, width: int) -> Image.Image:
    """Create a discipline section header."""
    height = 50
    color = DISCIPLINE_COLORS.get(discipline, (128, 128, 128))
    header = Image.new('RGB', (width, height), color)
    draw = ImageDraw.Draw(header)
    
    font = get_font(18)
    label = DISCIPLINE_LABELS.get(discipline, discipline.upper())
    plan_desc = plan_info.get('plan_description', '')
    
    text = f"{label}"
    if plan_desc:
        text += f" — {plan_desc}"
    
    draw.text((15, 12), text, fill=(255, 255, 255), font=font)
    
    return header


def export_room_multiplan(
    room_id: str, 
    output_dir: str = "output/exports",
    target_crop_width: int = 1200
) -> dict:
    """
    Génère une fiche complète pour un local avec tous ses plans.
    
    Args:
        room_id: Identifiant du local (e.g., "A-204")
        output_dir: Répertoire de sortie
        target_crop_width: Largeur cible pour les crops
        
    Returns:
        {
            "room_id": str,
            "room_info": dict,
            "plans_found": ["architecture/A-1.png", ...],
            "export_path": "output/exports/A-204_multiplan.png"
        }
    """
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow is required for this operation")
    
    # Load data
    rooms_by_id, bboxes_by_plan = load_data()
    
    # Get room info
    room_info = rooms_by_id.get(room_id, {})
    if not room_info:
        logger.warning(f"Room {room_id} not found in rooms_complete.json, using defaults")
        room_info = {"id": room_id, "name": "N/A", "block": room_id[0] if room_id else "?", "floor": "?"}
    
    # Find room on all plans
    plans_found = find_room_on_plans(room_id, bboxes_by_plan)
    
    if not plans_found:
        logger.error(f"Room {room_id} not found on any plan in bboxes_by_plan.json")
        return {
            "room_id": room_id,
            "room_info": room_info,
            "plans_found": [],
            "export_path": None,
            "error": "Room not found on any plan"
        }
    
    logger.info(f"Found {room_id} on {len(plans_found)} plans: {list(plans_found.keys())}")
    
    # Group by discipline
    by_discipline = {}
    for plan_path, info in plans_found.items():
        discipline = get_discipline_from_path(plan_path)
        if discipline not in by_discipline:
            by_discipline[discipline] = []
        by_discipline[discipline].append((plan_path, info))
    
    # Create crops for each discipline
    sections = []
    
    # Define discipline order
    discipline_order = ['architecture', 'mecanique', 'electrique', 'structure', 'gicleurs', 'civil']
    
    for discipline in discipline_order:
        if discipline not in by_discipline:
            continue
            
        for plan_path, plan_info in by_discipline[discipline]:
            bbox = plan_info.get('bbox')
            if not bbox:
                continue
            
            crop = crop_room_from_plan(plan_path, bbox, padding=80)
            if crop:
                # Scale crop to target width
                ratio = target_crop_width / crop.width
                new_height = int(crop.height * ratio)
                crop = crop.resize((target_crop_width, new_height), Image.Resampling.LANCZOS)
                
                sections.append({
                    'discipline': discipline,
                    'plan_path': plan_path,
                    'plan_info': plan_info,
                    'crop': crop
                })
    
    if not sections:
        logger.error(f"No valid crops generated for {room_id}")
        return {
            "room_id": room_id,
            "room_info": room_info,
            "plans_found": list(plans_found.keys()),
            "export_path": None,
            "error": "No valid crops could be generated"
        }
    
    # Calculate total height
    header_height = 120
    discipline_header_height = 50
    padding = 10
    
    total_height = header_height + padding
    for section in sections:
        total_height += discipline_header_height + section['crop'].height + padding
    
    # Create composite image
    composite = Image.new('RGB', (target_crop_width, total_height), (245, 245, 245))
    
    # Add main header
    main_header = create_header_image(room_id, room_info, target_crop_width)
    composite.paste(main_header, (0, 0))
    
    # Add sections
    y_offset = header_height + padding
    
    for section in sections:
        # Discipline header
        disc_header = create_discipline_header(
            section['discipline'], 
            section['plan_info'],
            target_crop_width
        )
        composite.paste(disc_header, (0, y_offset))
        y_offset += discipline_header_height
        
        # Crop
        composite.paste(section['crop'], (0, y_offset))
        y_offset += section['crop'].height + padding
    
    # Save
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    export_file = output_path / f"{room_id}_multiplan.png"
    composite.save(export_file, 'PNG')
    
    logger.info(f"✅ Exported: {export_file}")
    
    return {
        "room_id": room_id,
        "room_info": room_info,
        "plans_found": list(plans_found.keys()),
        "export_path": str(export_file)
    }


def export_bloc_rooms(bloc: str, output_dir: str = "output/exports") -> list:
    """Export all rooms in a bloc."""
    rooms_by_id, bboxes_by_plan = load_data()
    
    results = []
    bloc_rooms = [r for r in rooms_by_id.values() if r.get('block') == bloc]
    
    logger.info(f"Found {len(bloc_rooms)} rooms in bloc {bloc}")
    
    for room in sorted(bloc_rooms, key=lambda r: r['id']):
        result = export_room_multiplan(room['id'], output_dir)
        results.append(result)
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Export multi-plan room sheets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 scripts/export_room_multiplan.py A-204
    python3 scripts/export_room_multiplan.py --all-bloc A
    python3 scripts/export_room_multiplan.py A-204 --output-dir output/exports
        """
    )
    
    parser.add_argument('room_id', nargs='?', help='Room ID to export (e.g., A-204)')
    parser.add_argument('--all-bloc', metavar='BLOC', help='Export all rooms in bloc (e.g., A, B, C)')
    parser.add_argument('--output-dir', default='output/exports', help='Output directory')
    parser.add_argument('--list-plans', action='store_true', help='List available plans')
    
    args = parser.parse_args()
    
    if args.list_plans:
        _, bboxes = load_data()
        print("Available plans:")
        for plan in sorted(bboxes.keys()):
            info = bboxes[plan]
            count = len(info.get('locaux', {}))
            print(f"  {plan}: {count} locaux")
        return 0
    
    if args.all_bloc:
        results = export_bloc_rooms(args.all_bloc, args.output_dir)
        successful = [r for r in results if r.get('export_path')]
        print(f"\n✅ Exported {len(successful)}/{len(results)} rooms from bloc {args.all_bloc}")
        return 0
    
    if not args.room_id:
        parser.print_help()
        return 1
    
    result = export_room_multiplan(args.room_id, args.output_dir)
    
    if result.get('export_path'):
        print(f"\n✅ Export successful: {result['export_path']}")
        print(f"   Plans found: {', '.join(result['plans_found'])}")
        return 0
    else:
        print(f"\n❌ Export failed: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
