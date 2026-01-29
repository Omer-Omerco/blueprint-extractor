#!/usr/bin/env python3
"""
Tests for render_room.py — Room visualization rendering.
"""

import json
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


# ============== Fixtures ==============

@pytest.fixture
def output_dir(tmp_path):
    """Create a mock output directory structure."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow not installed")

    # Create directories
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    renders_dir = tmp_path / "renders"
    renders_dir.mkdir()

    # Create page images
    for i in [2, 3, 5]:
        img = Image.new("RGB", (800, 600), "white")
        img.save(pages_dir / f"page-{i:03d}.png")

    # Create rooms_complete.json
    rooms_data = {
        "rooms": [
            {
                "id": "A-101",
                "name": "CLASSE",
                "primary_source": 2,
                "page": 2,
                "block": "A",
                "floor": 1,
                "confidence": 0.95,
            },
            {
                "id": "A-102",
                "name": "CORRIDOR",
                "primary_source": 3,
                "page": 3,
                "block": "A",
                "floor": 1,
                "confidence": 0.88,
                "dimensions": "25'-6\" x 8'-0\"",
                "area_sqft": 204,
            },
            {
                "id": "B-201",
                "name": "GYMNASE",
                "primary_source": 5,
                "page": 5,
                "block": "B",
                "floor": 2,
                "confidence": 0.90,
            },
        ]
    }
    with open(tmp_path / "rooms_complete.json", "w") as f:
        json.dump(rooms_data, f)

    # Create room_bboxes.json
    bboxes = {
        "A-101": {"bbox": [100, 100, 400, 350], "confidence": 0.9},
        "A-102": {"bbox": [50, 50, 750, 550], "confidence": 0.85},
        # B-201 has no bbox intentionally
    }
    with open(tmp_path / "room_bboxes.json", "w") as f:
        json.dump(bboxes, f)

    return tmp_path


# ============== Import after fixture to allow skip ==============

def _import_render_room():
    from render_room import (
        load_room_data,
        get_page_path,
        render_room,
        crop_room,
        render_room_card,
        render_floor,
    )
    return load_room_data, get_page_path, render_room, crop_room, render_room_card, render_floor


# ============== load_room_data ==============

class TestLoadRoomData:
    def test_load(self, output_dir):
        load_room_data, *_ = _import_render_room()
        rooms, bboxes = load_room_data(output_dir)
        assert "A-101" in rooms
        assert "A-102" in rooms
        assert "A-101" in bboxes
        assert bboxes["A-101"]["bbox"] == [100, 100, 400, 350]

    def test_missing_files(self, tmp_path):
        load_room_data, *_ = _import_render_room()
        rooms, bboxes = load_room_data(tmp_path)
        assert rooms == {}
        assert bboxes == {}


# ============== get_page_path ==============

class TestGetPagePath:
    def test_standard_naming(self, output_dir):
        _, get_page_path, *_ = _import_render_room()
        path = get_page_path(2, output_dir / "pages")
        assert path is not None
        assert path.exists()

    def test_nonexistent(self, output_dir):
        _, get_page_path, *_ = _import_render_room()
        path = get_page_path(99, output_dir / "pages")
        assert path is None


# ============== render_room ==============

class TestRenderRoom:
    def test_with_bbox(self, output_dir):
        *_, render_room_fn, _, _, _ = _import_render_room()
        result = render_room_fn("A-101", str(output_dir))
        assert Path(result).exists()
        assert "highlight" in result

    def test_without_bbox_fallback(self, output_dir):
        *_, render_room_fn, _, _, _ = _import_render_room()
        # B-201 has no bbox
        result = render_room_fn("B-201", str(output_dir))
        assert Path(result).exists()

    def test_unknown_room(self, output_dir):
        *_, render_room_fn, _, _, _ = _import_render_room()
        with pytest.raises(ValueError, match="not found"):
            render_room_fn("Z-999", str(output_dir))


# ============== crop_room ==============

class TestCropRoom:
    def test_with_bbox(self, output_dir):
        *_, _, crop_room_fn, _, _ = _import_render_room()
        result = crop_room_fn("A-101", str(output_dir))
        assert Path(result).exists()
        assert "crop" in result

    def test_without_bbox_fallback(self, output_dir):
        *_, _, crop_room_fn, _, _ = _import_render_room()
        result = crop_room_fn("B-201", str(output_dir))
        assert Path(result).exists()

    def test_custom_padding(self, output_dir):
        *_, _, crop_room_fn, _, _ = _import_render_room()
        result = crop_room_fn("A-101", str(output_dir), padding=100)
        assert Path(result).exists()

    def test_unknown_room(self, output_dir):
        *_, _, crop_room_fn, _, _ = _import_render_room()
        with pytest.raises(ValueError, match="not found"):
            crop_room_fn("Z-999", str(output_dir))


# ============== render_room_card ==============

class TestRenderRoomCard:
    def test_card_generation(self, output_dir):
        *_, _, _, card_fn, _ = _import_render_room()
        result = card_fn("A-102", str(output_dir))
        assert Path(result).exists()
        assert "card" in result

    def test_unknown_room(self, output_dir):
        *_, _, _, card_fn, _ = _import_render_room()
        with pytest.raises(ValueError, match="not found"):
            card_fn("Z-999", str(output_dir))


# ============== render_floor ==============

class TestRenderFloor:
    def test_floor_render(self, output_dir):
        *_, floor_fn = _import_render_room()
        result = floor_fn("A", 1, str(output_dir))
        assert Path(result).exists()
        assert "floor" in result

    def test_unknown_floor(self, output_dir):
        *_, floor_fn = _import_render_room()
        with pytest.raises(ValueError, match="No rooms found"):
            floor_fn("Z", 99, str(output_dir))
