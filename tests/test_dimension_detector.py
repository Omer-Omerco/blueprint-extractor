"""
Tests for dimension_detector.py
Dimension detection from blueprint vector data.
"""

import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from dimension_detector import (
    parse_dimension,
    is_dimension_text,
    extract_dimensions_from_text,
    detect_dimensions,
    calculate_confidence,
    run_detection,
)


class TestParseDimension:
    """Tests for dimension parsing."""

    def test_standard_feet_inches(self):
        """Should parse standard 25'-6" format."""
        result = parse_dimension("25'-6\"")
        assert result is not None
        text, inches = result
        assert text == "25'-6\""
        assert inches == 306  # 25*12 + 6

    def test_feet_inches_with_fraction(self):
        """Should parse 12'-6 5/8" format with fraction."""
        result = parse_dimension("12'-6 5/8\"")
        assert result is not None
        text, inches = result
        assert text == "12'-6 5/8\""
        assert inches == pytest.approx(150.625, rel=0.01)  # 12*12 + 6 + 5/8

    def test_feet_only_with_zero(self):
        """Should parse 25'-0" format."""
        result = parse_dimension("25'-0\"")
        assert result is not None
        text, inches = result
        assert inches == 300  # 25*12

    def test_feet_only(self):
        """Should parse 25' format."""
        result = parse_dimension("25'")
        assert result is not None
        text, inches = result
        assert inches == 300  # 25*12

    def test_inches_only(self):
        """Should parse 6" format."""
        result = parse_dimension("6\"")
        assert result is not None
        text, inches = result
        assert inches == 6

    def test_inches_with_fraction(self):
        """Should parse 6 5/8" format."""
        result = parse_dimension("6 5/8\"")
        assert result is not None
        text, inches = result
        assert inches == pytest.approx(6.625, rel=0.01)

    def test_no_space_before_dash(self):
        """Should handle 25'-6\" without spaces."""
        result = parse_dimension("25'-6\"")
        assert result is not None
        _, inches = result
        assert inches == 306

    def test_space_around_dash(self):
        """Should handle 25' - 6\" with spaces."""
        result = parse_dimension("25' - 6\"")
        assert result is not None
        _, inches = result
        assert inches == 306

    def test_returns_none_for_non_dimension(self):
        """Should return None for non-dimension text."""
        assert parse_dimension("hello") is None
        assert parse_dimension("123") is None
        assert parse_dimension("12.5m") is None


class TestIsDimensionText:
    """Tests for dimension text detection."""

    @pytest.mark.parametrize("text", [
        "25'-6\"",
        "12'-0\"",
        "8'",
        "6\"",
        "12'-6 5/8\"",
        "6 1/2\"",
        "30'-0\"",
    ])
    def test_recognizes_valid_dimensions(self, text):
        """Should recognize valid dimension formats."""
        assert is_dimension_text(text) is True

    @pytest.mark.parametrize("text", [
        "hello",
        "25",
        "12.5m",
        "ROOM 101",
        "P-01",
        "25'-",  # Incomplete
    ])
    def test_rejects_non_dimensions(self, text):
        """Should reject non-dimension text."""
        assert is_dimension_text(text) is False


class TestExtractDimensionsFromText:
    """Tests for extracting dimensions from longer text."""

    def test_extracts_single_dimension(self):
        """Should extract single dimension from text."""
        result = extract_dimensions_from_text("Width: 25'-6\"")
        assert len(result) == 1
        assert result[0]["text"] == "25'-6\""
        assert result[0]["value_inches"] == 306

    def test_extracts_multiple_dimensions(self):
        """Should extract multiple dimensions."""
        result = extract_dimensions_from_text("Room: 25'-6\" x 30'-0\"")
        assert len(result) == 2
        values = [r["value_inches"] for r in result]
        assert 306 in values  # 25'-6"
        assert 360 in values  # 30'-0"

    def test_handles_fractions_in_text(self):
        """Should handle fractions in longer text."""
        result = extract_dimensions_from_text("Offset: 6 5/8\"")
        assert len(result) == 1
        assert result[0]["value_inches"] == pytest.approx(6.625, rel=0.01)

    def test_avoids_duplicate_overlapping_matches(self):
        """Should not return overlapping matches."""
        result = extract_dimensions_from_text("12'-6 5/8\"")
        # Should match full "12'-6 5/8\"" not also "6 5/8\""
        assert len(result) == 1


