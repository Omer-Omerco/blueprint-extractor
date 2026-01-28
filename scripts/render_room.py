#!/usr/bin/env python3
"""
Render room visualizations from blueprint pages.

Provides functions to:
- Highlight a room on its page (red overlay)
- Crop a room from its page
- Generate a room info card with specs

Falls back gracefully when bbox data is unavailable.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.error("Pillow is required for rendering. Install with: pip install Pillow")


def load_room_data(output_dir: Path) -> tuple[dict, dict]:
    """
    Load room and bbox data from output directory.
    
    Returns:
        Tuple of (rooms_by_id, bboxes_by_id)
    """
    rooms_path = output_dir / 'rooms_complete.json'
    bbox_path = output_dir / 'room_bboxes.json'
    
    rooms_by_id = {}
    bboxes_by_id = {}
    
    if rooms_path.exists():
        with open(rooms_path) as f:
            data = json.load(f)
            rooms_by_id = {r['id']: r for r in data.get('rooms', [])}
    
    if bbox_path.exists():
        with open(bbox_path) as f:
            bboxes_by_id = json.load(f)
    
    return rooms_by_id, bboxes_by_id


def get_page_path(page_num: int, pages_dir: Path) -> Optional[Path]:
    """Get path to a page image."""
    page_path = pages_dir / f'page-{page_num:03d}.png'
    if page_path.exists():
        return page_path
    
    # Try alternative naming
    alt_path = pages_dir / f'page_{page_num:03d}.png'
    if alt_path.exists():
        return alt_path
    
    return None


def render_room(
    room_id: str,
    output_dir: str = "output",
    highlight_color: tuple = (255, 0, 0, 100),
    border_width: int = 4
) -> str:
    """
    Generate image with room highlighted in red.
    
    Args:
        room_id: Room identifier (e.g., "A-204")
        output_dir: Base output directory
        highlight_color: RGBA tuple for highlight fill
        border_width: Width of highlight border
        
    Returns:
        Path to generated PNG file
        
    Raises:
        ValueError: If room not found
        RuntimeError: If Pillow not available
    """
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow is required for rendering")
    
    output_path = Path(output_dir)
    rooms, bboxes = load_room_data(output_path)
    
    if room_id not in rooms:
        raise ValueError(f"Room {room_id} not found in rooms_complete.json")
    
    room = rooms[room_id]
    bbox_info = bboxes.get(room_id, {})
    
    # Get page number
    page_num = room.get('primary_source') or room.get('page') or (room.get('pages', [None])[0])
    if not page_num:
        raise ValueError(f"No page number found for room {room_id}")
    
    # Load page image
    pages_dir = output_path / 'pages'
    page_path = get_page_path(page_num, pages_dir)
    if not page_path:
        raise ValueError(f"Page {page_num} not found in {pages_dir}")
    
    img = Image.open(page_path).convert('RGBA')
    
    # Create highlight overlay
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    bbox = bbox_info.get('bbox') if bbox_info else None
    
    if bbox:
        x1, y1, x2, y2 = bbox
        # Draw filled rectangle with transparency
        draw.rectangle([x1, y1, x2, y2], fill=highlight_color)
        # Draw solid border
        border_color = (255, 0, 0, 255)
        for i in range(border_width):
            draw.rectangle([x1-i, y1-i, x2+i, y2+i], outline=border_color)
    else:
        # Fallback: add title banner at top
        logger.warning(f"bbox non disponible pour {room_id} - affichage page complète")
        _add_title_banner(draw, img.size, room_id, room.get('name', ''))
    
    # Composite overlay onto image
    result = Image.alpha_composite(img, overlay)
    
    # Ensure renders directory exists
    renders_dir = output_path / 'renders'
    renders_dir.mkdir(parents=True, exist_ok=True)
    
    # Save result
    result_path = renders_dir / f'{room_id}_highlight.png'
    result.convert('RGB').save(result_path, 'PNG')
    
    logger.info(f"Generated highlight: {result_path}")
    return str(result_path)


def crop_room(
    room_id: str,
    output_dir: str = "output",
    padding: int = 50
) -> str:
    """
    Crop and return the room area from its page.
    
    Args:
        room_id: Room identifier (e.g., "A-204")
        output_dir: Base output directory
        padding: Pixels to add around the bbox
        
    Returns:
        Path to cropped PNG file
        
    Raises:
        ValueError: If room not found or no bbox available
        RuntimeError: If Pillow not available
    """
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow is required for rendering")
    
    output_path = Path(output_dir)
    rooms, bboxes = load_room_data(output_path)
    
    if room_id not in rooms:
        raise ValueError(f"Room {room_id} not found in rooms_complete.json")
    
    room = rooms[room_id]
    bbox_info = bboxes.get(room_id, {})
    bbox = bbox_info.get('bbox') if bbox_info else None
    
    # Get page
    page_num = room.get('primary_source') or room.get('page') or (room.get('pages', [None])[0])
    if not page_num:
        raise ValueError(f"No page number found for room {room_id}")
    
    pages_dir = output_path / 'pages'
    page_path = get_page_path(page_num, pages_dir)
    if not page_path:
        raise ValueError(f"Page {page_num} not found")
    
    img = Image.open(page_path)
    width, height = img.size
    
    if bbox:
        x1, y1, x2, y2 = bbox
        # Add padding
        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(width, x2 + padding)
        y2 = min(height, y2 + padding)
        cropped = img.crop((x1, y1, x2, y2))
    else:
        # Fallback: return full page with title
        logger.warning(f"bbox non disponible pour {room_id} - retournant page complète")
        cropped = img.copy()
        draw = ImageDraw.Draw(cropped)
        _add_title_banner(draw, cropped.size, room_id, room.get('name', ''))
    
    # Ensure renders directory exists
    renders_dir = output_path / 'renders'
    renders_dir.mkdir(parents=True, exist_ok=True)
    
    # Save result
    result_path = renders_dir / f'{room_id}_crop.png'
    cropped.save(result_path, 'PNG')
    
    logger.info(f"Generated crop: {result_path}")
    return str(result_path)


def render_room_card(
    room_id: str,
    output_dir: str = "output"
) -> str:
    """
    Generate a room info card with image and specs.
    
    The card includes:
    - Cropped room image (or full page fallback)
    - Room ID and name
    - Floor and block info
    - Any available specs from devis
    
    Args:
        room_id: Room identifier (e.g., "A-204")
        output_dir: Base output directory
        
    Returns:
        Path to generated card PNG
        
    Raises:
        ValueError: If room not found
        RuntimeError: If Pillow not available
    """
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow is required for rendering")
    
    output_path = Path(output_dir)
    rooms, bboxes = load_room_data(output_path)
    
    if room_id not in rooms:
        raise ValueError(f"Room {room_id} not found in rooms_complete.json")
    
    room = rooms[room_id]
    
    # Card dimensions
    card_width = 800
    card_height = 1000
    header_height = 150
    image_height = 500
    specs_height = card_height - header_height - image_height
    
    # Create card
    card = Image.new('RGB', (card_width, card_height), (255, 255, 255))
    draw = ImageDraw.Draw(card)
    
    # Try to load fonts
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        subtitle_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
        body_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except Exception:
        title_font = ImageFont.load_default()
        subtitle_font = title_font
        body_font = title_font
    
    # Header background
    draw.rectangle([0, 0, card_width, header_height], fill=(41, 128, 185))
    
    # Title
    title = f"{room_id}"
    draw.text((30, 30), title, fill=(255, 255, 255), font=title_font)
    
    # Subtitle (room name)
    subtitle = room.get('name', 'UNKNOWN')
    draw.text((30, 90), subtitle, fill=(220, 220, 220), font=subtitle_font)
    
    # Room image
    try:
        crop_path = crop_room(room_id, output_dir, padding=30)
        room_img = Image.open(crop_path)
        
        # Resize to fit
        room_img.thumbnail((card_width - 40, image_height - 40), Image.Resampling.LANCZOS)
        
        # Center image
        img_x = (card_width - room_img.width) // 2
        img_y = header_height + 20
        
        card.paste(room_img, (img_x, img_y))
    except Exception as e:
        logger.warning(f"Could not load room image: {e}")
        # Draw placeholder
        draw.rectangle(
            [20, header_height + 20, card_width - 20, header_height + image_height - 20],
            outline=(200, 200, 200),
            width=2
        )
        draw.text(
            (card_width // 2 - 100, header_height + image_height // 2),
            "Image non disponible",
            fill=(150, 150, 150),
            font=body_font
        )
    
    # Specs section
    specs_y = header_height + image_height + 20
    draw.line([20, specs_y - 10, card_width - 20, specs_y - 10], fill=(200, 200, 200), width=2)
    
    specs = [
        f"Bloc: {room.get('block', 'N/A')}",
        f"Étage: {room.get('floor', 'N/A')}",
        f"Page source: {room.get('primary_source', 'N/A')}",
        f"Confiance: {room.get('confidence', 0):.0%}",
    ]
    
    # Add dimensions if available
    if 'dimensions' in room:
        specs.append(f"Dimensions: {room['dimensions']}")
    if 'area_sqft' in room:
        specs.append(f"Superficie: {room['area_sqft']} pi²")
    
    for i, spec in enumerate(specs):
        draw.text((30, specs_y + i * 35), spec, fill=(50, 50, 50), font=body_font)
    
    # Ensure renders directory exists
    renders_dir = output_path / 'renders'
    renders_dir.mkdir(parents=True, exist_ok=True)
    
    # Save card
    result_path = renders_dir / f'{room_id}_card.png'
    card.save(result_path, 'PNG')
    
    logger.info(f"Generated card: {result_path}")
    return str(result_path)


def render_floor(
    block: str,
    floor: int,
    output_dir: str = "output"
) -> str:
    """
    Render all rooms on a floor with highlights.
    
    Args:
        block: Building block (A, B, C)
        floor: Floor number
        output_dir: Base output directory
        
    Returns:
        Path to generated PNG
    """
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow is required for rendering")
    
    output_path = Path(output_dir)
    rooms, bboxes = load_room_data(output_path)
    
    # Filter rooms for this floor
    floor_rooms = [
        r for r in rooms.values()
        if r.get('block') == block and r.get('floor') == floor
    ]
    
    if not floor_rooms:
        raise ValueError(f"No rooms found for block {block}, floor {floor}")
    
    # Find the primary page for this floor
    page_counts: dict[int, int] = {}
    for room in floor_rooms:
        page = room.get('primary_source') or room.get('page')
        if page:
            page_counts[page] = page_counts.get(page, 0) + 1
    
    if not page_counts:
        raise ValueError("No page data for floor rooms")
    
    primary_page = max(page_counts, key=page_counts.get)
    
    # Load page
    pages_dir = output_path / 'pages'
    page_path = get_page_path(primary_page, pages_dir)
    if not page_path:
        raise ValueError(f"Page {primary_page} not found")
    
    img = Image.open(page_path).convert('RGBA')
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Colors for different rooms
    colors = [
        (255, 0, 0, 80),    # Red
        (0, 255, 0, 80),    # Green
        (0, 0, 255, 80),    # Blue
        (255, 255, 0, 80),  # Yellow
        (255, 0, 255, 80),  # Magenta
        (0, 255, 255, 80),  # Cyan
    ]
    
    for i, room in enumerate(floor_rooms):
        room_id = room['id']
        bbox_info = bboxes.get(room_id, {})
        bbox = bbox_info.get('bbox')
        
        if bbox:
            color = colors[i % len(colors)]
            x1, y1, x2, y2 = bbox
            draw.rectangle([x1, y1, x2, y2], fill=color)
            draw.rectangle([x1, y1, x2, y2], outline=(0, 0, 0, 255), width=2)
            
            # Add room ID label
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
            except Exception:
                font = ImageFont.load_default()
            draw.text((x1 + 5, y1 + 5), room_id, fill=(0, 0, 0, 255), font=font)
    
    # Composite
    result = Image.alpha_composite(img, overlay)
    
    # Ensure renders directory exists
    renders_dir = output_path / 'renders'
    renders_dir.mkdir(parents=True, exist_ok=True)
    
    # Save
    result_path = renders_dir / f'floor_{block}{floor}.png'
    result.convert('RGB').save(result_path, 'PNG')
    
    logger.info(f"Generated floor view: {result_path}")
    return str(result_path)


def _add_title_banner(
    draw: ImageDraw.Draw,
    size: tuple[int, int],
    room_id: str,
    room_name: str
) -> None:
    """Add a title banner to indicate which room we're showing."""
    width, height = size
    banner_height = 80
    
    # Draw banner background
    draw.rectangle([0, 0, width, banner_height], fill=(41, 128, 185, 230))
    
    # Try to load font
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    except Exception:
        font = ImageFont.load_default()
    
    # Draw text
    text = f"{room_id} - {room_name}"
    draw.text((20, 20), text, fill=(255, 255, 255, 255), font=font)
    
    # Warning text
    try:
        small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    except Exception:
        small_font = font
    
    warning = "⚠️ bbox non disponible - page complète affichée"
    draw.text((width - 400, 25), warning, fill=(255, 200, 100, 255), font=small_font)


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Render room visualizations from blueprints',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python render_room.py A-204 --mode highlight
  python render_room.py A-204 --mode crop --padding 100
  python render_room.py A-204 --mode card
  python render_room.py --floor A 1  # Render all rooms on floor A-1
        """
    )
    
    parser.add_argument('room_id', nargs='?', help='Room ID (e.g., A-204)')
    parser.add_argument('--mode', choices=['highlight', 'crop', 'card'],
                        default='highlight', help='Render mode')
    parser.add_argument('--output-dir', '-o', type=str, default='output',
                        help='Output directory')
    parser.add_argument('--padding', type=int, default=50,
                        help='Padding for crop mode')
    parser.add_argument('--floor', nargs=2, metavar=('BLOCK', 'FLOOR'),
                        help='Render entire floor (block and floor number)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        if args.floor:
            block, floor = args.floor
            result = render_floor(block, int(floor), args.output_dir)
        elif args.room_id:
            if args.mode == 'highlight':
                result = render_room(args.room_id, args.output_dir)
            elif args.mode == 'crop':
                result = crop_room(args.room_id, args.output_dir, args.padding)
            elif args.mode == 'card':
                result = render_room_card(args.room_id, args.output_dir)
        else:
            parser.print_help()
            sys.exit(1)
        
        print(f"Generated: {result}")
        
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
