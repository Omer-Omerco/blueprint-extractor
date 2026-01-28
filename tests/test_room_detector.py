"""
Tests for room_detector.py
"""

import json
import pytest
import tempfile
from pathlib import Path

# Import the module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from room_detector import (
    match_room_number,
    is_room_name,
    calculate_distance,
    find_nearby_name,
    calculate_expanded_bbox,
    detect_rooms_in_page,
    detect_rooms,
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
def sample_page_data():
    """Sample page data with rooms."""
    return {
        "page_number": 12,
        "dimensions": {
            "width_pts": 792,
            "height_pts": 612,
            "width_px": 3300,
            "height_px": 2550,
            "scale_factor": 4.166
        },
        "text_blocks": [
            {"text": "101", "bbox": {"x": 500, "y": 400, "width": 30, "height": 20}},
            {"text": "CLASSE", "bbox": {"x": 490, "y": 370, "width": 60, "height": 15}},
            {"text": "102", "bbox": {"x": 800, "y": 400, "width": 30, "height": 20}},
            {"text": "BUREAU", "bbox": {"x": 790, "y": 370, "width": 60, "height": 15}},
            {"text": "103", "bbox": {"x": 1100, "y": 400, "width": 30, "height": 20}},
            {"text": "S.D.B.", "bbox": {"x": 1090, "y": 370, "width": 50, "height": 15}},
            {"text": "Random Text", "bbox": {"x": 2000, "y": 2000, "width": 100, "height": 20}},
            {"text": "A-204", "bbox": {"x": 500, "y": 600, "width": 40, "height": 20}},
            {"text": "CORRIDOR", "bbox": {"x": 480, "y": 570, "width": 80, "height": 15}},
        ],
        "drawings": []
    }


@pytest.fixture
def sample_vectors_data(sample_page_data):
    """Sample vectors data structure."""
    return {
        "source": "/path/to/test.pdf",
        "total_pages": 20,
        "dpi": 300,
        "pages": [sample_page_data]
    }


# =============================================================================
# Unit Tests - Pattern Matching
# =============================================================================

class TestMatchRoomNumber:
    """Tests for match_room_number function."""

    def test_three_digit_number(self):
        number, confidence = match_room_number("101")
        assert number == "101"
        assert confidence == 1.0

    def test_three_digit_number_200s(self):
        number, confidence = match_room_number("204")
        assert number == "204"
        assert confidence == 1.0

    def test_prefix_pattern(self):
        number, confidence = match_room_number("A-101")
        assert number == "A-101"
        assert confidence == 1.0

    def test_prefix_no_dash(self):
        number, confidence = match_room_number("B204")
        assert number == "B204"
        assert confidence == 1.0

    def test_suffix_letter(self):
        number, confidence = match_room_number("101A")
        assert number == "101A"
        assert confidence == 0.95

    def test_two_digit(self):
        number, confidence = match_room_number("25")
        assert number == "25"
        assert confidence == 0.8

    def test_four_digit(self):
        number, confidence = match_room_number("1234")
        assert number == "1234"
        assert confidence == 0.8

    def test_not_a_room_number(self):
        number, confidence = match_room_number("CLASSE")
        assert number is None
        assert confidence == 0.0

    def test_empty_string(self):
        number, confidence = match_room_number("")
        assert number is None
        assert confidence == 0.0

    def test_whitespace_stripped(self):
        number, confidence = match_room_number("  101  ")
        assert number == "101"
        assert confidence == 1.0


class TestIsRoomName:
    """Tests for is_room_name function."""

    def test_classe(self):
        assert is_room_name("CLASSE") is True
        assert is_room_name("classe") is True

    def test_corridor(self):
        assert is_room_name("CORRIDOR") is True
        assert is_room_name("CORR.") is True
        assert is_room_name("CORR") is True

    def test_sdb(self):
        assert is_room_name("S.D.B.") is True
        assert is_room_name("SDB") is True
        assert is_room_name("SALLE DE BAIN") is True

    def test_wc(self):
        assert is_room_name("W.C.") is True
        assert is_room_name("WC") is True
        assert is_room_name("TOILETTE") is True
        assert is_room_name("TOILETTES") is True

    def test_rangement(self):
        assert is_room_name("RANGEMENT") is True
        assert is_room_name("RANG.") is True

    def test_mecanique(self):
        assert is_room_name("MÉCANIQUE") is True
        assert is_room_name("MÉC.") is True

    def test_bureau(self):
        assert is_room_name("BUREAU") is True
        assert is_room_name("BUR.") is True

    def test_gymnase(self):
        assert is_room_name("GYMNASE") is True
        assert is_room_name("GYM.") is True

    def test_not_room_name(self):
        assert is_room_name("101") is False
        assert is_room_name("Random Text") is False
        assert is_room_name("") is False


