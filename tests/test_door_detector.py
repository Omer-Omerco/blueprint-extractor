"""
Tests for door_detector.py
Door detection from blueprint vector data.
"""

import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from door_detector import (
    calculate_arc_angle,
    calculate_arc_radius,
    determine_swing_direction,
    find_nearby_door_number,
    is_door_arc,
    is_door_label,
    normalize_door_number,
    calculate_confidence,
    detect_doors,
    detect_doors_from_labels,
    run_detection,
)


class TestCalculateArcAngle:
    """Tests for arc angle calculation."""

    def test_90_degree_arc_with_center(self):
        """Should detect ~90° arc when center is provided."""
        curve = {
            "start": {"x": 100, "y": 0},
            "end": {"x": 0, "y": 100},
            "center": {"x": 0, "y": 0}
        }
        angle = calculate_arc_angle(curve)
        assert 85 <= angle <= 95

    def test_90_degree_bezier_curve(self):
        """Should estimate ~90° from bezier control points."""
        # Approximate 90° bezier curve
        # For a quarter circle, control points are at ~0.552 * radius
        curve = {
            "start": {"x": 100, "y": 0},
            "end": {"x": 0, "y": 100},
            "control1": {"x": 100, "y": 55.2},
            "control2": {"x": 55.2, "y": 100}
        }
        angle = calculate_arc_angle(curve)
        assert 80 <= angle <= 100

    def test_fallback_for_simple_curve(self):
        """Should return default 90° for simple arc endpoints."""
        curve = {
            "start": {"x": 0, "y": 0},
            "end": {"x": 50, "y": 50}
        }
        angle = calculate_arc_angle(curve)
        assert angle == 90.0


class TestCalculateArcRadius:
    """Tests for arc radius (door width) calculation."""

    def test_calculates_radius_from_chord(self):
        """Should calculate radius from chord length."""
        # For 90° arc: chord = radius * sqrt(2)
        # Chord of ~141.4 → radius of 100
        curve = {
            "start": {"x": 100, "y": 0},
            "end": {"x": 0, "y": 100}
        }
        radius = calculate_arc_radius(curve)
        assert 95 <= radius <= 105

    def test_small_door_radius(self):
        """Should handle small door dimensions."""
        curve = {
            "start": {"x": 30, "y": 0},
            "end": {"x": 0, "y": 30}
        }
        radius = calculate_arc_radius(curve)
        # Chord ≈ 42.4, radius ≈ 30
        assert 25 <= radius <= 35


class TestDetermineSwingDirection:
    """Tests for door swing direction detection."""

    def test_left_swing_detection(self):
        """Should detect left swing from control points."""
        curve = {
            "start": {"x": 0, "y": 0},
            "end": {"x": 100, "y": 100},
            "control1": {"x": 0, "y": 50},  # Curves left
            "control2": {"x": 50, "y": 100}
        }
        direction = determine_swing_direction(curve)
        assert direction == "left"

    def test_right_swing_detection(self):
        """Should detect right swing from control points."""
        curve = {
            "start": {"x": 0, "y": 0},
            "end": {"x": 100, "y": 100},
            "control1": {"x": 50, "y": 0},  # Curves right
            "control2": {"x": 100, "y": 50}
        }
        direction = determine_swing_direction(curve)
        assert direction == "right"

    def test_unknown_without_control_points(self):
        """Should return unknown without control points."""
        curve = {
            "start": {"x": 0, "y": 0},
            "end": {"x": 100, "y": 100}
        }
        direction = determine_swing_direction(curve)
        assert direction == "unknown"


class TestFindNearbyDoorNumber:
    """Tests for door number text detection."""

    def test_finds_p_dash_number(self):
        """Should find P-XX format door numbers."""
        position = {"x": 125, "y": 125}  # Center of curve
        texts = [
            {"text": "P-01", "bbox": {"x0": 120, "y0": 120, "x1": 140, "y1": 130}},
            {"text": "ROOM", "bbox": {"x0": 200, "y0": 200, "x1": 250, "y1": 220}}
        ]
        result = find_nearby_door_number(position, texts)
        assert result == "P-01"

    def test_finds_p_number_format(self):
        """Should find PXX format and normalize to P-XX."""
        position = {"x": 125, "y": 125}
        texts = [
            {"text": "P12", "bbox": {"x0": 120, "y0": 120, "x1": 140, "y1": 130}}
        ]
        result = find_nearby_door_number(position, texts)
        assert result == "P-12"

    def test_ignores_distant_numbers(self):
        """Should not match door numbers that are too far away."""
        position = {"x": 125, "y": 125}
        texts = [
            {"text": "P-01", "bbox": {"x0": 500, "y0": 500, "x1": 520, "y1": 510}}
        ]
        result = find_nearby_door_number(position, texts, max_distance=50)
        assert result is None

    def test_finds_closest_when_multiple(self):
        """Should find the closest door number when multiple exist."""
        position = {"x": 125, "y": 125}
        texts = [
            {"text": "P-02", "bbox": {"x0": 200, "y0": 200, "x1": 220, "y1": 210}},
            {"text": "P-01", "bbox": {"x0": 120, "y0": 120, "x1": 140, "y1": 130}},
        ]
        result = find_nearby_door_number(position, texts)
        assert result == "P-01"


