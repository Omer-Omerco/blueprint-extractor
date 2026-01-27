#!/usr/bin/env python3
"""
Devis (Specification) Parser for Quebec construction documents.

Extracts structured content from specification PDFs:
- Sections and hierarchy (by font analysis)
- CSI MasterFormat codes
- Local references (room numbers)
- Products and manufacturers

Usage:
    python parse_devis.py input.pdf [-o output.json] [--pages 1-10]
"""

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from collections import Counter

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF required. Install with: pip install PyMuPDF")
    sys.exit(1)

from extract_sections import (
    TextBlock, SectionExtractor, FontStats,
    extract_local_references
)
from extract_products import ProductExtractor


@dataclass
class DocumentStats:
    """Document-level statistics for pattern analysis."""
    total_pages: int = 0
    total_blocks: int = 0
    fonts: Counter = field(default_factory=Counter)
    font_sizes: Counter = field(default_factory=Counter)
    dominant_font: Optional[tuple] = None
    title_fonts: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "total_pages": self.total_pages,
            "total_blocks": self.total_blocks,
            "dominant_font": self.dominant_font,
            "title_fonts": self.title_fonts[:5],  # Top 5
            "font_count": len(self.fonts)
        }


class DevisParser:
    """
    Main parser for construction specification (devis) PDFs.
    
    Principles:
    1. OBSERVE patterns - never hardcode specific values
    2. Use font analysis to detect hierarchy
    3. CSI MasterFormat codes for section classification
    4. Extract manufacturer/product references
    """
    
    def __init__(self, pdf_path: str, page_range: Optional[tuple] = None):
        """
        Initialize the parser.
        
        Args:
            pdf_path: Path to the PDF file
            page_range: Optional (start, end) page range (1-indexed)
        """
        self.pdf_path = Path(pdf_path)
        self.page_range = page_range
        self.doc = None
        self.blocks: list[TextBlock] = []
        self.stats = DocumentStats()
        self._raw_text_pages: dict[int, str] = {}
        
    def __enter__(self):
        self.doc = fitz.open(str(self.pdf_path))
        return self
        
    def __exit__(self, *args):
        if self.doc:
            self.doc.close()
    
    def _parse_page_range(self) -> tuple[int, int]:
        """Get the effective page range to process."""
        if not self.doc:
            raise ValueError("Document not opened")
            
        total = len(self.doc)
        
        if self.page_range:
            start = max(0, self.page_range[0] - 1)  # Convert to 0-indexed
            end = min(total, self.page_range[1])
            return start, end
        
        return 0, total
    
    def _extract_blocks_from_page(self, page_num: int) -> list[TextBlock]:
        """Extract text blocks with formatting from a page."""
        page = self.doc[page_num]
        blocks = []
        
        # Get detailed text with formatting
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # Skip non-text blocks
                continue
                
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    
                    font_name = span.get("font", "unknown")
                    font_size = span.get("size", 10)
                    bbox = span.get("bbox", (0, 0, 0, 0))
                    flags = span.get("flags", 0)
                    
                    # Detect bold/italic from flags
                    is_bold = bool(flags & 2 ** 4) or "bold" in font_name.lower()
                    is_italic = bool(flags & 2 ** 1) or "italic" in font_name.lower()
                    
                    text_block = TextBlock(
                        text=text,
                        font_name=font_name,
                        font_size=font_size,
                        x0=bbox[0],
                        y0=bbox[1],
                        x1=bbox[2],
                        y1=bbox[3],
                        page_num=page_num + 1,  # 1-indexed for output
                        is_bold=is_bold,
                        is_italic=is_italic
                    )
                    blocks.append(text_block)
                    
                    # Update stats
                    self.stats.fonts[(font_name, round(font_size, 1))] += len(text)
                    self.stats.font_sizes[round(font_size, 1)] += len(text)
        
        return blocks
    
    def _analyze_font_patterns(self):
        """Analyze font usage to determine hierarchy."""
        if not self.stats.fonts:
            return
        
        # Find dominant (body) font
        self.stats.dominant_font = self.stats.fonts.most_common(1)[0][0]
        dominant_size = self.stats.dominant_font[1]
        
        # Find title fonts (larger than dominant)
        self.stats.title_fonts = [
            (font, size) for (font, size), count in self.stats.fonts.most_common(20)
            if size > dominant_size
        ]
    
    def load(self) -> 'DevisParser':
        """Load and parse the PDF document."""
        if not self.doc:
            self.doc = fitz.open(str(self.pdf_path))
        
        start, end = self._parse_page_range()
        self.stats.total_pages = end - start
        
        print(f"Processing pages {start + 1} to {end} of {len(self.doc)}...")
        
        for page_num in range(start, end):
            # Extract blocks with formatting
            page_blocks = self._extract_blocks_from_page(page_num)
            self.blocks.extend(page_blocks)
            
            # Also store raw text for reference
            page = self.doc[page_num]
            self._raw_text_pages[page_num + 1] = page.get_text()
        
        self.stats.total_blocks = len(self.blocks)
        self._analyze_font_patterns()
        
        print(f"Extracted {self.stats.total_blocks} text blocks")
        print(f"Dominant font: {self.stats.dominant_font}")
        print(f"Title fonts detected: {len(self.stats.title_fonts)}")
        
        return self
    
    def extract_sections(self) -> list[dict]:
        """Extract document sections by formatting analysis."""
        extractor = SectionExtractor(self.blocks)
        sections = extractor.extract_sections()
        return [s.to_dict() for s in sections]
    
    def extract_csi_sections(self) -> list[dict]:
        """Extract CSI MasterFormat references."""
        extractor = SectionExtractor(self.blocks)
        return extractor.extract_csi_sections()
    
    def extract_local_references(self) -> list[dict]:
        """Extract local room/space references."""
        return extract_local_references(self.blocks)
    
    def extract_products(self, csi_refs: list[dict] = None) -> list[dict]:
        """Extract product/manufacturer mentions."""
        # Build CSI context map
        csi_context = {}
        if csi_refs:
            for ref in csi_refs:
                csi_context[ref["page_num"]] = ref["code"]
        
        extractor = ProductExtractor(self.blocks, csi_context)
        products = extractor.extract_products()
        return [p.to_dict() for p in products]
    
    def get_raw_text(self) -> str:
        """Get concatenated raw text."""
        return "\n\n".join(
            f"--- Page {num} ---\n{text}"
            for num, text in sorted(self._raw_text_pages.items())
        )
    
    def parse(self) -> dict:
        """
        Full parse of the document.
        
        Returns:
            Structured JSON-serializable dictionary
        """
        self.load()
        
        # Generate document ID from content hash
        raw_text = self.get_raw_text()
        doc_hash = hashlib.sha256(raw_text.encode()).hexdigest()[:12]
        
        # Extract all components
        csi_sections = self.extract_csi_sections()
        
        result = {
            "document_id": f"devis-{doc_hash}",
            "source_filename": self.pdf_path.name,
            "stats": self.stats.to_dict(),
            "sections": self.extract_sections(),
            "csi_sections": csi_sections,
            "local_references": self.extract_local_references(),
            "products": self.extract_products(csi_sections),
            "raw_text": raw_text[:50000] if len(raw_text) > 50000 else raw_text  # Limit size
        }
        
        return result


