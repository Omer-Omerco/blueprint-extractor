"""
Tests for crop_extractor.py
Room crop extraction from PDF pages.
"""

import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from crop_extractor import (
    load_rooms,
    convert_bbox_to_fitz,
    sanitize_filename,
    extract_room_crop,
    extract_all_rooms,
    run_extraction,
)

try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    def test_preserves_alphanumeric(self):
        """Should preserve alphanumeric characters."""
        assert sanitize_filename("Room101") == "Room101"
        assert sanitize_filename("abc123") == "abc123"

    def test_preserves_allowed_chars(self):
        """Should preserve dashes, underscores, dots."""
        assert sanitize_filename("room-101") == "room-101"
        assert sanitize_filename("room_101") == "room_101"
        assert sanitize_filename("room.101") == "room.101"

    def test_replaces_special_chars(self):
        """Should replace special characters with underscores."""
        assert sanitize_filename("ROOM 101") == "ROOM_101"
        assert sanitize_filename("LOCAL/109") == "LOCAL_109"
        assert sanitize_filename("SALLE #1") == "SALLE_1"

    def test_removes_consecutive_underscores(self):
        """Should collapse consecutive underscores."""
        assert sanitize_filename("room  101") == "room_101"
        assert sanitize_filename("A   B") == "A_B"

    def test_strips_edge_underscores(self):
        """Should strip leading/trailing underscores."""
        assert sanitize_filename(" room ") == "room"
        assert sanitize_filename("_room_") == "room"


class TestConvertBboxToFitz:
    """Tests for bbox coordinate conversion."""

    def test_converts_basic_bbox(self):
        """Should convert bbox to fitz.Rect."""
        if not HAS_FITZ:
            pytest.skip("PyMuPDF not installed")
        
        bbox = {"x": 100, "y": 200, "width": 300, "height": 400}
        rect = convert_bbox_to_fitz(bbox, 1000)
        
        assert rect.x0 == 100
        assert rect.y0 == 200
        assert rect.x1 == 400  # x + width
        assert rect.y1 == 600  # y + height

    def test_handles_zero_bbox(self):
        """Should handle zero/empty bbox."""
        if not HAS_FITZ:
            pytest.skip("PyMuPDF not installed")
        
        bbox = {"x": 0, "y": 0, "width": 0, "height": 0}
        rect = convert_bbox_to_fitz(bbox, 1000)
        
        assert rect.x0 == 0
        assert rect.y0 == 0
        assert rect.x1 == 0
        assert rect.y1 == 0

    def test_handles_missing_fields(self):
        """Should handle missing bbox fields with defaults."""
        if not HAS_FITZ:
            pytest.skip("PyMuPDF not installed")
        
        bbox = {"x": 100}  # Only x specified
        rect = convert_bbox_to_fitz(bbox, 1000)
        
        assert rect.x0 == 100
        assert rect.y0 == 0


class TestLoadRooms:
    """Tests for loading rooms data."""

    def test_loads_rooms_file(self, temp_dir):
        """Should load rooms from JSON file."""
        rooms_file = temp_dir / "rooms.json"
        rooms_data = {
            "source": "test.pdf",
            "total_rooms": 2,
            "rooms": [
                {"id": "room-001", "name": "OFFICE", "page": 1, "bbox": {"x": 0, "y": 0, "width": 100, "height": 100}},
                {"id": "room-002", "name": "HALL", "page": 1, "bbox": {"x": 100, "y": 0, "width": 100, "height": 100}}
            ]
        }
        with open(rooms_file, "w") as f:
            json.dump(rooms_data, f)

        loaded = load_rooms(str(rooms_file))

        assert loaded["total_rooms"] == 2
        assert len(loaded["rooms"]) == 2
        assert loaded["rooms"][0]["name"] == "OFFICE"


