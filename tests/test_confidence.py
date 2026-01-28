"""
Tests for the confidence.py score calculator.
"""

import json
import pytest
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from confidence import (
    calculate_room_confidence,
    calculate_primary_source,
    enhance_room_data,
    enhance_rooms_file,
    METHOD_WEIGHTS
)


class TestCalculateRoomConfidence:
    """Test confidence calculation for rooms."""
    
    def test_high_confidence_multi_source(self):
        """Room with many sources should have higher confidence than few."""
        room_many = {
            "id": "A-101",
            "name": "CLASSE",
            "source_pages": [4, 9, 12, 30]
        }
        room_few = {
            "id": "A-102",
            "name": "CLASSE",
            "source_pages": [4]
        }
        
        conf_many, method, notes = calculate_room_confidence(room_many)
        conf_few, _, _ = calculate_room_confidence(room_few)
        
        assert conf_many > conf_few  # More sources = higher confidence
        assert conf_many >= 0.7  # Reasonable threshold for OCR extraction
        assert "Multiples sources" in " ".join(notes)
    
    def test_low_confidence_no_source(self):
        """Room with no sources should have low confidence."""
        room = {
            "id": "A-102",
            "name": "LOCAL",
            "source_pages": []
        }
        
        confidence, method, notes = calculate_room_confidence(room)
        
        assert confidence < 0.5
        assert any("Aucune page source" in n for n in notes)
    
    def test_single_source_warning(self):
        """Room with single source should note validation needed."""
        room = {
            "id": "A-103",
            "name": "BUREAU",
            "source_pages": [5]
        }
        
        confidence, method, notes = calculate_room_confidence(room)
        
        assert 0.5 <= confidence < 0.9
        assert any("Source unique" in n or "validation" in n for n in notes)
    
    def test_generic_name_reduces_confidence(self):
        """Generic name should reduce confidence."""
        room1 = {"id": "A-104", "name": "LOCAL", "source_pages": [1, 2]}
        room2 = {"id": "A-105", "name": "CLASSE", "source_pages": [1, 2]}
        
        conf1, _, notes1 = calculate_room_confidence(room1)
        conf2, _, notes2 = calculate_room_confidence(room2)
        
        assert conf1 < conf2
        assert any("Nom générique" in n for n in notes1)
    
    def test_manual_method_highest_confidence(self):
        """Manual method should have highest base confidence."""
        room = {
            "id": "A-106",
            "name": "CLASSE",
            "source_pages": [1, 2, 3],
            "extraction_method": "manual"
        }
        
        confidence, method, _ = calculate_room_confidence(room)
        
        assert method == "manual"
        assert confidence >= 0.9


class TestCalculatePrimarySource:
    """Test primary source page determination."""
    
    def test_empty_sources(self):
        """Empty sources should return None."""
        assert calculate_primary_source([]) is None
    
    def test_single_source(self):
        """Single source should be returned."""
        assert calculate_primary_source([5]) == 5
    
    def test_prefers_non_schedule_pages(self):
        """Should prefer pages before room schedules (page 30+)."""
        result = calculate_primary_source([30, 31, 4, 9])
        assert result == 4  # Lower non-schedule page
    
    def test_schedule_only_pages(self):
        """If only schedule pages, return first."""
        result = calculate_primary_source([30, 31, 32])
        assert result == 30


class TestEnhanceRoomData:
    """Test room data enhancement."""
    
    def test_enhance_adds_confidence(self):
        """Enhancement should add confidence field."""
        room = {"id": "A-101", "name": "CLASSE", "pages": [4, 9]}
        
        enhanced = enhance_room_data(room)
        
        assert "confidence" in enhanced
        assert 0 < enhanced["confidence"] <= 1
    
    def test_enhance_adds_extraction_method(self):
        """Enhancement should add extraction method."""
        room = {"id": "A-101", "name": "CLASSE", "pages": [4, 9, 30]}
        
        enhanced = enhance_room_data(room)
        
        assert "extraction_method" in enhanced
        assert enhanced["extraction_method"] in METHOD_WEIGHTS
    
    def test_enhance_normalizes_source_pages(self):
        """Enhancement should use source_pages field."""
        room = {"id": "A-101", "name": "CLASSE", "pages": [4, 9]}
        
        enhanced = enhance_room_data(room)
        
        assert "source_pages" in enhanced
        assert enhanced["source_pages"] == [4, 9]
    
    def test_enhance_adds_primary_source(self):
        """Enhancement should add primary source."""
        room = {"id": "A-101", "name": "CLASSE", "pages": [4, 9, 30]}
        
        enhanced = enhance_room_data(room)
        
        assert "primary_source" in enhanced
        assert enhanced["primary_source"] == 4
    
    def test_enhance_preserves_existing_fields(self):
        """Enhancement should preserve existing fields."""
        room = {
            "id": "A-101",
            "name": "CLASSE",
            "pages": [4],
            "floor": 1,
            "block": "A",
            "custom_field": "preserved"
        }
        
        enhanced = enhance_room_data(room)
        
        assert enhanced["floor"] == 1
        assert enhanced["block"] == "A"
        assert enhanced["custom_field"] == "preserved"


class TestEnhanceRoomsFile:
    """Test file-level enhancement."""
    
    @pytest.fixture
    def sample_rooms_file(self, tmp_path):
        """Create sample rooms file."""
        rooms_data = {
            "project": {"name": "Test Project"},
            "rooms": [
                {"id": "A-101", "name": "CLASSE", "pages": [4, 9, 30], "floor": 1, "block": "A"},
                {"id": "A-102", "name": "CORRIDOR", "pages": [4], "floor": 1, "block": "A"},
                {"id": "A-103", "name": "LOCAL", "pages": [], "floor": 1, "block": "A"},
            ]
        }
        
        file_path = tmp_path / "rooms.json"
        with open(file_path, "w") as f:
            json.dump(rooms_data, f)
        
        return file_path
    
    def test_enhance_file_adds_quality_meta(self, sample_rooms_file, tmp_path):
        """Enhancement should add quality metadata."""
        output_path = tmp_path / "rooms_enhanced.json"
        
        data = enhance_rooms_file(sample_rooms_file, output_path)
        
        assert "quality_meta" in data
        assert data["quality_meta"]["confidence_added"] is True
        assert "average_confidence" in data["quality_meta"]
    
    def test_enhance_file_categorizes_confidence(self, sample_rooms_file, tmp_path):
        """Enhancement should categorize rooms by confidence."""
        output_path = tmp_path / "rooms_enhanced.json"
        
        data = enhance_rooms_file(sample_rooms_file, output_path)
        
        meta = data["quality_meta"]
        total = (
            meta["rooms_high_confidence"] +
            meta["rooms_medium_confidence"] +
            meta["rooms_low_confidence"]
        )
        
        assert total == len(data["rooms"])
    
    def test_enhance_file_writes_output(self, sample_rooms_file, tmp_path):
        """Enhancement should write output file."""
        output_path = tmp_path / "rooms_enhanced.json"
        
        enhance_rooms_file(sample_rooms_file, output_path)
        
        assert output_path.exists()
        
        with open(output_path) as f:
            saved_data = json.load(f)
        
        assert "quality_meta" in saved_data
        assert all("confidence" in r for r in saved_data["rooms"])
    
    def test_enhance_file_preserves_structure(self, sample_rooms_file, tmp_path):
        """Enhancement should preserve original structure."""
        output_path = tmp_path / "rooms_enhanced.json"
        
        data = enhance_rooms_file(sample_rooms_file, output_path)
        
        assert "project" in data
        assert data["project"]["name"] == "Test Project"
