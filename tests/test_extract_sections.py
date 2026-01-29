#!/usr/bin/env python3
"""
Tests for extract_sections.py — CSI section extraction from devis.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from extract_sections import (
    FontStats,
    TextBlock,
    Section,
    CSISectionFull,
    SectionExtractor,
    extract_local_references,
)


# ============== Fixtures ==============

@pytest.fixture
def sample_blocks():
    """Sample text blocks mimicking a construction devis."""
    return [
        # Page 1: Title
        TextBlock(
            text="SECTION 09 91 00",
            font_name="Helvetica-Bold",
            font_size=14.0,
            x0=50, y0=50, x1=300, y1=70,
            page_num=1,
            is_bold=True,
        ),
        TextBlock(
            text="PEINTURE INTÉRIEURE",
            font_name="Helvetica-Bold",
            font_size=14.0,
            x0=50, y0=75, x1=300, y1=95,
            page_num=1,
            is_bold=True,
        ),
        # Body text
        TextBlock(
            text="Appliquer peinture latex sur tous les murs des classes.",
            font_name="Helvetica",
            font_size=10.0,
            x0=50, y0=120, x1=500, y1=135,
            page_num=1,
        ),
        TextBlock(
            text="Local A-101: finition standard",
            font_name="Helvetica",
            font_size=10.0,
            x0=50, y0=140, x1=400, y1=155,
            page_num=1,
        ),
        # Subsection
        TextBlock(
            text="PARTIE 2 - PRODUITS",
            font_name="Helvetica-Bold",
            font_size=12.0,
            x0=50, y0=200, x1=300, y1=215,
            page_num=1,
            is_bold=True,
        ),
        TextBlock(
            text="ProMar 200 ou équivalent approuvé.",
            font_name="Helvetica",
            font_size=10.0,
            x0=50, y0=230, x1=400, y1=245,
            page_num=1,
        ),
        # Page 2: Another section
        TextBlock(
            text="SECTION 09 65 00",
            font_name="Helvetica-Bold",
            font_size=14.0,
            x0=50, y0=50, x1=300, y1=70,
            page_num=2,
            is_bold=True,
        ),
        TextBlock(
            text="REVÊTEMENTS DE SOL RÉSILIENTS",
            font_name="Helvetica-Bold",
            font_size=14.0,
            x0=50, y0=75, x1=400, y1=95,
            page_num=2,
            is_bold=True,
        ),
        TextBlock(
            text="VCT Armstrong pour corridors et classes.",
            font_name="Helvetica",
            font_size=10.0,
            x0=50, y0=120, x1=500, y1=135,
            page_num=2,
        ),
    ]


@pytest.fixture
def body_blocks():
    """Blocks with only body text (no titles)."""
    return [
        TextBlock(
            text="Regular body text line 1.",
            font_name="Helvetica",
            font_size=10.0,
            x0=50, y0=100, x1=400, y1=115,
            page_num=1,
        ),
        TextBlock(
            text="Regular body text line 2.",
            font_name="Helvetica",
            font_size=10.0,
            x0=50, y0=120, x1=400, y1=135,
            page_num=1,
        ),
    ]


@pytest.fixture
def room_reference_blocks():
    """Text blocks with room references."""
    return [
        TextBlock(
            text="Installer dans local A-101 et classe 204.",
            font_name="Helvetica",
            font_size=10.0,
            x0=50, y0=100, x1=500, y1=115,
            page_num=1,
        ),
        TextBlock(
            text="Voir plan B-205 pour détails vestiaire.",
            font_name="Helvetica",
            font_size=10.0,
            x0=50, y0=120, x1=500, y1=135,
            page_num=1,
        ),
        TextBlock(
            text="Conforme norme CSA-A371 et ASTM C979.",
            font_name="Helvetica",
            font_size=10.0,
            x0=50, y0=140, x1=500, y1=155,
            page_num=2,
        ),
    ]


# ============== FontStats ==============

class TestFontStats:
    def test_empty(self):
        fs = FontStats()
        assert fs.dominant_font is None
        assert fs.title_fonts == []

    def test_dominant_font(self):
        from collections import Counter
        fs = FontStats()
        fs.fonts = Counter({("Helvetica", 10.0): 5000, ("Helvetica-Bold", 14.0): 200})
        fs.sizes = Counter({10.0: 5000, 14.0: 200})
        assert fs.dominant_font == ("Helvetica", 10.0)

    def test_title_fonts(self):
        from collections import Counter
        fs = FontStats()
        fs.fonts = Counter({("Helvetica", 10.0): 5000, ("Helvetica-Bold", 14.0): 200})
        fs.sizes = Counter({10.0: 5000, 14.0: 200})
        titles = fs.title_fonts
        assert len(titles) > 0
        assert ("Helvetica-Bold", 14.0) in titles


# ============== TextBlock ==============

class TestTextBlock:
    def test_font_key(self):
        block = TextBlock(
            text="Test", font_name="Helvetica", font_size=10.123,
            x0=0, y0=0, x1=100, y1=20, page_num=1,
        )
        assert block.font_key == ("Helvetica", 10.1)

    def test_attributes(self):
        block = TextBlock(
            text="Hello", font_name="Arial-Bold", font_size=12.0,
            x0=10, y0=20, x1=200, y1=35, page_num=3,
            is_bold=True, is_italic=False,
        )
        assert block.text == "Hello"
        assert block.is_bold is True
        assert block.page_num == 3


# ============== Section ==============

class TestSection:
    def test_to_dict(self):
        section = Section(
            title="PEINTURE",
            level=1,
            page_num=5,
            start_y=100.0,
            content="Apply paint to walls.",
            csi_code="09 91 00",
        )
        d = section.to_dict()
        assert d["title"] == "PEINTURE"
        assert d["level"] == 1
        assert d["csi_code"] == "09 91 00"
        assert "subsections" in d

    def test_content_truncated(self):
        long_content = "x" * 1000
        section = Section(title="T", level=1, page_num=1, start_y=0, content=long_content)
        d = section.to_dict()
        assert len(d["content"]) <= 500

    def test_subsections(self):
        sub = Section(title="SUB", level=2, page_num=1, start_y=50)
        main = Section(title="MAIN", level=1, page_num=1, start_y=10, subsections=[sub])
        d = main.to_dict()
        assert len(d["subsections"]) == 1
        assert d["subsections"][0]["title"] == "SUB"


# ============== CSISectionFull ==============

class TestCSISectionFull:
    def test_to_dict(self):
        s = CSISectionFull(
            code="09 91 00",
            division="09",
            title="PEINTURE",
            start_page=10,
            end_page=15,
            full_text="Full text content here.",
            products=["ProMar 200"],
            locals_mentioned=["A-101"],
        )
        d = s.to_dict()
        assert d["code"] == "09 91 00"
        assert d["text_length"] == len("Full text content here.")
        assert "products" in d
        assert "locals_mentioned" in d


# ============== SectionExtractor ==============

class TestSectionExtractor:
    def test_extract_sections(self, sample_blocks):
        extractor = SectionExtractor(sample_blocks)
        sections = extractor.extract_sections()
        assert len(sections) > 0
        # Should detect title blocks
        assert any("SECTION" in s.title or "PEINTURE" in s.title for s in sections)

    def test_extract_csi_codes(self, sample_blocks):
        extractor = SectionExtractor(sample_blocks)
        csi_refs = extractor.extract_csi_sections()
        assert len(csi_refs) > 0
        codes = [r["code"] for r in csi_refs]
        assert "09 91 00" in codes
        assert "09 65 00" in codes

    def test_csi_ref_structure(self, sample_blocks):
        extractor = SectionExtractor(sample_blocks)
        csi_refs = extractor.extract_csi_sections()
        for ref in csi_refs:
            assert "code" in ref
            assert "division" in ref
            assert "page_num" in ref
            assert "is_header" in ref

    def test_title_detection(self, sample_blocks):
        extractor = SectionExtractor(sample_blocks)
        # Bold 14pt should be title
        title_block = sample_blocks[0]
        assert extractor._is_title_block(title_block)

    def test_body_not_title(self, sample_blocks):
        extractor = SectionExtractor(sample_blocks)
        body_block = sample_blocks[2]  # Regular body text
        assert not extractor._is_title_block(body_block)

    def test_title_level(self, sample_blocks):
        extractor = SectionExtractor(sample_blocks)
        # Large font → level 1
        level = extractor._detect_title_level(sample_blocks[0])
        assert level in [1, 2]

    def test_extract_csi_code(self, sample_blocks):
        extractor = SectionExtractor(sample_blocks)
        assert extractor._extract_csi_code("SECTION 09 91 00") == "09 91 00"
        assert extractor._extract_csi_code("No code here") is None

    def test_body_only_blocks(self, body_blocks):
        extractor = SectionExtractor(body_blocks)
        sections = extractor.extract_sections()
        # Might not have sections if no titles detected
        assert isinstance(sections, list)

    def test_empty_blocks(self):
        extractor = SectionExtractor([])
        sections = extractor.extract_sections()
        assert sections == []

    def test_dedup_csi(self, sample_blocks):
        """CSI sections should be deduplicated."""
        # Add duplicate CSI block
        dup_block = TextBlock(
            text="Référence SECTION 09 91 00",
            font_name="Helvetica",
            font_size=10.0,
            x0=50, y0=300, x1=400, y1=315,
            page_num=1,
        )
        extractor = SectionExtractor(sample_blocks + [dup_block])
        csi_refs = extractor.extract_csi_sections()
        codes = [r["code"] for r in csi_refs]
        # Should be deduplicated
        assert codes.count("09 91 00") == 1


# ============== extract_local_references ==============

class TestExtractLocalReferences:
    def test_finds_room_refs(self, room_reference_blocks):
        refs = extract_local_references(room_reference_blocks)
        room_ids = [r["room_ref"] for r in refs]
        assert any("A-101" in r for r in room_ids)

    def test_excludes_standards(self, room_reference_blocks):
        refs = extract_local_references(room_reference_blocks)
        room_ids = [r["room_ref"] for r in refs]
        # Should NOT include CSA-A371 or ASTM C979
        assert not any("CSA" in r for r in room_ids)
        assert not any("C979" in r for r in room_ids)

    def test_deduplication(self):
        blocks = [
            TextBlock(
                text="Local A-101 peinture. Aussi A-101 finition.",
                font_name="Helvetica", font_size=10.0,
                x0=0, y0=0, x1=400, y1=15, page_num=1,
            )
        ]
        refs = extract_local_references(blocks)
        ids = [r["room_ref"] for r in refs]
        # Should be deduplicated
        assert ids.count("A-101") <= 1

    def test_empty_blocks(self):
        refs = extract_local_references([])
        assert refs == []

    def test_ref_structure(self, room_reference_blocks):
        refs = extract_local_references(room_reference_blocks)
        for ref in refs:
            assert "room_ref" in ref
            assert "context" in ref
            assert "page_num" in ref
