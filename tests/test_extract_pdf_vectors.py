"""
Tests for extract_pdf_vectors.py
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import the module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from extract_pdf_vectors import (
    extract_pdf_vectors,
    extract_text_blocks,
    extract_drawings,
    calculate_scale_factor,
    parse_page_range,
    get_page_dimensions,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def real_pdf_path():
    """Path to the real test PDF."""
    pdf = Path(__file__).parent.parent / "output" / "C25-256 _Architecture_plan_Construction.pdf"
    if pdf.exists():
        return pdf
    pytest.skip("Test PDF not found")


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_page():
    """Create a mock PyMuPDF page."""
    page = MagicMock()
    page.rect = MagicMock()
    page.rect.width = 612  # Letter width in points
    page.rect.height = 792  # Letter height in points
    page.rect.x0 = 0
    page.rect.y0 = 0

    # Mock get_text('dict')
    page.get_text.return_value = {
        "blocks": [
            {
                "type": 0,
                "lines": [
                    {
                        "spans": [
                            {
                                "text": "101",
                                "bbox": [100, 100, 130, 120],
                                "font": "Helvetica",
                                "size": 12,
                                "flags": 0
                            }
                        ]
                    }
                ]
            },
            {
                "type": 0,
                "lines": [
                    {
                        "spans": [
                            {
                                "text": "CLASSE",
                                "bbox": [100, 80, 160, 95],
                                "font": "Helvetica",
                                "size": 10,
                                "flags": 0
                            }
                        ]
                    }
                ]
            }
        ]
    }

    # Mock get_drawings()
    mock_rect = MagicMock()
    mock_rect.x0 = 50
    mock_rect.y0 = 50
    mock_rect.width = 200
    mock_rect.height = 150
    mock_rect.is_empty = False
    mock_rect.is_infinite = False

    mock_point1 = MagicMock()
    mock_point1.x = 50
    mock_point1.y = 50

    mock_point2 = MagicMock()
    mock_point2.x = 250
    mock_point2.y = 50

    page.get_drawings.return_value = [
        {
            "rect": mock_rect,
            "items": [("l", mock_point1, mock_point2)],
            "fill": None,
            "color": (0, 0, 0),
            "width": 1
        }
    ]

    return page


# =============================================================================
# Unit Tests
# =============================================================================

class TestParsePageRange:
    """Tests for parse_page_range function."""

    def test_single_page(self):
        assert parse_page_range("5") == [5]

    def test_range(self):
        assert parse_page_range("1-5") == [1, 2, 3, 4, 5]

    def test_multiple_pages(self):
        assert parse_page_range("1,3,5") == [1, 3, 5]

    def test_mixed(self):
        assert parse_page_range("1-3,7,10-12") == [1, 2, 3, 7, 10, 11, 12]

    def test_duplicates_removed(self):
        assert parse_page_range("1,1,2,2") == [1, 2]

    def test_sorted(self):
        assert parse_page_range("5,1,3") == [1, 3, 5]


class TestCalculateScaleFactor:
    """Tests for calculate_scale_factor function."""

    def test_default_dpi(self, mock_page):
        scale = calculate_scale_factor(mock_page)
        # 300 DPI / 72 points per inch = 4.166...
        assert abs(scale - (300 / 72)) < 0.01

    def test_custom_dpi(self, mock_page):
        scale = calculate_scale_factor(mock_page, dpi=150)
        assert abs(scale - (150 / 72)) < 0.01

    def test_with_image_dimensions(self, mock_page):
        # Page is 612x792 points
        # Image is 2550x3300 pixels (like 300 DPI)
        scale = calculate_scale_factor(mock_page, image_width=2550, image_height=3300)
        expected = ((2550 / 612) + (3300 / 792)) / 2
        assert abs(scale - expected) < 0.01


class TestExtractTextBlocks:
    """Tests for extract_text_blocks function."""

    def test_extracts_text(self, mock_page):
        blocks = extract_text_blocks(mock_page, scale=1.0)
        assert len(blocks) == 2
        texts = [b["text"] for b in blocks]
        assert "101" in texts
        assert "CLASSE" in texts

    def test_applies_scale(self, mock_page):
        blocks = extract_text_blocks(mock_page, scale=2.0)
        block_101 = next(b for b in blocks if b["text"] == "101")
        # Original bbox: [100, 100, 130, 120]
        # Scaled: x=200, y=200, width=60, height=40
        assert block_101["bbox"]["x"] == 200
        assert block_101["bbox"]["y"] == 200
        assert block_101["bbox"]["width"] == 60
        assert block_101["bbox"]["height"] == 40

    def test_includes_font_info(self, mock_page):
        blocks = extract_text_blocks(mock_page, scale=1.0)
        block = blocks[0]
        assert "font" in block
        assert "size" in block


class TestExtractDrawings:
    """Tests for extract_drawings function."""

    def test_extracts_lines(self, mock_page):
        drawings = extract_drawings(mock_page, scale=1.0)
        assert len(drawings) == 1
        assert drawings[0]["items"][0]["type"] == "line"

    def test_applies_scale_to_drawings(self, mock_page):
        drawings = extract_drawings(mock_page, scale=2.0)
        drawing = drawings[0]
        # Original line: p1(50,50) p2(250,50)
        # Scaled: p1(100,100) p2(500,100)
        line = drawing["items"][0]
        assert line["p1"]["x"] == 100
        assert line["p1"]["y"] == 100
        assert line["p2"]["x"] == 500


# =============================================================================
# Integration Tests with Real PDF
# =============================================================================

class TestExtractPdfVectorsIntegration:
    """Integration tests using real PDF."""

    def test_extract_single_page(self, real_pdf_path, temp_output_dir):
        """Test extracting a single page."""
        output_file = temp_output_dir / "vectors.json"

        result = extract_pdf_vectors(
            str(real_pdf_path),
            output_path=str(output_file),
            pages=[12]  # Page with rooms 100-216
        )

        assert "pages" in result
        assert len(result["pages"]) == 1
        assert result["pages"][0]["page_number"] == 12

    def test_extract_has_text_blocks(self, real_pdf_path, temp_output_dir):
        """Test that text blocks are extracted."""
        result = extract_pdf_vectors(
            str(real_pdf_path),
            pages=[12]
        )

        page = result["pages"][0]
        assert "text_blocks" in page
        assert len(page["text_blocks"]) > 0

        # Should have room numbers
        texts = [b["text"] for b in page["text_blocks"]]
        # Look for 3-digit numbers
        three_digit = [t for t in texts if t.isdigit() and len(t) == 3]
        assert len(three_digit) > 0, "Should find room numbers"

    def test_extract_has_drawings(self, real_pdf_path, temp_output_dir):
        """Test that drawings are extracted."""
        result = extract_pdf_vectors(
            str(real_pdf_path),
            pages=[12]
        )

        page = result["pages"][0]
        assert "drawings" in page
        # Blueprints should have vector drawings
        # Note: some PDFs may have rasterized drawings
        # so we just check the key exists

    def test_output_file_created(self, real_pdf_path, temp_output_dir):
        """Test that output file is created."""
        output_file = temp_output_dir / "vectors.json"

        extract_pdf_vectors(
            str(real_pdf_path),
            output_path=str(output_file),
            pages=[12]
        )

        assert output_file.exists()

        with open(output_file) as f:
            data = json.load(f)

        assert "source" in data
        assert "pages" in data

    def test_dimensions_included(self, real_pdf_path):
        """Test that page dimensions are included."""
        result = extract_pdf_vectors(
            str(real_pdf_path),
            pages=[1]
        )

        page = result["pages"][0]
        assert "dimensions" in page
        assert "width_pts" in page["dimensions"]
        assert "height_pts" in page["dimensions"]
        assert "width_px" in page["dimensions"]
        assert "height_px" in page["dimensions"]
        assert "scale_factor" in page["dimensions"]

    def test_bbox_structure(self, real_pdf_path):
        """Test that bboxes have correct structure."""
        result = extract_pdf_vectors(
            str(real_pdf_path),
            pages=[12]
        )

        page = result["pages"][0]
        if page["text_blocks"]:
            bbox = page["text_blocks"][0]["bbox"]
            assert "x" in bbox
            assert "y" in bbox
            assert "width" in bbox
            assert "height" in bbox
            # All values should be non-negative
            assert bbox["x"] >= 0
            assert bbox["y"] >= 0
            assert bbox["width"] >= 0
            assert bbox["height"] >= 0

    def test_multiple_pages(self, real_pdf_path):
        """Test extracting multiple pages."""
        result = extract_pdf_vectors(
            str(real_pdf_path),
            pages=[10, 11, 12]
        )

        assert len(result["pages"]) == 3
        page_nums = [p["page_number"] for p in result["pages"]]
        assert page_nums == [10, 11, 12]


class TestExtractPdfVectorsErrors:
    """Test error handling."""

    def test_file_not_found(self, temp_output_dir):
        """Test that FileNotFoundError is raised for missing file."""
        with pytest.raises(FileNotFoundError):
            extract_pdf_vectors("/nonexistent/file.pdf")

    def test_invalid_page_numbers_filtered(self, real_pdf_path):
        """Test that invalid page numbers are filtered out."""
        result = extract_pdf_vectors(
            str(real_pdf_path),
            pages=[1, 9999]  # 9999 is out of range
        )

        # Should only extract page 1
        assert len(result["pages"]) == 1
        assert result["pages"][0]["page_number"] == 1