class TestDetectDimensions:
    """Tests for main dimension detection function."""

    def test_detects_dimension_from_text_element(self):
        """Should detect dimension from text elements."""
        vectors = {
            "texts": [
                {"text": "25'-6\"", "bbox": {"x0": 100, "y0": 100, "x1": 150, "y1": 120}}
            ],
            "page": 1
        }
        dims = detect_dimensions(vectors)
        assert len(dims) == 1
        assert dims[0]["value_text"] == "25'-6\""
        assert dims[0]["value_inches"] == 306

    def test_detects_multiple_dimensions(self):
        """Should detect multiple dimensions."""
        vectors = {
            "texts": [
                {"text": "25'-6\"", "bbox": {"x0": 100, "y0": 100, "x1": 150, "y1": 120}},
                {"text": "30'-0\"", "bbox": {"x0": 200, "y0": 100, "x1": 250, "y1": 120}},
                {"text": "ROOM 101", "bbox": {"x0": 150, "y0": 150, "x1": 220, "y1": 170}}
            ],
            "page": 2
        }
        dims = detect_dimensions(vectors)
        assert len(dims) == 2

    def test_includes_page_number(self):
        """Should include page number in output."""
        vectors = {
            "texts": [
                {"text": "25'-6\"", "bbox": {"x0": 100, "y0": 100, "x1": 150, "y1": 120}}
            ],
            "page": 5
        }
        dims = detect_dimensions(vectors)
        assert dims[0]["page"] == 5

    def test_includes_bbox(self):
        """Should include bounding box in output."""
        vectors = {
            "texts": [
                {"text": "25'-6\"", "bbox": {"x0": 100, "y0": 100, "x1": 150, "y1": 120}}
            ]
        }
        dims = detect_dimensions(vectors)
        assert "bbox" in dims[0]
        assert dims[0]["bbox"]["x0"] == 100

    def test_extracts_embedded_dimensions(self):
        """Should extract dimensions embedded in longer text."""
        vectors = {
            "texts": [
                {"text": "Width: 25'-6\"", "bbox": {"x0": 100, "y0": 100, "x1": 200, "y1": 120}}
            ]
        }
        dims = detect_dimensions(vectors)
        assert len(dims) == 1
        assert dims[0]["value_text"] == "25'-6\""

    def test_avoids_duplicate_texts(self):
        """Should not create duplicates for same text at same position."""
        vectors = {
            "texts": [
                {"text": "25'-6\"", "bbox": {"x0": 100, "y0": 100, "x1": 150, "y1": 120}},
                {"text": "25'-6\"", "bbox": {"x0": 100, "y0": 100, "x1": 150, "y1": 120}}
            ]
        }
        dims = detect_dimensions(vectors)
        assert len(dims) == 1


class TestCalculateConfidence:
    """Tests for confidence score calculation."""

    def test_base_confidence(self):
        """Should have reasonable base confidence."""
        conf = calculate_confidence("25'-6\"", {})
        assert conf >= 0.7

    def test_higher_confidence_for_standard_format(self):
        """Standard format should have higher confidence."""
        conf_standard = calculate_confidence("25'-6\"", {})
        conf_inches = calculate_confidence("6\"", {})
        assert conf_standard >= conf_inches

    def test_confidence_capped_at_one(self):
        """Confidence should not exceed 1.0."""
        conf = calculate_confidence("12'-0\"", {})
        assert conf <= 1.0


