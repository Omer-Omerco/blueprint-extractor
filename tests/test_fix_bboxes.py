#!/usr/bin/env python3
"""
Tests for fix_bboxes.py — Room bbox fixing via PyMuPDF text extraction.
Tests the pure functions without requiring the actual PDF.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from fix_bboxes import (
    get_all_spans,
    find_room_on_page,
)


# ============== Fixtures ==============

@pytest.fixture
def sample_spans():
    """Simulated PyMuPDF text spans."""
    return [
        {"text": "A-101", "bbox": (100.0, 200.0, 140.0, 215.0), "size": 8.0},
        {"text": "CLASSE", "bbox": (100.0, 220.0, 160.0, 235.0), "size": 7.0},
        {"text": "A-102", "bbox": (300.0, 200.0, 340.0, 215.0), "size": 8.0},
        {"text": "CORRIDOR", "bbox": (300.0, 220.0, 380.0, 235.0), "size": 7.0},
        {"text": "B-201", "bbox": (500.0, 400.0, 540.0, 415.0), "size": 8.0},
        {"text": "GYMNASE", "bbox": (500.0, 420.0, 580.0, 435.0), "size": 7.0},
        {"text": "102", "bbox": (300.5, 200.5, 325.0, 215.0), "size": 8.0},  # Number only
    ]


@pytest.fixture
def scale():
    """Scale factor from PDF points to pixels."""
    return 5.0  # Typical: ~5000px / ~1000pt


# ============== find_room_on_page ==============

class TestFindRoomOnPage:
    def test_find_by_id(self, sample_spans, scale):
        bbox = find_room_on_page("A-101", "CLASSE", sample_spans, scale)
        assert bbox is not None
        assert len(bbox) == 4
        # x1 <= x2, y1 <= y2
        assert bbox[0] <= bbox[2]
        assert bbox[1] <= bbox[3]

    def test_find_by_id_with_name(self, sample_spans, scale):
        """Should merge label bbox with name bbox."""
        bbox = find_room_on_page("A-101", "CLASSE", sample_spans, scale)
        assert bbox is not None
        # Bbox should include both the ID and name spans

    def test_find_different_rooms(self, sample_spans, scale):
        bbox_a101 = find_room_on_page("A-101", "CLASSE", sample_spans, scale)
        bbox_a102 = find_room_on_page("A-102", "CORRIDOR", sample_spans, scale)
        bbox_b201 = find_room_on_page("B-201", "GYMNASE", sample_spans, scale)

        assert bbox_a101 is not None
        assert bbox_a102 is not None
        assert bbox_b201 is not None

        # They should be at different positions
        assert bbox_a101[0] != bbox_b201[0]

    def test_not_found(self, sample_spans, scale):
        bbox = find_room_on_page("Z-999", "INCONNU", sample_spans, scale)
        assert bbox is None

    def test_multipart_id(self, sample_spans, scale):
        """Test room IDs with multiple parts like A-102-1."""
        spans = [
            {"text": "102-1", "bbox": (100.0, 100.0, 140.0, 115.0), "size": 8.0},
            {"text": "RANGEMENT", "bbox": (100.0, 120.0, 180.0, 135.0), "size": 7.0},
        ]
        bbox = find_room_on_page("A-102-1", "RANGEMENT", spans, scale)
        assert bbox is not None

    def test_bbox_clamped(self, sample_spans, scale):
        """Bboxes should be clamped to >= 0."""
        # Span near edge
        spans = [
            {"text": "A-100", "bbox": (2.0, 2.0, 20.0, 15.0), "size": 8.0},
        ]
        bbox = find_room_on_page("A-100", "", spans, scale)
        assert bbox is not None
        assert bbox[0] >= 0
        assert bbox[1] >= 0

    def test_empty_spans(self, scale):
        bbox = find_room_on_page("A-101", "CLASSE", [], scale)
        assert bbox is None

    def test_no_name_given(self, sample_spans, scale):
        """Should work without a room name."""
        bbox = find_room_on_page("A-101", "", sample_spans, scale)
        assert bbox is not None

    def test_alt_number_format(self, scale):
        """Test dot-separated number format (102.1 for 102-1)."""
        spans = [
            {"text": "102.1", "bbox": (100.0, 100.0, 140.0, 115.0), "size": 8.0},
        ]
        bbox = find_room_on_page("A-102-1", "", spans, scale)
        assert bbox is not None


# ============== get_all_spans ==============

class TestGetAllSpans:
    def test_with_mock_page(self):
        """Test span extraction with a mock fitz page."""
        try:
            import fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")

        # Create an in-memory PDF page
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text((100, 100), "A-101", fontsize=10)
        page.insert_text((100, 120), "CLASSE", fontsize=10)

        spans = get_all_spans(page)

        assert len(spans) > 0
        texts = [s["text"] for s in spans]
        assert "A-101" in texts
        assert "CLASSE" in texts

        for span in spans:
            assert "text" in span
            assert "bbox" in span
            assert "size" in span
            assert len(span["bbox"]) == 4

        doc.close()

    def test_empty_page(self):
        try:
            import fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")

        doc = fitz.open()
        page = doc.new_page()
        spans = get_all_spans(page)
        assert spans == []
        doc.close()