class TestCalculateDistance:
    """Tests for calculate_distance function."""

    def test_same_position(self):
        bbox = {"x": 100, "y": 100, "width": 50, "height": 20}
        distance = calculate_distance(bbox, bbox)
        assert distance == 0

    def test_horizontal_distance(self):
        bbox1 = {"x": 0, "y": 0, "width": 100, "height": 100}
        bbox2 = {"x": 200, "y": 0, "width": 100, "height": 100}
        # Centers: (50, 50) and (250, 50)
        distance = calculate_distance(bbox1, bbox2)
        assert distance == 200

    def test_vertical_distance(self):
        bbox1 = {"x": 0, "y": 0, "width": 100, "height": 100}
        bbox2 = {"x": 0, "y": 200, "width": 100, "height": 100}
        # Centers: (50, 50) and (50, 250)
        distance = calculate_distance(bbox1, bbox2)
        assert distance == 200

    def test_diagonal_distance(self):
        bbox1 = {"x": 0, "y": 0, "width": 0, "height": 0}
        bbox2 = {"x": 3, "y": 4, "width": 0, "height": 0}
        distance = calculate_distance(bbox1, bbox2)
        assert distance == 5  # 3-4-5 triangle


class TestFindNearbyName:
    """Tests for find_nearby_name function."""

    def test_finds_name_above(self, sample_page_data):
        room_block = sample_page_data["text_blocks"][0]  # 101
        text_blocks = sample_page_data["text_blocks"]

        name = find_nearby_name(room_block, text_blocks)
        assert name == "CLASSE"

    def test_finds_correct_name_for_each_room(self, sample_page_data):
        text_blocks = sample_page_data["text_blocks"]

        # Room 102 should find BUREAU
        room_102 = text_blocks[2]
        name = find_nearby_name(room_102, text_blocks)
        assert name == "BUREAU"

        # Room 103 should find S.D.B.
        room_103 = text_blocks[4]
        name = find_nearby_name(room_103, text_blocks)
        assert name == "S.D.B."

    def test_respects_max_distance(self, sample_page_data):
        text_blocks = sample_page_data["text_blocks"]
        room_block = text_blocks[0]  # 101

        # With very small max_distance, should not find name
        name = find_nearby_name(room_block, text_blocks, max_distance=5)
        assert name is None

    def test_no_name_found(self):
        room_block = {"text": "999", "bbox": {"x": 100, "y": 100, "width": 30, "height": 20}}
        text_blocks = [
            room_block,
            {"text": "Random", "bbox": {"x": 5000, "y": 5000, "width": 50, "height": 15}}
        ]

        name = find_nearby_name(room_block, text_blocks)
        assert name is None


class TestCalculateExpandedBbox:
    """Tests for calculate_expanded_bbox function."""

    def test_room_only(self):
        room_block = {"bbox": {"x": 100, "y": 100, "width": 30, "height": 20}}

        bbox = calculate_expanded_bbox(room_block, padding=10)

        assert bbox["x"] == 90
        assert bbox["y"] == 90
        assert bbox["width"] == 50
        assert bbox["height"] == 40

    def test_with_name_block(self):
        room_block = {"bbox": {"x": 100, "y": 120, "width": 30, "height": 20}}
        name_block = {"bbox": {"x": 90, "y": 90, "width": 60, "height": 15}}

        bbox = calculate_expanded_bbox(room_block, name_block, padding=10)

        # x: min(100, 90) - 10 = 80
        # y: min(120, 90) - 10 = 80
        # x_max: max(130, 150) + 10 = 160
        # y_max: max(140, 105) + 10 = 150
        assert bbox["x"] == 80
        assert bbox["y"] == 80
        assert bbox["width"] == 80  # 160 - 80
        assert bbox["height"] == 70  # 150 - 80

    def test_no_negative_coords(self):
        room_block = {"bbox": {"x": 5, "y": 5, "width": 10, "height": 10}}

        bbox = calculate_expanded_bbox(room_block, padding=20)

        assert bbox["x"] == 0  # Clamped to 0
        assert bbox["y"] == 0


