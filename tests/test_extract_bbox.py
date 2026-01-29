#!/usr/bin/env python3
"""
Tests for extract_bbox.py — Room bounding box extraction.
"""

import json
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from extract_bbox import (
    load_rooms,
    get_room_patterns,
    extract_bbox_from_page,
    _fallback_bbox,
    extract_all_bboxes,
    update_rooms_with_bbox,
)


# ============== Fixtures ==============

@pytest.fixture
def rooms_json(tmp_path):
    rooms_data = {
        "rooms": [
            {"id": "A-101", "name": "CLASSE", "primary_source": 2, "page": 2},
            {"id": "A-102", "name": "CORRIDOR", "primary_source": 3, "page": 3},
            {"id": "B-201", "name": "GYMNASE", "primary_source": 5, "page": 5},
        ]
    }
    path = tmp_path / "rooms_complete.json"
    with open(path, "w") as f:
        json.dump(rooms_data, f)
    return path


@pytest.fixture
def rooms_data_dict():
    return {
        "rooms": [
            {"id": "A-101", "name": "CLASSE", "primary_source": 2},
            {"id": "A-102", "name": "CORRIDOR", "primary_source": 3},
        ]
    }


# ============== load_rooms ==============

class TestLoadRooms:
    def test_load(self, rooms_json):
        rooms = load_rooms(rooms_json)
        assert "A-101" in rooms
        assert "A-102" in rooms
        assert rooms["A-101"]["name"] == "CLASSE"

    def test_empty(self, tmp_path):
        path = tmp_path / "empty.json"
        with open(path, "w") as f:
            json.dump({"rooms": []}, f)
        rooms = load_rooms(path)
        assert rooms == {}


# ============== get_room_patterns ==============

class TestGetRoomPatterns:
    def test_returns_patterns(self):
        patterns = get_room_patterns()
        assert len(patterns) >= 2

    def test_matches_standard_ids(self):
        patterns = get_room_patterns()
        # Standard format: A-101
        text = "Local A-101 CLASSE"
        matches = []
        for p in patterns:
            matches.extend(p.findall(text))
        assert any("101" in m for m in matches)

    def test_matches_three_digits(self):
        patterns = get_room_patterns()
        text = "Room 205"
        matches = []
        for p in patterns:
            matches.extend(p.findall(text))
        assert any("205" in m for m in matches)


# ============== _fallback_bbox ==============

class TestFallbackBbox:
    def test_with_pil(self, tmp_path):
        """Test fallback creates generic bbox."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        # Create a simple test image
        img = Image.new("RGB", (1000, 800), "white")
        img_path = tmp_path / "page-002.png"
        img.save(img_path)

        result = _fallback_bbox(img_path, {"A-101", "A-102"}, 2)

        assert "A-101" in result
        assert "A-102" in result
        assert result["A-101"]["page"] == 2
        assert result["A-101"]["confidence"] == 0.1
        assert result["A-101"]["fallback"] is True
        assert len(result["A-101"]["bbox"]) == 4

    def test_empty_room_ids(self, tmp_path):
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img = Image.new("RGB", (500, 500), "white")
        img_path = tmp_path / "page.png"
        img.save(img_path)

        result = _fallback_bbox(img_path, set(), 1)
        assert result == {}


# ============== extract_bbox_from_page ==============

class TestExtractBboxFromPage:
    def test_without_dependencies(self, tmp_path):
        """When OCR not available, should fallback gracefully."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img = Image.new("RGB", (800, 600), "white")
        img_path = tmp_path / "page.png"
        img.save(img_path)

        # This should work even without tesseract (uses fallback)
        result = extract_bbox_from_page(img_path, {"A-101"}, 1)
        assert isinstance(result, dict)


# ============== extract_all_bboxes ==============

class TestExtractAllBboxes:
    def test_basic(self, tmp_path, rooms_json):
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        # Create page images
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()
        for i in [2, 3, 5]:
            img = Image.new("RGB", (500, 400), "white")
            img.save(pages_dir / f"page-{i:03d}.png")

        result = extract_all_bboxes(pages_dir, rooms_json)

        assert isinstance(result, dict)
        # All rooms should have entries (even fallback ones)
        assert "A-101" in result
        assert "A-102" in result
        assert "B-201" in result

    def test_save_output(self, tmp_path, rooms_json):
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()
        for i in [2, 3, 5]:
            img = Image.new("RGB", (500, 400), "white")
            img.save(pages_dir / f"page-{i:03d}.png")

        output_path = tmp_path / "bboxes.json"
        extract_all_bboxes(pages_dir, rooms_json, output_path)

        assert output_path.exists()
        with open(output_path) as f:
            data = json.load(f)
        assert "A-101" in data

    def test_no_pages(self, tmp_path, rooms_json):
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        pages_dir = tmp_path / "empty_pages"
        pages_dir.mkdir()

        result = extract_all_bboxes(pages_dir, rooms_json)
        # Should still have entries but all fallback
        assert all(r.get("confidence", 0) == 0 for r in result.values() if r.get("bbox") is None)


# ============== update_rooms_with_bbox ==============

class TestUpdateRoomsWithBbox:
    def test_update(self, tmp_path):
        rooms_data = {
            "rooms": [
                {"id": "A-101", "name": "CLASSE"},
                {"id": "A-102", "name": "CORRIDOR"},
            ]
        }
        rooms_path = tmp_path / "rooms.json"
        with open(rooms_path, "w") as f:
            json.dump(rooms_data, f)

        bbox_data = {
            "A-101": {"bbox": [10, 20, 200, 300], "confidence": 0.9},
            "A-102": {"bbox": [50, 60, 400, 500], "confidence": 0.85},
        }
        bbox_path = tmp_path / "bboxes.json"
        with open(bbox_path, "w") as f:
            json.dump(bbox_data, f)

        update_rooms_with_bbox(rooms_path, bbox_path)

        with open(rooms_path) as f:
            updated = json.load(f)

        assert updated["rooms"][0]["bbox"] == [10, 20, 200, 300]
        assert updated["rooms"][0]["bbox_confidence"] == 0.9
        assert updated["rooms"][1]["bbox"] == [50, 60, 400, 500]

    def test_update_separate_output(self, tmp_path):
        rooms_path = tmp_path / "rooms.json"
        with open(rooms_path, "w") as f:
            json.dump({"rooms": [{"id": "A-101"}]}, f)

        bbox_path = tmp_path / "bboxes.json"
        with open(bbox_path, "w") as f:
            json.dump({"A-101": {"bbox": [0, 0, 100, 100], "confidence": 0.5}}, f)

        output_path = tmp_path / "output_rooms.json"
        update_rooms_with_bbox(rooms_path, bbox_path, output_path)

        assert output_path.exists()
        with open(output_path) as f:
            data = json.load(f)
        assert data["rooms"][0]["bbox"] == [0, 0, 100, 100]