class TestIsDoorArc:
    """Tests for door arc detection."""

    def test_detects_valid_door_arc(self):
        """Should detect valid door arc with ~90° angle."""
        curve = {
            "start": {"x": 100, "y": 0},
            "end": {"x": 0, "y": 100},
            "center": {"x": 0, "y": 0}
        }
        assert is_door_arc(curve) is True

    def test_rejects_small_radius(self):
        """Should reject arcs with too small radius."""
        curve = {
            "start": {"x": 5, "y": 0},
            "end": {"x": 0, "y": 5},
            "center": {"x": 0, "y": 0}
        }
        assert is_door_arc(curve, min_radius=10) is False

    def test_rejects_large_radius(self):
        """Should reject arcs with too large radius."""
        curve = {
            "start": {"x": 1000, "y": 0},
            "end": {"x": 0, "y": 1000},
            "center": {"x": 0, "y": 0}
        }
        assert is_door_arc(curve, max_radius=500) is False


class TestCalculateConfidence:
    """Tests for confidence score calculation."""

    def test_base_confidence_for_arc(self):
        """Should have base confidence of 0.5 for arc detection."""
        conf = calculate_confidence("arc", has_arc=True, has_line=False, has_number=False)
        assert conf >= 0.5

    def test_higher_confidence_with_line(self):
        """Should increase confidence with associated line."""
        conf_no_line = calculate_confidence("arc", has_arc=True, has_line=False, has_number=False)
        conf_with_line = calculate_confidence("arc", has_arc=True, has_line=True, has_number=False)
        assert conf_with_line > conf_no_line

    def test_higher_confidence_with_number(self):
        """Should increase confidence with door number."""
        conf_no_num = calculate_confidence("arc", has_arc=True, has_line=False, has_number=False)
        conf_with_num = calculate_confidence("arc", has_arc=True, has_line=False, has_number=True)
        assert conf_with_num > conf_no_num

    def test_max_confidence_capped(self):
        """Confidence should not exceed 1.0."""
        conf = calculate_confidence("arc", has_arc=True, has_line=True, has_number=True, angle_quality=1.0)
        assert conf <= 1.0
    
    def test_label_detection_confidence(self):
        """Label-only detection should have lower base confidence than full arc detection."""
        # Full arc detection with line and number
        arc_full_conf = calculate_confidence("arc", has_arc=True, has_line=True, has_number=True, angle_quality=1.0)
        # Label-only detection with number
        label_conf = calculate_confidence("label", has_number=True)
        # Full arc detection should be higher confidence than label-only
        assert label_conf < arc_full_conf
        # Label base (without number) should be lower than arc base
        label_base = calculate_confidence("label", has_number=False)
        arc_base = calculate_confidence("arc", has_arc=True)
        assert label_base < arc_base


class TestDetectDoors:
    """Tests for main door detection function."""

    def test_detects_door_from_curve(self):
        """Should detect door from valid curve."""
        vectors = {
            "curves": [
                {
                    "start": {"x": 100, "y": 0},
                    "end": {"x": 0, "y": 100},
                    "center": {"x": 0, "y": 0}
                }
            ],
            "lines": [],
            "texts": [],
            "page": 1
        }
        doors = detect_doors(vectors)
        assert len(doors) == 1
        assert doors[0]["id"] == "door-001"
        assert 85 <= doors[0]["swing_angle"] <= 95

    def test_detects_door_with_number(self):
        """Should associate door number with detected door."""
        vectors = {
            "curves": [
                {
                    "start": {"x": 100, "y": 0},
                    "end": {"x": 0, "y": 100},
                    "center": {"x": 0, "y": 0}
                }
            ],
            "lines": [],
            "texts": [
                {"text": "P-05", "bbox": {"x0": 45, "y0": 45, "x1": 65, "y1": 55}}
            ],
            "page": 2
        }
        doors = detect_doors(vectors)
        assert len(doors) == 1
        assert doors[0]["number"] == "P-05"
        assert doors[0]["page"] == 2

    def test_detects_multiple_doors(self):
        """Should detect multiple doors."""
        vectors = {
            "curves": [
                {
                    "start": {"x": 100, "y": 0},
                    "end": {"x": 0, "y": 100},
                    "center": {"x": 0, "y": 0}
                },
                {
                    "start": {"x": 300, "y": 200},
                    "end": {"x": 200, "y": 300},
                    "center": {"x": 200, "y": 200}
                }
            ],
            "lines": [],
            "texts": []
        }
        doors = detect_doors(vectors)
        assert len(doors) == 2

    def test_detects_doors_from_path_segments(self):
        """Should detect doors from curves embedded in paths."""
        vectors = {
            "curves": [],
            "lines": [],
            "texts": [],
            "paths": [
                {
                    "segments": [
                        {
                            "type": "curve",
                            "start": {"x": 100, "y": 0},
                            "end": {"x": 0, "y": 100},
                            "center": {"x": 0, "y": 0}
                        }
                    ]
                }
            ]
        }
        doors = detect_doors(vectors)
        assert len(doors) == 1