# =============================================================================
# Integration Tests
# =============================================================================

class TestDetectRoomsInPage:
    """Tests for detect_rooms_in_page function."""

    def test_detects_all_rooms(self, sample_page_data):
        rooms = detect_rooms_in_page(sample_page_data)

        # Should find 4 rooms: 101, 102, 103, A-204
        assert len(rooms) == 4

    def test_room_structure(self, sample_page_data):
        rooms = detect_rooms_in_page(sample_page_data)

        room = rooms[0]
        assert "number" in room
        assert "name" in room
        assert "confidence" in room
        assert "bbox" in room
        assert "number_bbox" in room
        assert "page" in room

    def test_rooms_have_correct_names(self, sample_page_data):
        rooms = detect_rooms_in_page(sample_page_data)

        room_dict = {r["number"]: r for r in rooms}

        assert room_dict["101"]["name"] == "CLASSE"
        assert room_dict["102"]["name"] == "BUREAU"
        assert room_dict["103"]["name"] == "S.D.B."
        assert room_dict["A-204"]["name"] == "CORRIDOR"

    def test_confidence_scores(self, sample_page_data):
        rooms = detect_rooms_in_page(sample_page_data)

        room_dict = {r["number"]: r for r in rooms}

        # 3-digit should be 1.0
        assert room_dict["101"]["confidence"] == 1.0
        # A-xxx should be 1.0
        assert room_dict["A-204"]["confidence"] == 1.0


class TestDetectRooms:
    """Tests for detect_rooms function."""

    def test_detects_rooms_all_pages(self, sample_vectors_data):
        result = detect_rooms(sample_vectors_data)

        assert "rooms" in result
        assert "stats" in result
        assert result["stats"]["total_rooms"] == 4
        assert result["stats"]["with_names"] == 4

    def test_stats_by_page(self, sample_vectors_data):
        result = detect_rooms(sample_vectors_data)

        assert "12" in result["stats"]["by_page"]
        assert result["stats"]["by_page"]["12"] == 4

    def test_preserves_source(self, sample_vectors_data):
        result = detect_rooms(sample_vectors_data)

        assert result["source"] == sample_vectors_data["source"]
        assert result["total_pages"] == sample_vectors_data["total_pages"]


class TestIntegrationWithRealPDF:
    """Integration tests with real extracted vectors."""

    def test_full_pipeline(self, real_pdf_path, temp_output_dir):
        """Test full pipeline: extract vectors then detect rooms."""
        # Import extract function
        from extract_pdf_vectors import extract_pdf_vectors

        # Extract vectors from page 12
        vectors = extract_pdf_vectors(
            str(real_pdf_path),
            pages=[12]
        )

        # Detect rooms
        result = detect_rooms(vectors)

        # Should find some rooms
        assert result["stats"]["total_rooms"] > 0
        print(f"Found {result['stats']['total_rooms']} rooms")

        # Check room structure
        if result["rooms"]:
            room = result["rooms"][0]
            assert "number" in room
            assert "bbox" in room
            assert room["page"] == 12

    def test_finds_room_numbers(self, real_pdf_path, temp_output_dir):
        """Test that room numbers are found."""
        from extract_pdf_vectors import extract_pdf_vectors

        vectors = extract_pdf_vectors(
            str(real_pdf_path),
            pages=[12]
        )

        result = detect_rooms(vectors)

        room_numbers = [r["number"] for r in result["rooms"]]
        print(f"Found room numbers: {room_numbers}")

        # Should find at least some 3-digit numbers
        three_digit = [n for n in room_numbers if n.isdigit() and len(n) == 3]
        assert len(three_digit) > 0, "Should find 3-digit room numbers"

    def test_output_to_file(self, real_pdf_path, temp_output_dir):
        """Test writing output to file."""
        from extract_pdf_vectors import extract_pdf_vectors

        vectors = extract_pdf_vectors(
            str(real_pdf_path),
            pages=[12]
        )

        result = detect_rooms(vectors)

        output_file = temp_output_dir / "rooms_detected.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)

        assert output_file.exists()

        # Verify it can be read back
        with open(output_file) as f:
            loaded = json.load(f)

        assert loaded["stats"]["total_rooms"] == result["stats"]["total_rooms"]