def parse_page_range(range_str: str) -> tuple[int, int]:
    """Parse page range string like '1-10' or '5'."""
    if '-' in range_str:
        parts = range_str.split('-')
        return int(parts[0]), int(parts[1])
    else:
        page = int(range_str)
        return page, page


def main():
    parser = argparse.ArgumentParser(
        description="Parse construction specification (devis) PDFs"
    )
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("-o", "--output", help="Output JSON file path")
    parser.add_argument("-p", "--pages", help="Page range (e.g., 1-10)")
    parser.add_argument("--raw-text-only", action="store_true",
                       help="Output only raw text (for debugging)")
    parser.add_argument("--stats-only", action="store_true",
                       help="Output only document statistics")
    
    args = parser.parse_args()
    
    # Parse page range if provided
    page_range = None
    if args.pages:
        page_range = parse_page_range(args.pages)
    
    # Process document
    with DevisParser(args.pdf_path, page_range) as parser_obj:
        if args.raw_text_only:
            parser_obj.load()
            print(parser_obj.get_raw_text())
            return
        
        if args.stats_only:
            parser_obj.load()
            print(json.dumps(parser_obj.stats.to_dict(), indent=2, ensure_ascii=False))
            return
        
        result = parser_obj.parse()
    
    # Output
    output_json = json.dumps(result, indent=2, ensure_ascii=False)
    
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output_json, encoding='utf-8')
        print(f"\nWritten to {output_path}")
        print(f"  - Sections: {len(result['sections'])}")
        print(f"  - CSI codes: {len(result['csi_sections'])}")
        print(f"  - Local refs: {len(result['local_references'])}")
        print(f"  - Products: {len(result['products'])}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
