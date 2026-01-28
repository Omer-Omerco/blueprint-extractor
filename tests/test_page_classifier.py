"""
Tests for page_classifier.py
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from page_classifier import (
    compute_scores,
    classify_page,
    KEYWORDS,
    ROOM_NUMBER_PATTERN,
)


class TestComputeScores:
    """Tests for compute_scores function."""

    def test_legend_keywords(self):
        """Test LEGEND detection with French keywords."""
        text = "LÉGENDE DES SYMBOLES\nVoir nomenclature"
        scores = compute_scores(text)
        assert scores["LEGEND"] > scores["PLAN"]
        assert scores["LEGEND"] > 0

    def test_plan_keywords(self):
        """Test PLAN detection with floor-related keywords."""
        text = "NIVEAU 1 - ÉTAGE\nRez-de-chaussée"
        scores = compute_scores(text)
        assert scores["PLAN"] > scores["LEGEND"]
        assert scores["PLAN"] > 0

    def test_plan_room_numbers(self):
        """Test PLAN detection with 3-digit room numbers."""
        text = "101 CLASSE\n102 BUREAU\n103 CORRIDOR\n104 S.D.B."
        scores = compute_scores(text)
        assert scores["PLAN"] > 0
        # 4 room numbers * 2 weight = 8

    def test_room_number_score_capped(self):
        """Test that room number contribution is capped."""
        # Generate many room numbers
        rooms = " ".join(str(i) for i in range(100, 200))
        scores = compute_scores(rooms)
        # Should be capped at 20 (ROOM_NUMBER_MAX_SCORE)
        assert scores["PLAN"] == 20

    def test_detail_keywords(self):
        """Test DETAIL detection."""
        text = "DÉTAIL A - COUPE SECTION"
        scores = compute_scores(text)
        assert scores["DETAIL"] > scores["OTHER"]

    def test_elevation_keywords(self):
        """Test ELEVATION detection."""
        text = "ÉLÉVATION NORD - FAÇADE PRINCIPALE"
        scores = compute_scores(text)
        assert scores["ELEVATION"] > scores["OTHER"]

    def test_empty_text(self):
        """Test with empty text returns zero scores."""
        scores = compute_scores("")
        assert all(v == 0 for v in scores.values())

    def test_case_insensitive(self):
        """Test that scoring is case-insensitive."""
        text1 = "LÉGENDE"
        text2 = "légende"
        text3 = "Légende"
        assert compute_scores(text1) == compute_scores(text2) == compute_scores(text3)


class TestClassifyPage:
    """Tests for classify_page function."""

    def test_classify_legend(self):
        """Test classification of a LEGEND page."""
        text = """
        LÉGENDE DES SYMBOLES
        ━━━━━━━━━━━━━━━━━━━━
        ○ Luminaire encastré
        □ Prise électrique
        △ Sortie de secours
        """
        page_type, scores = classify_page(text)
        assert page_type == "LEGEND"

    def test_classify_plan(self):
        """Test classification of a PLAN page."""
        text = """
        PLAN DU REZ-DE-CHAUSSÉE - NIVEAU 1

        101 CLASSE
        102 CLASSE
        103 CORRIDOR
        104 S.D.B.
        105 RANGEMENT
        """
        page_type, scores = classify_page(text)
        assert page_type == "PLAN"

    def test_classify_detail(self):
        """Test classification of a DETAIL page."""
        text = """
        DÉTAIL A - COUPE DE MUR TYPE
        SECTION B-B
        ASSEMBLAGE DE FENÊTRE
        """
        page_type, scores = classify_page(text)
        assert page_type == "DETAIL"

    def test_classify_elevation(self):
        """Test classification of an ELEVATION page."""
        text = """
        ÉLÉVATION NORD
        FAÇADE PRINCIPALE
        VUE EST
        """
        page_type, scores = classify_page(text)
        assert page_type == "ELEVATION"

    def test_classify_other(self):
        """Test classification of an OTHER page (no clear indicators)."""
        text = "Page blanche ou contenu non pertinent"
        page_type, scores = classify_page(text)
        assert page_type == "OTHER"

    def test_classify_mixed_content(self):
        """Test with mixed content - should pick highest score."""
        # PLAN has more indicators
        text = """
        NIVEAU 2 - ÉTAGE
        101 CLASSE
        102 BUREAU
        Voir détail A
        """
        page_type, scores = classify_page(text)
        assert page_type == "PLAN"


class TestRoomNumberPattern:
    """Tests for room number regex pattern."""

    def test_three_digit_numbers(self):
        """Test that 3-digit numbers starting with 1-9 are matched."""
        text = "101 102 103 201 301"
        matches = ROOM_NUMBER_PATTERN.findall(text)
        assert len(matches) == 5
        assert "101" in matches

    def test_no_leading_zero(self):
        """Test that numbers starting with 0 are not matched."""
        text = "001 010 099"
        matches = ROOM_NUMBER_PATTERN.findall(text)
        assert len(matches) == 0

    def test_four_digit_not_matched(self):
        """Test that 4-digit numbers are not matched as room numbers."""
        text = "1001 2022"
        matches = ROOM_NUMBER_PATTERN.findall(text)
        assert len(matches) == 0

    def test_two_digit_not_matched(self):
        """Test that 2-digit numbers are not matched."""
        text = "10 99"
        matches = ROOM_NUMBER_PATTERN.findall(text)
        assert len(matches) == 0


class TestKeywordConfig:
    """Tests for keyword configuration."""

    def test_all_types_have_keywords(self):
        """Test that all page types have keywords defined."""
        expected_types = {"LEGEND", "PLAN", "DETAIL", "ELEVATION"}
        assert set(KEYWORDS.keys()) == expected_types

    def test_keywords_have_weights(self):
        """Test that all keywords have positive weights."""
        for page_type, keywords in KEYWORDS.items():
            for keyword, weight in keywords.items():
                assert weight > 0, f"{keyword} in {page_type} has non-positive weight"


class TestIntegrationWithRealPDF:
    """Integration tests with real PDF file."""

    @pytest.fixture
    def test_pdf_path(self):
        """Path to test PDF."""
        path = Path(__file__).parent.parent / "output" / "C25-256 _Architecture_plan_Construction.pdf"
        if not path.exists():
            pytest.skip(f"Test PDF not found: {path}")
        return path

    def test_classify_real_pdf_sample(self, test_pdf_path):
        """Test classification on a few pages of real PDF."""
        from page_classifier import extract_page_text, classify_page, get_page_count

        page_count = get_page_count(test_pdf_path)
        assert page_count > 0

        # Test first 3 pages
        results = []
        for page_num in range(1, min(4, page_count + 1)):
            text = extract_page_text(test_pdf_path, page_num)
            page_type, scores = classify_page(text)
            results.append({
                "page": page_num,
                "type": page_type,
                "scores": scores
            })

        # Should have classified some pages
        assert len(results) > 0
        # All types should be valid
        valid_types = {"LEGEND", "PLAN", "DETAIL", "ELEVATION", "OTHER"}
        for r in results:
            assert r["type"] in valid_types
