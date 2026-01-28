#!/usr/bin/env python3
"""
Tests for render_room.py

Tests rendering functions including:
- render_room() generates valid PNG
- crop_room() generates crop of correct size
- Room not found errors
- Fallback behavior when bbox unavailable
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


class TestRenderRoom:
    """Tests for render_room function."""
    
    @pytest.fixture
    def mock_output_dir(self, tmp_path):
        """Create a mock output directory with test data."""
        # Create directory structure
        pages_dir = tmp_path / 'pages'
        pages_dir.mkdir()
        renders_dir = tmp_path / 'renders'
        renders_dir.mkdir()
        
        # Create a simple test image (100x100 white PNG)
        try:
            from PIL import Image
            img = Image.new('RGB', (100, 100), (255, 255, 255))
            img.save(pages_dir / 'page-004.png', 'PNG')
        except ImportError:
            pytest.skip("Pillow not installed")
        
        # Create rooms_complete.json
        rooms_data = {
            "project": {"name": "Test Project"},
            "rooms": [
                {
                    "id": "A-101",
                    "name": "CLASSE",
                    "floor": 1,
                    "block": "A",
                    "primary_source": 4,
                    "confidence": 0.9
                },
                {
                    "id": "A-102",
                    "name": "CORRIDOR",
                    "floor": 1,
                    "block": "A",
                    "primary_source": 4,
                    "confidence": 0.8
                }
            ]
        }
        with open(tmp_path / 'rooms_complete.json', 'w') as f:
            json.dump(rooms_data, f)
        
        # Create room_bboxes.json
        bboxes = {
            "A-101": {
                "page": 4,
                "bbox": [10, 10, 50, 50],
                "confidence": 0.85
            }
            # A-102 has no bbox - tests fallback
        }
        with open(tmp_path / 'room_bboxes.json', 'w') as f:
            json.dump(bboxes, f)
        
        return tmp_path
    
    def test_render_room_with_bbox(self, mock_output_dir):
        """Test render_room generates valid PNG when bbox available."""
        try:
            from render_room import render_room, PIL_AVAILABLE
            if not PIL_AVAILABLE:
                pytest.skip("Pillow not installed")
        except ImportError:
            pytest.skip("render_room not importable")
        
        result = render_room("A-101", str(mock_output_dir))
        
        # Check file was created
        assert result.endswith('.png')
        assert Path(result).exists()
        
        # Verify it's a valid PNG
        from PIL import Image
        img = Image.open(result)
        assert img.format == 'PNG'
        assert img.size == (100, 100)  # Same as source
    
    def test_render_room_fallback_no_bbox(self, mock_output_dir):
        """Test render_room falls back gracefully when no bbox."""
        try:
            from render_room import render_room, PIL_AVAILABLE
            if not PIL_AVAILABLE:
                pytest.skip("Pillow not installed")
        except ImportError:
            pytest.skip("render_room not importable")
        
        # A-102 has no bbox in our test data
        result = render_room("A-102", str(mock_output_dir))
        
        # Should still generate an image
        assert Path(result).exists()
        
        from PIL import Image
        img = Image.open(result)
        assert img.format == 'PNG'
    
    def test_render_room_invalid_id(self, mock_output_dir):
        """Test render_room raises ValueError for invalid room ID."""
        try:
            from render_room import render_room, PIL_AVAILABLE
            if not PIL_AVAILABLE:
                pytest.skip("Pillow not installed")
        except ImportError:
            pytest.skip("render_room not importable")
        
        with pytest.raises(ValueError, match="not found"):
            render_room("Z-999", str(mock_output_dir))


class TestCropRoom:
    """Tests for crop_room function."""
    
    @pytest.fixture
    def mock_output_dir(self, tmp_path):
        """Create a mock output directory with larger test image."""
        pages_dir = tmp_path / 'pages'
        pages_dir.mkdir()
        renders_dir = tmp_path / 'renders'
        renders_dir.mkdir()
        
        try:
            from PIL import Image
            # Larger image for crop testing
            img = Image.new('RGB', (200, 200), (255, 255, 255))
            img.save(pages_dir / 'page-004.png', 'PNG')
        except ImportError:
            pytest.skip("Pillow not installed")
        
        rooms_data = {
            "rooms": [
                {
                    "id": "A-101",
                    "name": "CLASSE",
                    "primary_source": 4
                },
                {
                    "id": "A-102",
                    "name": "CORRIDOR",
                    "primary_source": 4
                }
            ]
        }
        with open(tmp_path / 'rooms_complete.json', 'w') as f:
            json.dump(rooms_data, f)
        
        bboxes = {
            "A-101": {
                "page": 4,
                "bbox": [50, 50, 100, 100],  # 50x50 region
                "confidence": 0.85
            }
        }
        with open(tmp_path / 'room_bboxes.json', 'w') as f:
            json.dump(bboxes, f)
        
        return tmp_path
    
    def test_crop_room_with_bbox(self, mock_output_dir):
        """Test crop_room generates correctly sized crop."""
        try:
            from render_room import crop_room, PIL_AVAILABLE
            if not PIL_AVAILABLE:
                pytest.skip("Pillow not installed")
        except ImportError:
            pytest.skip("render_room not importable")
        
        padding = 10
        result = crop_room("A-101", str(mock_output_dir), padding=padding)
        
        assert Path(result).exists()
        
        from PIL import Image
        img = Image.open(result)
        
        # Bbox is 50x50, padding adds 10 each side
        # Expected: 70x70 (50 + 10*2)
        expected_size = 50 + padding * 2
        assert img.width == expected_size
        assert img.height == expected_size
    
    def test_crop_room_no_bbox_fallback(self, mock_output_dir):
        """Test crop_room returns full page when no bbox."""
        try:
            from render_room import crop_room, PIL_AVAILABLE
            if not PIL_AVAILABLE:
                pytest.skip("Pillow not installed")
        except ImportError:
            pytest.skip("render_room not importable")
        
        result = crop_room("A-102", str(mock_output_dir))
        
        assert Path(result).exists()
        
        from PIL import Image
        img = Image.open(result)
        # Should be full page size
        assert img.size == (200, 200)
    
    def test_crop_room_invalid_id(self, mock_output_dir):
        """Test crop_room raises ValueError for invalid room ID."""
        try:
            from render_room import crop_room, PIL_AVAILABLE
            if not PIL_AVAILABLE:
                pytest.skip("Pillow not installed")
        except ImportError:
            pytest.skip("render_room not importable")
        
        with pytest.raises(ValueError, match="not found"):
            crop_room("INVALID-123", str(mock_output_dir))


class TestRenderRoomCard:
    """Tests for render_room_card function."""
    
    @pytest.fixture
    def mock_output_dir(self, tmp_path):
        """Create mock output directory for card tests."""
        pages_dir = tmp_path / 'pages'
        pages_dir.mkdir()
        renders_dir = tmp_path / 'renders'
        renders_dir.mkdir()
        
        try:
            from PIL import Image
            img = Image.new('RGB', (100, 100), (255, 255, 255))
            img.save(pages_dir / 'page-004.png', 'PNG')
        except ImportError:
            pytest.skip("Pillow not installed")
        
        rooms_data = {
            "rooms": [
                {
                    "id": "A-101",
                    "name": "CLASSE",
                    "floor": 1,
                    "block": "A",
                    "primary_source": 4,
                    "confidence": 0.9,
                    "dimensions": "25'-6\" x 30'-0\"",
                    "area_sqft": 765
                }
            ]
        }
        with open(tmp_path / 'rooms_complete.json', 'w') as f:
            json.dump(rooms_data, f)
        
        bboxes = {
            "A-101": {"page": 4, "bbox": [10, 10, 50, 50], "confidence": 0.85}
        }
        with open(tmp_path / 'room_bboxes.json', 'w') as f:
            json.dump(bboxes, f)
        
        return tmp_path
    
    def test_render_room_card_generates_png(self, mock_output_dir):
        """Test render_room_card generates valid PNG card."""
        try:
            from render_room import render_room_card, PIL_AVAILABLE
            if not PIL_AVAILABLE:
                pytest.skip("Pillow not installed")
        except ImportError:
            pytest.skip("render_room not importable")
        
        result = render_room_card("A-101", str(mock_output_dir))
        
        assert Path(result).exists()
        assert result.endswith('_card.png')
        
        from PIL import Image
        img = Image.open(result)
        assert img.format == 'PNG'
        # Card dimensions
        assert img.width == 800
        assert img.height == 1000
    
    def test_render_room_card_invalid_id(self, mock_output_dir):
        """Test render_room_card raises ValueError for invalid room ID."""
        try:
            from render_room import render_room_card, PIL_AVAILABLE
            if not PIL_AVAILABLE:
                pytest.skip("Pillow not installed")
        except ImportError:
            pytest.skip("render_room not importable")
        
        with pytest.raises(ValueError, match="not found"):
            render_room_card("NONEXISTENT-999", str(mock_output_dir))


class TestExtractBbox:
    """Tests for extract_bbox.py functions."""
    
    def test_load_rooms(self, tmp_path):
        """Test load_rooms parses rooms_complete.json."""
        try:
            from extract_bbox import load_rooms
        except ImportError:
            pytest.skip("extract_bbox not importable")
        
        rooms_data = {
            "rooms": [
                {"id": "A-101", "name": "CLASSE"},
                {"id": "A-102", "name": "CORRIDOR"}
            ]
        }
        rooms_path = tmp_path / 'rooms_complete.json'
        with open(rooms_path, 'w') as f:
            json.dump(rooms_data, f)
        
        result = load_rooms(rooms_path)
        
        assert len(result) == 2
        assert "A-101" in result
        assert result["A-101"]["name"] == "CLASSE"
    
    def test_get_room_patterns(self):
        """Test room ID patterns match expected formats."""
        try:
            from extract_bbox import get_room_patterns
        except ImportError:
            pytest.skip("extract_bbox not importable")
        
        patterns = get_room_patterns()
        
        # Test pattern matching
        test_cases = [
            ("A-101", True),
            ("B-205", True),
            ("C-301", True),
            ("A101", True),   # Without dash
            ("101", True),    # Just number
            ("ROOM", False),
            ("X", False),
        ]
        
        for text, should_match in test_cases:
            matched = any(p.search(text) for p in patterns)
            assert matched == should_match, f"Pattern match failed for '{text}'"


class TestRenderFloor:
    """Tests for render_floor function."""
    
    @pytest.fixture
    def mock_output_dir(self, tmp_path):
        """Create mock output directory for floor tests."""
        pages_dir = tmp_path / 'pages'
        pages_dir.mkdir()
        renders_dir = tmp_path / 'renders'
        renders_dir.mkdir()
        
        try:
            from PIL import Image
            img = Image.new('RGB', (200, 200), (255, 255, 255))
            img.save(pages_dir / 'page-004.png', 'PNG')
        except ImportError:
            pytest.skip("Pillow not installed")
        
        rooms_data = {
            "rooms": [
                {"id": "A-101", "name": "CLASSE", "floor": 1, "block": "A", "primary_source": 4},
                {"id": "A-102", "name": "CORRIDOR", "floor": 1, "block": "A", "primary_source": 4},
                {"id": "B-101", "name": "BUREAU", "floor": 1, "block": "B", "primary_source": 5},
            ]
        }
        with open(tmp_path / 'rooms_complete.json', 'w') as f:
            json.dump(rooms_data, f)
        
        bboxes = {
            "A-101": {"page": 4, "bbox": [10, 10, 50, 50], "confidence": 0.85},
            "A-102": {"page": 4, "bbox": [60, 10, 100, 50], "confidence": 0.80},
        }
        with open(tmp_path / 'room_bboxes.json', 'w') as f:
            json.dump(bboxes, f)
        
        return tmp_path
    
    def test_render_floor_generates_png(self, mock_output_dir):
        """Test render_floor generates valid PNG."""
        try:
            from render_room import render_floor, PIL_AVAILABLE
            if not PIL_AVAILABLE:
                pytest.skip("Pillow not installed")
        except ImportError:
            pytest.skip("render_room not importable")
        
        result = render_floor("A", 1, str(mock_output_dir))
        
        assert Path(result).exists()
        assert 'floor_A1' in result
        
        from PIL import Image
        img = Image.open(result)
        assert img.format == 'PNG'
    
    def test_render_floor_invalid_block(self, mock_output_dir):
        """Test render_floor raises ValueError for invalid block."""
        try:
            from render_room import render_floor, PIL_AVAILABLE
            if not PIL_AVAILABLE:
                pytest.skip("Pillow not installed")
        except ImportError:
            pytest.skip("render_room not importable")
        
        with pytest.raises(ValueError, match="No rooms found"):
            render_floor("Z", 99, str(mock_output_dir))


class TestPillowUnavailable:
    """Tests for behavior when Pillow is not available."""
    
    def test_render_room_without_pillow(self, monkeypatch):
        """Test render_room raises RuntimeError when Pillow unavailable."""
        # Mock PIL_AVAILABLE to False
        try:
            import render_room
            monkeypatch.setattr(render_room, 'PIL_AVAILABLE', False)
            
            with pytest.raises(RuntimeError, match="Pillow is required"):
                render_room.render_room("A-101")
        except ImportError:
            pytest.skip("render_room not importable")
