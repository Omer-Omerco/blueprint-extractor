"""
Tests for page_selector.py
"""

import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from page_selector import select_pages, _diversify_indices


class TestSelectPages:
    """Tests for select_pages function."""

    @pytest.fixture
    def sample_page_types(self):
        """Sample page classification data."""
        return {
            "source_pdf": "/test/blueprint.pdf",
            "page_count": 10,
            "pages": [
                {"page": 1, "type": "LEGEND", "scores": {"LEGEND": 25, "PLAN": 0, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
                {"page": 2, "type": "PLAN", "scores": {"LEGEND": 0, "PLAN": 30, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
                {"page": 3, "type": "PLAN", "scores": {"LEGEND": 0, "PLAN": 25, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
                {"page": 4, "type": "PLAN", "scores": {"LEGEND": 0, "PLAN": 20, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
                {"page": 5, "type": "PLAN", "scores": {"LEGEND": 0, "PLAN": 15, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
                {"page": 6, "type": "PLAN", "scores": {"LEGEND": 0, "PLAN": 10, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
                {"page": 7, "type": "DETAIL", "scores": {"LEGEND": 0, "PLAN": 0, "DETAIL": 20, "ELEVATION": 0, "OTHER": 0}},
                {"page": 8, "type": "ELEVATION", "scores": {"LEGEND": 0, "PLAN": 0, "DETAIL": 0, "ELEVATION": 15, "OTHER": 0}},
                {"page": 9, "type": "OTHER", "scores": {"LEGEND": 0, "PLAN": 0, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
                {"page": 10, "type": "OTHER", "scores": {"LEGEND": 0, "PLAN": 0, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
            ]
        }

    def test_select_5_pages_with_legend(self, sample_page_types):
        """Test selecting 5 pages when LEGEND is available."""
        result = select_pages(sample_page_types, n=5)

        assert result["selection_count"] == 5
        assert result["requested_count"] == 5

        # Check that LEGEND is included
        page_types = [p["type"] for p in result["selected"]]
        assert "LEGEND" in page_types

        # Check that we have PLAN pages
        plan_count = sum(1 for p in result["selected"] if p["type"] == "PLAN")
        assert plan_count == 4  # 5 - 1 LEGEND = 4 PLAN

    def test_select_without_legend(self):
        """Test selecting when no LEGEND page exists."""
        page_types = {
            "source_pdf": "/test/blueprint.pdf",
            "pages": [
                {"page": 1, "type": "PLAN", "scores": {"LEGEND": 0, "PLAN": 30, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
                {"page": 2, "type": "PLAN", "scores": {"LEGEND": 0, "PLAN": 25, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
                {"page": 3, "type": "PLAN", "scores": {"LEGEND": 0, "PLAN": 20, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
                {"page": 4, "type": "DETAIL", "scores": {"LEGEND": 0, "PLAN": 0, "DETAIL": 15, "ELEVATION": 0, "OTHER": 0}},
                {"page": 5, "type": "OTHER", "scores": {"LEGEND": 0, "PLAN": 0, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
            ]
        }

        result = select_pages(page_types, n=5)

        # Should have all 3 PLAN pages + 2 fallback
        assert result["selection_count"] == 5
        assert "0 LEGEND" in result["strategy"]

    def test_fallback_to_first_pages(self):
        """Test fallback when not enough PLAN pages."""
        page_types = {
            "source_pdf": "/test/blueprint.pdf",
            "pages": [
                {"page": 1, "type": "LEGEND", "scores": {"LEGEND": 25, "PLAN": 0, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
                {"page": 2, "type": "PLAN", "scores": {"LEGEND": 0, "PLAN": 20, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
                {"page": 3, "type": "OTHER", "scores": {"LEGEND": 0, "PLAN": 0, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
                {"page": 4, "type": "OTHER", "scores": {"LEGEND": 0, "PLAN": 0, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
            ]
        }

        result = select_pages(page_types, n=5)

        # Only 4 pages available, should select all
        assert result["selection_count"] == 4
        assert "FALLBACK" in result["strategy"]

    def test_empty_pages(self):
        """Test with no pages."""
        page_types = {
            "source_pdf": "/test/blueprint.pdf",
            "pages": []
        }

        result = select_pages(page_types, n=5)

        assert result["selection_count"] == 0
        assert "empty" in result["strategy"]

    def test_pages_sorted_by_page_number(self, sample_page_types):
        """Test that selected pages are sorted by page number."""
        result = select_pages(sample_page_types, n=5)

        page_nums = [p["page"] for p in result["selected"]]
        assert page_nums == sorted(page_nums)

    def test_select_fewer_than_available(self, sample_page_types):
        """Test selecting fewer pages than available."""
        result = select_pages(sample_page_types, n=3)

        assert result["selection_count"] == 3
        assert result["requested_count"] == 3

    def test_select_more_than_available(self):
        """Test requesting more pages than available."""
        page_types = {
            "source_pdf": "/test/blueprint.pdf",
            "pages": [
                {"page": 1, "type": "PLAN", "scores": {"LEGEND": 0, "PLAN": 20, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
                {"page": 2, "type": "PLAN", "scores": {"LEGEND": 0, "PLAN": 15, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}},
            ]
        }

        result = select_pages(page_types, n=10)

        # Should return all available pages
        assert result["selection_count"] == 2
        assert result["requested_count"] == 10

    def test_diversified_plan_selection(self):
        """Test that PLAN pages are diversified (not just top N)."""
        # 10 PLAN pages with decreasing scores
        page_types = {
            "source_pdf": "/test/blueprint.pdf",
            "pages": [
                {"page": i, "type": "PLAN", "scores": {"LEGEND": 0, "PLAN": 100 - i*5, "DETAIL": 0, "ELEVATION": 0, "OTHER": 0}}
                for i in range(1, 11)
            ]
        }

        result = select_pages(page_types, n=5)

        # Should include page 1 (best) but also spread across others
        page_nums = [p["page"] for p in result["selected"]]
        assert 1 in page_nums  # Best score should always be included


class TestDiversifyIndices:
    """Tests for _diversify_indices helper function."""

    def test_count_equals_total(self):
        """Test when count equals total."""
        indices = _diversify_indices(5, 5)
        assert indices == [0, 1, 2, 3, 4]

    def test_count_greater_than_total(self):
        """Test when count exceeds total."""
        indices = _diversify_indices(3, 10)
        assert indices == [0, 1, 2]

    def test_select_one(self):
        """Test selecting just one index."""
        indices = _diversify_indices(10, 1)
        assert indices == [0]

    def test_select_zero(self):
        """Test selecting zero indices."""
        indices = _diversify_indices(10, 0)
        assert indices == []

    def test_spread_evenly(self):
        """Test that indices are spread evenly."""
        indices = _diversify_indices(10, 3)
        # Should be [0, 5, 9] or similar spread
        assert 0 in indices  # First always included
        assert len(indices) == 3
        # Check spread
        assert max(indices) - min(indices) > 2

    def test_unique_indices(self):
        """Test that all indices are unique."""
        for total in range(1, 20):
            for count in range(1, total + 1):
                indices = _diversify_indices(total, count)
                assert len(indices) == len(set(indices)), f"Duplicates for total={total}, count={count}"

    def test_sorted_output(self):
        """Test that output is sorted."""
        indices = _diversify_indices(100, 10)
        assert indices == sorted(indices)


class TestIntegrationWithRealData:
    """Integration tests with real classified data."""

    @pytest.fixture
    def real_page_types_path(self):
        """Path to real page types if available."""
        path = Path(__file__).parent.parent / "output" / "page_types.json"
        return path

    def test_with_classified_pdf(self, real_page_types_path):
        """Test selection with real classified data."""
        if not real_page_types_path.exists():
            pytest.skip("No real page_types.json available")

        with open(real_page_types_path) as f:
            page_types = json.load(f)

        result = select_pages(page_types, n=5)

        assert result["selection_count"] > 0
        assert result["selection_count"] <= 5
        assert len(result["selected"]) == result["selection_count"]