class TestRunDetection:
    """Integration tests for run_detection."""

    def test_loads_and_processes_file(self, temp_dir):
        """Should load JSON file and detect doors."""
        vectors_file = temp_dir / "vectors.json"
        vectors_data = {
            "curves": [
                {
                    "start": {"x": 100, "y": 0},
                    "end": {"x": 0, "y": 100},
                    "center": {"x": 0, "y": 0}
                }
            ],
            "lines": [],
            "texts": [
                {"text": "P-01", "bbox": {"x0": 45, "y0": 45, "x1": 65, "y1": 55}}
            ],
            "page": 1
        }
        with open(vectors_file, "w") as f:
            json.dump(vectors_data, f)

        results = run_detection(str(vectors_file))

        assert results["total_doors"] == 1
        assert results["doors"][0]["number"] == "P-01"

    def test_handles_multiple_pages(self, temp_dir):
        """Should handle multi-page vector data."""
        vectors_file = temp_dir / "vectors.json"
        vectors_data = {
            "pages": [
                {
                    "page": 1,
                    "curves": [
                        {"start": {"x": 100, "y": 0}, "end": {"x": 0, "y": 100}, "center": {"x": 0, "y": 0}}
                    ],
                    "lines": [],
                    "texts": []
                },
                {
                    "page": 2,
                    "curves": [
                        {"start": {"x": 50, "y": 0}, "end": {"x": 0, "y": 50}, "center": {"x": 0, "y": 0}}
                    ],
                    "lines": [],
                    "texts": []
                }
            ]
        }
        with open(vectors_file, "w") as f:
            json.dump(vectors_data, f)

        results = run_detection(str(vectors_file))

        assert results["total_doors"] == 2

    def test_writes_output_file(self, temp_dir):
        """Should write results to output file."""
        vectors_file = temp_dir / "vectors.json"
        output_file = temp_dir / "output" / "doors.json"

        vectors_data = {
            "curves": [
                {"start": {"x": 100, "y": 0}, "end": {"x": 0, "y": 100}, "center": {"x": 0, "y": 0}}
            ],
            "lines": [],
            "texts": []
        }
        with open(vectors_file, "w") as f:
            json.dump(vectors_data, f)

        run_detection(str(vectors_file), str(output_file))

        assert output_file.exists()
        with open(output_file) as f:
            saved = json.load(f)
        assert saved["total_doors"] == 1


class TestDoorOutputFormat:
    """Tests for door output structure."""

    def test_door_has_required_fields(self):
        """Each door should have all required fields."""
        vectors = {
            "curves": [
                {
                    "start": {"x": 100, "y": 0},
                    "end": {"x": 0, "y": 100},
                    "center": {"x": 0, "y": 0}
                }
            ],
            "lines": [],
            "texts": [],
            "page": 1
        }
        doors = detect_doors(vectors)

        assert len(doors) == 1
        door = doors[0]

        assert "id" in door
        assert "number" in door
        assert "position" in door
        assert "swing_angle" in door
        assert "direction" in door
        assert "width_estimate" in door
        assert "confidence" in door
        assert "page" in door

    def test_position_has_xy(self):
        """Position should have x and y coordinates."""
        vectors = {
            "curves": [
                {"start": {"x": 100, "y": 0}, "end": {"x": 0, "y": 100}, "center": {"x": 0, "y": 0}}
            ],
            "lines": [],
            "texts": []
        }
        doors = detect_doors(vectors)
        position = doors[0]["position"]

        assert "x" in position
        assert "y" in position


