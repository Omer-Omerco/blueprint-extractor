"""Tests for scripts/sniper.py — Sniper Mode (on-the-fly room crops)."""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Import helpers – sniper.py lives under scripts/, not a package.
# We add its parent to sys.path so we can import it.
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import sniper  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures – lightweight fitz fakes
# ---------------------------------------------------------------------------

class FakeRect:
    """Minimal stand-in for fitz.Rect."""
    def __init__(self, x0=100, y0=200, x1=150, y1=230):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.width = x1 - x0
        self.height = y1 - y0


class FakePage:
    """Minimal stand-in for a fitz page."""
    def __init__(self, search_results=None, text="CLASSE 204"):
        self._search_results = search_results or []
        self._text = text
        self.rect = FakeRect(0, 0, 2000, 1400)

    def search_for(self, term):
        return self._search_results

    def get_text(self, mode="text", clip=None):
        return self._text

    def get_pixmap(self, matrix=None, clip=None):
        pix = MagicMock()
        pix.save = MagicMock()
        return pix


class FakeDoc:
    """Minimal stand-in for fitz.Document."""
    def __init__(self, pages=None):
        self._pages = pages or []

    def __len__(self):
        return len(self._pages)

    def __getitem__(self, idx):
        return self._pages[idx]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def close(self):
        pass


# ---------------------------------------------------------------------------
# PAGE_TO_PLAN mapping tests
# ---------------------------------------------------------------------------

class TestPageToPlan:
    """Validate the PAGE_TO_PLAN mapping structure."""

    def test_has_35_pages(self):
        assert len(sniper.PAGE_TO_PLAN) == 35

    def test_pages_0_to_34(self):
        for i in range(35):
            assert i in sniper.PAGE_TO_PLAN, f"Missing page {i}"

    def test_all_values_start_with_A(self):
        for page, plan in sniper.PAGE_TO_PLAN.items():
            assert plan.startswith("A-"), f"Page {page}: {plan} doesn't start with A-"

    def test_key_plans_present(self):
        """Critical plans must exist in the mapping."""
        values = set(sniper.PAGE_TO_PLAN.values())
        for plan in ["A-150", "A-151", "A-250", "A-900", "A-950"]:
            assert plan in values, f"{plan} missing from mapping"

    def test_plan_descriptions_cover_all_plans(self):
        """Every plan ID in the mapping should have a description."""
        for plan in sniper.PAGE_TO_PLAN.values():
            assert plan in sniper.PLAN_DESCRIPTIONS, (
                f"{plan} has no description in PLAN_DESCRIPTIONS"
            )


# ---------------------------------------------------------------------------
# find_room_on_pages tests
# ---------------------------------------------------------------------------

class TestFindRoomOnPages:
    def _make_doc(self, hits_on_pages: dict[int, list] | None = None):
        """Build a FakeDoc with 35 pages. hits_on_pages = {page_idx: [FakeRect,...]}"""
        hits_on_pages = hits_on_pages or {}
        pages = []
        for i in range(35):
            rects = hits_on_pages.get(i, [])
            pages.append(FakePage(search_results=rects, text=f"CLASSE 204 context p{i}"))
        return FakeDoc(pages)

    def test_room_not_found(self):
        doc = self._make_doc({})
        results = sniper.find_room_on_pages(doc, "A-999")
        assert results == []

    def test_room_found_single_page(self):
        doc = self._make_doc({8: [FakeRect(100, 200, 150, 230)]})
        results = sniper.find_room_on_pages(doc, "A-204")
        assert len(results) == 1
        assert results[0]["page_idx"] == 8
        assert results[0]["plan_id"] == "A-150"

    def test_room_found_multiple_pages(self):
        doc = self._make_doc({
            8: [FakeRect(100, 200, 150, 230)],
            29: [FakeRect(300, 400, 350, 430)],
        })
        results = sniper.find_room_on_pages(doc, "A-204")
        page_indices = [r["page_idx"] for r in results]
        assert 8 in page_indices
        assert 29 in page_indices

    def test_room_id_without_prefix(self):
        """Should handle bare number '204' the same as 'A-204'."""
        doc = self._make_doc({8: [FakeRect()]})
        results = sniper.find_room_on_pages(doc, "204")
        assert len(results) == 1

    def test_context_is_populated(self):
        doc = self._make_doc({8: [FakeRect()]})
        results = sniper.find_room_on_pages(doc, "A-204")
        assert results[0]["context"]  # non-empty string

    def test_description_from_plan(self):
        doc = self._make_doc({8: [FakeRect()]})
        results = sniper.find_room_on_pages(doc, "A-204")
        assert results[0]["description"] == sniper.PLAN_DESCRIPTIONS["A-150"]


# ---------------------------------------------------------------------------
# generate_crop tests
# ---------------------------------------------------------------------------