class TestRunDetection:
    """Integration tests for run_detection."""

    def test_loads_and_processes_file(self, temp_dir):
        """Should load JSON file and detect dimensions."""
        vectors_file = temp_dir / "vectors.json"
        vectors_data = {
            "texts": [
                {"text": "25'-6\"", "bbox": {"x0": 100, "y0": 100, "x1": 150, "y1": 120}},
                {"text": "12'-0\"", "bbox": {"x0": 200, "y0": 200, "x1": 250, "y1": 220}}
            ],
            "page": 1
        }
        with open(vectors_file, "w") as f:
            json.dump(vectors_data, f)

        results = run_detection(str(vectors_file))

        assert results["total_dimensions"] == 2

    def test_handles_multiple_pages(self, temp_dir):
        """Should handle multi-page vector data."""
        vectors_file = temp_dir / "vectors.json"
        vectors_data = {
            "pages": [
                {
                    "page": 1,
                    "texts": [
                        {"text": "25'-6\"", "bbox": {"x0": 100, "y0": 100, "x1": 150, "y1": 120}}
                    ]
                },
                {
                    "page": 2,
                    "texts": [
                        {"text": "30'-0\"", "bbox": {"x0": 100, "y0": 100, "x1": 150, "y1": 120}}
                    ]
                }
            ]
        }
        with open(vectors_file, "w") as f:
            json.dump(vectors_data, f)

        results = run_detection(str(vectors_file))

        assert results["total_dimensions"] == 2

    def test_writes_output_file(self, temp_dir):
        """Should write results to output file."""
        vectors_file = temp_dir / "vectors.json"
        output_file = temp_dir / "output" / "dimensions.json"

        vectors_data = {
            "texts": [
                {"text": "25'-6\"", "bbox": {"x0": 100, "y0": 100, "x1": 150, "y1": 120}}
            ]
        }
        with open(vectors_file, "w") as f:
            json.dump(vectors_data, f)

        run_detection(str(vectors_file), str(output_file))

        assert output_file.exists()
        with open(output_file) as f:
            saved = json.load(f)
        assert saved["total_dimensions"] == 1


class TestDimensionOutputFormat:
    """Tests for dimension output structure."""

    def test_dimension_has_required_fields(self):
        """Each dimension should have all required fields."""
        vectors = {
            "texts": [
                {"text": "25'-6\"", "bbox": {"x0": 100, "y0": 100, "x1": 150, "y1": 120}}
            ],
            "page": 1
        }
        dims = detect_dimensions(vectors)

        assert len(dims) == 1
        dim = dims[0]

        assert "id" in dim
        assert "value_text" in dim
        assert "value_inches" in dim
        assert "bbox" in dim
        assert "confidence" in dim
        assert "page" in dim

    def test_value_inches_is_numeric(self):
        """value_inches should be a number."""
        vectors = {
            "texts": [
                {"text": "25'-6\"", "bbox": {"x0": 100, "y0": 100, "x1": 150, "y1": 120}}
            ]
        }
        dims = detect_dimensions(vectors)
        assert isinstance(dims[0]["value_inches"], (int, float))


class TestQuebecDimensionFormats:
    """Tests for Quebec-specific dimension formats."""

    @pytest.mark.parametrize("text,expected_inches", [
        ("25'-6\"", 306),
        ("12'-0\"", 144),
        ("8'-0\"", 96),
        ("30'-0\"", 360),
        ("8'-6\"", 102),
        ("10'-3\"", 123),
        ("15'-9\"", 189),
    ])
    def test_common_quebec_dimensions(self, text, expected_inches):
        """Should correctly parse common Quebec dimension formats."""
        result = parse_dimension(text)
        assert result is not None
        _, inches = result
        assert inches == expected_inches

    @pytest.mark.parametrize("text,expected_inches", [
        ("8'-6 1/2\"", 102.5),
        ("10'-3 1/4\"", 123.25),
        ("12'-6 5/8\"", 150.625),
        ("25'-0 3/4\"", 300.75),
    ])
    def test_fractional_dimensions(self, text, expected_inches):
        """Should correctly parse fractional dimensions."""
        result = parse_dimension(text)
        assert result is not None
        _, inches = result
        assert inches == pytest.approx(expected_inches, rel=0.01)

    def test_ceiling_height_format(self):
        """Should handle typical ceiling height format."""
        result = parse_dimension("8'-0\"")
        assert result is not None
        _, inches = result
        assert inches == 96  # 8 feet

    def test_corridor_width_format(self):
        """Should handle corridor width format."""
        result = parse_dimension("6'-0\"")
        assert result is not None
        _, inches = result
        assert inches == 72  # 6 feet