class TestIsDoorLabel:
    """Tests for door label pattern matching."""

    def test_matches_p_dash_format(self):
        """Should match P-XX format."""
        assert is_door_label("P-01") is True
        assert is_door_label("P-123") is True
        assert is_door_label("P-01A") is True

    def test_matches_p_format(self):
        """Should match PXX format without dash."""
        assert is_door_label("P01") is True
        assert is_door_label("P12") is True

    def test_matches_porte_format(self):
        """Should match PORTE format (French)."""
        assert is_door_label("PORTE 1") is True
        assert is_door_label("PORTE12") is True

    def test_matches_d_format(self):
        """Should match D-XX format (English)."""
        assert is_door_label("D-01") is True
        assert is_door_label("D01") is True

    def test_rejects_room_numbers(self):
        """Should not match room numbers."""
        assert is_door_label("100") is False
        assert is_door_label("ROOM 101") is False
        assert is_door_label("LOCAL 109") is False

    def test_rejects_random_text(self):
        """Should not match random text."""
        assert is_door_label("CORRIDOR") is False
        assert is_door_label("STAIRS") is False


class TestNormalizeDoorNumber:
    """Tests for door number normalization."""

    def test_normalizes_to_p_format(self):
        """Should normalize various formats to P-XX."""
        assert normalize_door_number("P-01") == "P-01"
        assert normalize_door_number("P01") == "P-01"
        assert normalize_door_number("P1") == "P-01"
        assert normalize_door_number("P-123") == "P-123"

    def test_preserves_suffix(self):
        """Should preserve letter suffix."""
        assert normalize_door_number("P-01A") == "P-01A"
        assert normalize_door_number("P12B") == "P-12B"


class TestLabelBasedDetection:
    """Tests for label-only door detection."""

    def test_detects_doors_from_labels_only(self):
        """Should detect doors from labels when no arcs present."""
        vectors = {
            "curves": [],
            "lines": [],
            "texts": [
                {"text": "P-01", "bbox": {"x0": 100, "y0": 100, "x1": 120, "y1": 110}},
                {"text": "P-02", "bbox": {"x0": 200, "y0": 200, "x1": 220, "y1": 210}}
            ],
            "page": 1
        }
        doors = detect_doors(vectors)

        assert len(doors) == 2
        assert doors[0]["number"] == "P-01"
        assert doors[1]["number"] == "P-02"
        assert doors[0]["detection_method"] == "label"

    def test_label_doors_have_null_swing(self):
        """Label-only doors should have null swing angle."""
        vectors = {
            "curves": [],
            "lines": [],
            "texts": [
                {"text": "P-01", "bbox": {"x0": 100, "y0": 100, "x1": 120, "y1": 110}}
            ]
        }
        doors = detect_doors(vectors)

        assert len(doors) == 1
        assert doors[0]["swing_angle"] is None
        assert doors[0]["width_estimate"] is None
        assert doors[0]["direction"] == "unknown"

    def test_combines_arc_and_label_detection(self):
        """Should combine arc-detected and label-detected doors."""
        vectors = {
            "curves": [
                {"start": {"x": 100, "y": 0}, "end": {"x": 0, "y": 100}, "center": {"x": 0, "y": 0}}
            ],
            "lines": [],
            "texts": [
                {"text": "P-01", "bbox": {"x0": 45, "y0": 45, "x1": 65, "y1": 55}},  # Near arc
                {"text": "P-02", "bbox": {"x0": 500, "y0": 500, "x1": 520, "y1": 510}}  # Far from arc
            ],
            "page": 1
        }
        doors = detect_doors(vectors)

        # Should have 2 doors: one arc-detected with P-01, one label-only with P-02
        assert len(doors) == 2
        
        arc_door = next(d for d in doors if d["detection_method"] == "arc")
        label_door = next(d for d in doors if d["detection_method"] == "label")
        
        assert arc_door["number"] == "P-01"
        assert label_door["number"] == "P-02"

    def test_avoids_duplicate_doors(self):
        """Should not create duplicate doors from same label near arc."""
        vectors = {
            "curves": [
                {"start": {"x": 100, "y": 0}, "end": {"x": 0, "y": 100}, "center": {"x": 0, "y": 0}}
            ],
            "lines": [],
            "texts": [
                {"text": "P-01", "bbox": {"x0": 45, "y0": 45, "x1": 65, "y1": 55}}  # Near arc
            ],
            "page": 1
        }
        doors = detect_doors(vectors)

        # Should only have 1 door (arc-detected with P-01), not 2
        assert len(doors) == 1
        assert doors[0]["detection_method"] == "arc"
        assert doors[0]["number"] == "P-01"