class TestGenerateCrop:
    def test_generates_png(self, tmp_path):
        doc = FakeDoc([FakePage()])
        rect = FakeRect(100, 200, 150, 230)
        output = sniper.generate_crop(
            doc, 0, rect, "A-204", "A-150",
            padding=50, zoom=2.0, output_dir=str(tmp_path)
        )
        assert output.endswith(".png")
        assert "sniper_A-204_A-150" in output

    def test_output_dir_created(self, tmp_path):
        nested = tmp_path / "sub" / "dir"
        doc = FakeDoc([FakePage()])
        rect = FakeRect(100, 200, 150, 230)
        sniper.generate_crop(
            doc, 0, rect, "A-204", "A-150",
            output_dir=str(nested)
        )
        assert nested.exists()


# ---------------------------------------------------------------------------
# sniper() integration tests (with mocked fitz.open)
# ---------------------------------------------------------------------------

class TestSniper:
    def _mock_fitz_open(self, hits_on_pages=None):
        """Return a mock for fitz.open that yields a FakeDoc."""
        hits_on_pages = hits_on_pages or {}
        pages = []
        for i in range(35):
            rects = hits_on_pages.get(i, [])
            pages.append(FakePage(search_results=rects))
        return FakeDoc(pages)

    @patch("sniper.fitz")
    def test_room_not_found_returns_empty(self, mock_fitz, tmp_path):
        mock_fitz.open.return_value = self._mock_fitz_open({})
        mock_fitz.Rect = lambda *a: FakeRect(*a)
        mock_fitz.Matrix = MagicMock()
        results = sniper.sniper("A-999", pdf_path="fake.pdf", output_dir=str(tmp_path))
        assert results == []

    @patch("sniper.fitz")
    def test_default_prefers_construction_plan(self, mock_fitz, tmp_path):
        mock_fitz.open.return_value = self._mock_fitz_open({
            3: [FakeRect()],   # A-100 (demolition)
            8: [FakeRect()],   # A-150 (construction)
            29: [FakeRect()],  # A-900 (finishes)
        })
        mock_fitz.Rect = lambda *a: FakeRect(*a)
        mock_fitz.Matrix = MagicMock()

        results = sniper.sniper("A-204", pdf_path="fake.pdf", output_dir=str(tmp_path))
        assert len(results) == 1
        assert results[0]["plan_id"] == "A-150"

    @patch("sniper.fitz")
    def test_all_plans_returns_all(self, mock_fitz, tmp_path):
        mock_fitz.open.return_value = self._mock_fitz_open({
            3: [FakeRect()],
            8: [FakeRect()],
            29: [FakeRect()],
        })
        mock_fitz.Rect = lambda *a: FakeRect(*a)
        mock_fitz.Matrix = MagicMock()

        results = sniper.sniper("A-204", all_plans=True, pdf_path="fake.pdf",
                                output_dir=str(tmp_path))
        assert len(results) == 3

    @patch("sniper.fitz")
    def test_plan_filter(self, mock_fitz, tmp_path):
        mock_fitz.open.return_value = self._mock_fitz_open({
            3: [FakeRect()],
            8: [FakeRect()],
            29: [FakeRect()],
        })
        mock_fitz.Rect = lambda *a: FakeRect(*a)
        mock_fitz.Matrix = MagicMock()

        results = sniper.sniper("A-204", plan_filter="A-900",
                                pdf_path="fake.pdf", output_dir=str(tmp_path))
        assert len(results) == 1
        assert results[0]["plan_id"] == "A-900"

    @patch("sniper.fitz")
    def test_plan_filter_nonexistent(self, mock_fitz, tmp_path):
        mock_fitz.open.return_value = self._mock_fitz_open({8: [FakeRect()]})
        mock_fitz.Rect = lambda *a: FakeRect(*a)
        mock_fitz.Matrix = MagicMock()

        results = sniper.sniper("A-204", plan_filter="A-999",
                                pdf_path="fake.pdf", output_dir=str(tmp_path))
        assert results == []

    @patch("sniper.fitz")
    def test_list_only_no_crops(self, mock_fitz, tmp_path):
        mock_fitz.open.return_value = self._mock_fitz_open({8: [FakeRect()]})
        mock_fitz.Rect = lambda *a: FakeRect(*a)
        mock_fitz.Matrix = MagicMock()

        results = sniper.sniper("A-204", list_only=True,
                                pdf_path="fake.pdf", output_dir=str(tmp_path))
        assert len(results) == 1
        assert "output_path" not in results[0]
        assert "plan_id" in results[0]

    @patch("sniper.fitz")
    def test_deduplicates_by_page(self, mock_fitz, tmp_path):
        """Multiple hits on the same page should be deduplicated."""
        mock_fitz.open.return_value = self._mock_fitz_open({
            8: [FakeRect(100, 200, 150, 230), FakeRect(300, 400, 350, 430)],
        })
        mock_fitz.Rect = lambda *a: FakeRect(*a)
        mock_fitz.Matrix = MagicMock()

        results = sniper.sniper("A-204", all_plans=True,
                                pdf_path="fake.pdf", output_dir=str(tmp_path))
        assert len(results) == 1  # only one crop per page