class TestExtractAllRooms:
    """Integration tests for room extraction."""

    @pytest.mark.skipif(not HAS_FITZ, reason="PyMuPDF not installed")
    def test_extracts_rooms_from_pdf(self, temp_dir, sample_pdf):
        """Should extract room crops from PDF."""
        # Create rooms data matching our sample PDF
        rooms_data = {
            "source": str(sample_pdf),
            "total_rooms": 1,
            "rooms": [
                {
                    "id": "room-001",
                    "name": "TEST",
                    "page": 1,
                    "bbox": {"x": 50, "y": 50, "width": 100, "height": 100}
                }
            ]
        }
        
        output_dir = temp_dir / "crops"
        
        results = extract_all_rooms(
            rooms_data,
            str(sample_pdf),
            str(output_dir),
            dpi=72,
            padding=5
        )
        
        assert results["extracted"] == 1
        assert results["failed"] == 0
        assert len(results["files"]) == 1
        
        # Check output file exists
        output_file = Path(results["files"][0]["output_file"])
        assert output_file.exists()
        assert output_file.suffix == ".png"

    @pytest.mark.skipif(not HAS_FITZ, reason="PyMuPDF not installed")
    def test_handles_invalid_page_number(self, temp_dir, sample_pdf):
        """Should handle rooms with invalid page numbers."""
        rooms_data = {
            "source": str(sample_pdf),
            "total_rooms": 1,
            "rooms": [
                {
                    "id": "room-001",
                    "name": "TEST",
                    "page": 999,  # Invalid page
                    "bbox": {"x": 50, "y": 50, "width": 100, "height": 100}
                }
            ]
        }
        
        output_dir = temp_dir / "crops"
        
        results = extract_all_rooms(
            rooms_data,
            str(sample_pdf),
            str(output_dir)
        )
        
        assert results["extracted"] == 0
        assert results["failed"] == 1

    @pytest.mark.skipif(not HAS_FITZ, reason="PyMuPDF not installed")
    def test_handles_missing_bbox(self, temp_dir, sample_pdf):
        """Should handle rooms without bbox."""
        rooms_data = {
            "source": str(sample_pdf),
            "total_rooms": 1,
            "rooms": [
                {
                    "id": "room-001",
                    "name": "TEST",
                    "page": 1
                    # No bbox
                }
            ]
        }
        
        output_dir = temp_dir / "crops"
        
        results = extract_all_rooms(
            rooms_data,
            str(sample_pdf),
            str(output_dir)
        )
        
        assert results["extracted"] == 0
        assert results["failed"] == 1


class TestRunExtraction:
    """Integration tests for full extraction pipeline."""

    @pytest.mark.skipif(not HAS_FITZ, reason="PyMuPDF not installed")
    def test_full_pipeline(self, temp_dir, sample_pdf):
        """Should run complete extraction pipeline."""
        # Create rooms JSON
        rooms_file = temp_dir / "rooms.json"
        rooms_data = {
            "source": str(sample_pdf),
            "total_rooms": 2,
            "rooms": [
                {
                    "id": "room-001",
                    "name": "OFFICE 101",
                    "page": 1,
                    "bbox": {"x": 10, "y": 10, "width": 80, "height": 80}
                },
                {
                    "id": "room-002",
                    "number": "102",
                    "page": 1,
                    "bbox": {"x": 100, "y": 10, "width": 80, "height": 80}
                }
            ]
        }
        with open(rooms_file, "w") as f:
            json.dump(rooms_data, f)
        
        output_dir = temp_dir / "crops"
        
        results = run_extraction(
            str(rooms_file),
            str(sample_pdf),
            str(output_dir),
            dpi=72,
            padding=5
        )
        
        assert results["total_rooms"] == 2
        assert results["extracted"] == 2
        assert len(results["files"]) == 2
        
        # Check files exist
        for f in results["files"]:
            assert Path(f["output_file"]).exists()


class TestOutputFormat:
    """Tests for output structure."""

    @pytest.mark.skipif(not HAS_FITZ, reason="PyMuPDF not installed")
    def test_results_have_required_fields(self, temp_dir, sample_pdf):
        """Results should have all required fields."""
        rooms_data = {
            "source": str(sample_pdf),
            "rooms": [
                {"id": "room-001", "page": 1, "bbox": {"x": 10, "y": 10, "width": 50, "height": 50}}
            ]
        }
        
        output_dir = temp_dir / "crops"
        
        results = extract_all_rooms(rooms_data, str(sample_pdf), str(output_dir))
        
        assert "source_pdf" in results
        assert "output_dir" in results
        assert "dpi" in results
        assert "total_rooms" in results
        assert "extracted" in results
        assert "failed" in results
        assert "files" in results
        assert "errors" in results

    @pytest.mark.skipif(not HAS_FITZ, reason="PyMuPDF not installed")
    def test_file_entry_format(self, temp_dir, sample_pdf):
        """Each file entry should have required fields."""
        rooms_data = {
            "source": str(sample_pdf),
            "rooms": [
                {"id": "room-001", "name": "TEST", "page": 1, "bbox": {"x": 10, "y": 10, "width": 50, "height": 50}}
            ]
        }
        
        output_dir = temp_dir / "crops"
        
        results = extract_all_rooms(rooms_data, str(sample_pdf), str(output_dir))
        
        assert len(results["files"]) == 1
        file_entry = results["files"][0]
        
        assert "room_id" in file_entry
        assert "room_name" in file_entry
        assert "page" in file_entry
        assert "output_file" in file_entry
