#!/usr/bin/env python3
"""
Devis (Specification) Parser for Quebec construction documents.

IMPROVED VERSION - Full RAG support:
- Extracts COMPLETE text content per CSI section
- Captures all products with multiple formats (pipe, "de/of")
- Creates chunks ready for semantic search
- Indexes by local (room) references

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
from collections import Counter, defaultdict

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


# CSI MasterFormat pattern - STRICT: only at start of line or after title
CSI_SECTION_HEADER_PATTERN = re.compile(
    r'^(?:Section\s+)?(\d{2})\s+(\d{2})\s+(\d{2})\s*$',
    re.MULTILINE | re.IGNORECASE
)

# Pattern for section title (ALL CAPS, standalone line)
SECTION_TITLE_PATTERN = re.compile(
    r'^([A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ][A-ZÀÂÄÉÈÊËÏÎÔÙÛÜÇ\s\-\'\,\.]{10,})$',
    re.MULTILINE
)

# Room/local patterns for indexing
LOCAL_PATTERNS = [
    re.compile(r'\blocal\s*(\d{3}[A-Z]?)\b', re.IGNORECASE),
    re.compile(r'\b([A-Z]-?\d{3}[A-Z]?)\b'),
    re.compile(r'\bpièce\s*(\d{3}[A-Z]?)\b', re.IGNORECASE),
    re.compile(r'\bclasse\s*(\d{3}[A-Z]?)\b', re.IGNORECASE),
    re.compile(r'\bgymnase\b', re.IGNORECASE),
    re.compile(r'\bsalle\s+(\d{3}[A-Z]?|\w+)\b', re.IGNORECASE),
]

# Known manufacturers for product detection
KNOWN_MANUFACTURERS = {
    # Paint
    'sherwin-williams', 'sherwin williams', 'benjamin moore', 'dulux', 'sico', 'behr', 'ppg',
    'pratt & lambert', 'rust-oleum', 'rust oleum', 'cloverdale', 'para',
    # Flooring & Tile
    'mapei', 'schluter', 'laticrete', 'custom', 'armstrong', 'tarkett', 'forbo',
    'johnsonite', 'nora', 'altro', 'mannington', 'interface', 'mohawk',
    # Drywall & Ceiling
    'usg', 'certainteed', 'cgc', 'armstrong', 'rockfon', 'owens corning',
    # Insulation
    'johns manville', 'rockwool', 'roxul', 'dow', 'owens corning',
    # Waterproofing & Sealants
    'basf', 'sika', 'tremco', 'henry', 'w.r. meadows', 'cetco', 'grace',
    # Roofing
    'carlisle', 'firestone', 'soprema', 'iko', 'gaf',
    # Doors & Windows
    'jeld-wen', 'masonite', 'therma-tru', 'andersen', 'pella', 'marvin',
    # Hardware
    'assa abloy', 'stanley', 'hager', 'von duprin', 'lcn', 'dorma', 'allegion',
    # Masonry & Concrete
    'daubois', 'mortar net', 'viance', 'polyprep', 'blok-lok',
    # Mechanical/HVAC
    'trane', 'carrier', 'lennox', 'daikin', 'mitsubishi', 'fujitsu',
    # Plumbing
    'kohler', 'american standard', 'moen', 'delta', 'grohe', 'sloan',
    # Electrical
    'leviton', 'hubbell', 'eaton', 'schneider', 'siemens', 'abb',
    # Quebec specific
    'densglass', 'gyproc', 'fiberock'
}


@dataclass
class CSISection:
    """A complete CSI section with full text content."""
    code: str
    division: str
    title: str
    start_page: int
    end_page: int
    full_text: str
    products: list = field(default_factory=list)
    locals_mentioned: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "division": self.division,
            "title": self.title,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "full_text": self.full_text,
            "text_length": len(self.full_text),
            "products": self.products,
            "locals_mentioned": self.locals_mentioned
        }


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
            "title_fonts": self.title_fonts[:5],
            "font_count": len(self.fonts)
        }


class DevisParser:
    """
    Main parser for construction specification (devis) PDFs.
    IMPROVED: Better section boundary detection and product extraction.
    """
    
    def __init__(self, pdf_path: str, page_range: Optional[tuple] = None):
        self.pdf_path = Path(pdf_path)
        self.page_range = page_range
        self.doc = None
        self.blocks: list[TextBlock] = []
        self.stats = DocumentStats()
        self._raw_text_pages: dict[int, str] = {}
        self._page_texts: dict[int, str] = {}
        
    def __enter__(self):
        self.doc = fitz.open(str(self.pdf_path))
        return self
        
    def __exit__(self, *args):
        if self.doc:
            self.doc.close()
    
    def _parse_page_range(self) -> tuple[int, int]:
        if not self.doc:
            raise ValueError("Document not opened")
        total = len(self.doc)
        if self.page_range:
            start = max(0, self.page_range[0] - 1)
            end = min(total, self.page_range[1])
            return start, end
        return 0, total
    
    def _clean_page_text(self, text: str) -> str:
        """Remove headers/footers from page text."""
        lines = text.split('\n')
        if len(lines) > 6:
            # Skip header lines and page number
            cleaned = []
            for i, line in enumerate(lines):
                # Skip common header patterns
                if 'Centre de services scolaire' in line:
                    continue
                if 'Réhabilitation de l\'école' in line:
                    continue
                if 'CSSST' in line and 'FLA' in line:
                    continue
                if re.match(r'^Page \d+ / \d+', line.strip()):
                    continue
                cleaned.append(line)
            return '\n'.join(cleaned)
        return text
    
    def _extract_blocks_from_page(self, page_num: int) -> list[TextBlock]:
        page = self.doc[page_num]
        blocks = []
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
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
                        page_num=page_num + 1,
                        is_bold=is_bold,
                        is_italic=is_italic
                    )
                    blocks.append(text_block)
                    self.stats.fonts[(font_name, round(font_size, 1))] += len(text)
                    self.stats.font_sizes[round(font_size, 1)] += len(text)
        return blocks
    
    def _analyze_font_patterns(self):
        if not self.stats.fonts:
            return
        self.stats.dominant_font = self.stats.fonts.most_common(1)[0][0]
        dominant_size = self.stats.dominant_font[1]
        self.stats.title_fonts = [
            (font, size) for (font, size), count in self.stats.fonts.most_common(20)
            if size > dominant_size
        ]
    
    def load(self) -> 'DevisParser':
        if not self.doc:
            self.doc = fitz.open(str(self.pdf_path))
        
        start, end = self._parse_page_range()
        self.stats.total_pages = end - start
        
        print(f"Processing pages {start + 1} to {end} of {len(self.doc)}...")
        
        for page_num in range(start, end):
            page_blocks = self._extract_blocks_from_page(page_num)
            self.blocks.extend(page_blocks)
            
            page = self.doc[page_num]
            raw_text = page.get_text()
            self._raw_text_pages[page_num + 1] = raw_text
            self._page_texts[page_num + 1] = self._clean_page_text(raw_text)
        
        self.stats.total_blocks = len(self.blocks)
        self._analyze_font_patterns()
        
        print(f"Extracted {self.stats.total_blocks} text blocks")
        print(f"Dominant font: {self.stats.dominant_font}")
        
        return self
    
    def _find_csi_section_boundaries(self) -> list[tuple[str, str, int]]:
        """
        Find CSI section starts by looking for proper headers.
        Returns: [(code, title, page_num), ...]
        """
        sections = []
        seen_codes = set()
        
        for page_num, text in sorted(self._page_texts.items()):
            lines = text.split('\n')
            
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                
                # Look for "Section XX XX XX" on its own line
                match = re.match(r'^Section\s+(\d{2})\s+(\d{2})\s+(\d{2})\s*$', 
                                line_stripped, re.IGNORECASE)
                if match:
                    code = f"{match.group(1)} {match.group(2)} {match.group(3)}"
                    
                    # Skip if we already have this section (avoid cross-references)
                    if code in seen_codes:
                        continue
                    
                    # Find title (usually 1-3 lines before)
                    title = ""
                    for j in range(max(0, i-3), i):
                        potential_title = lines[j].strip()
                        # Title is ALL CAPS and reasonably long
                        if (potential_title.isupper() and 
                            len(potential_title) > 8 and 
                            not potential_title.startswith('Page') and
                            not 'CSSST' in potential_title and
                            not 'Centre de services' in potential_title):
                            title = potential_title
                            break
                    
                    # Only add if this looks like a real section start
                    # (first occurrence of this code)
                    sections.append((code, title, page_num))
                    seen_codes.add(code)
        
        return sections
    
    def _extract_locals_from_text(self, text: str) -> list[str]:
        """Extract room/local references from text."""
        locals_found = set()
        
        for pattern in LOCAL_PATTERNS:
            for match in pattern.finditer(text):
                if match.groups():
                    local_ref = match.group(1).upper()
                else:
                    local_ref = match.group(0).upper()
                
                # Filter out codes/years
                if not re.match(r'^\d{4,}$', local_ref):
                    if not re.match(r'^(CSA|ASTM|CAN|ISO)', local_ref):
                        locals_found.add(local_ref)
        
        return sorted(locals_found)
    
    def _extract_products_from_text(self, text: str) -> list[dict]:
        """
        Extract products using multiple formats:
        1. Quebec pipe format: "Manufacturer | Product"
        2. French format: "Product de Manufacturer" 
        3. Explicit labels: "Fabricant:", "Produit:", "Manufacturer:"
        4. Known manufacturers mentions
        """
        products = []
        seen = set()
        
        # Normalize text: collapse newlines in product names, clean list markers
        # This handles cases like "Série\nB53 de Sherwin-Williams"
        normalized_text = re.sub(r'(\w)\s*\n\s*(\w)', r'\1 \2', text)
        # Remove list markers at start: ".1", "1.", etc.
        normalized_text = re.sub(r'^\s*\.?\d+\s*', '', normalized_text, flags=re.MULTILINE)
        
        skip_words = {
            'ou', 'et', 'le', 'la', 'les', 'de', 'du', 'des',
            'avant', 'après', 'selon', 'avec', 'sans', 'pour',
            'équivalent', 'equivalent', 'approuvé', 'approved',
            'produit', 'référence', 'reference', 'section',
            'voir', 'note', 'page', 'partie', 'article',
            'minimum', 'maximum', 'couche', 'couches', 'fini'
        }
        
        def clean_product_name(name: str) -> str:
            """Clean product name from leading numbers/markers."""
            name = re.sub(r'^[\s\.0-9]+', '', name).strip()
            name = re.sub(r'\s+', ' ', name)
            return name.rstrip('.,;:')
        
        def is_valid_product(manufacturer: str, model: str) -> bool:
            """Validate product entry."""
            if len(manufacturer) < 2 or len(manufacturer) > 50:
                return False
            if len(model) < 2 or len(model) > 60:
                return False
            if manufacturer.lower() in skip_words:
                return False
            if model.lower() in skip_words:
                return False
            # Skip if looks like a sentence fragment
            if any(w in manufacturer.lower() for w in ['avant', 'après', 'selon', 'des ', 'les ', 'une ', 'deux ']):
                return False
            # Skip if model contains section references
            if re.search(r'section\s+\d{2}\s+\d{2}\s+\d{2}', model, re.IGNORECASE):
                return False
            # Skip if model is ALL CAPS header (likely a section title)
            if model.isupper() and len(model) > 15:
                return False
            return True
        
        # 1. Quebec pipe format: "Manufacturer | Product"
        # Must have at least 3 chars on each side
        pipe_pattern = re.compile(
            r'([A-Z][A-Za-z\.\-]+(?:\s+[A-Za-z&\.\-]+)*?)\s*\|\s*([A-Za-z0-9][A-Za-z0-9\s\-\.]{2,})',
            re.MULTILINE
        )
        
        for match in pipe_pattern.finditer(normalized_text):
            manufacturer = match.group(1).strip().rstrip('.,;:')
            model = clean_product_name(match.group(2))
            
            # Skip common false positives
            if manufacturer.lower() in {'pvc', 'abs', 'hdpe', 'type', 'série', 'serie', 'class'}:
                continue
            # Manufacturer must be known or look like a company name
            mfr_lower = manufacturer.lower()
            is_known = any(known in mfr_lower for known in KNOWN_MANUFACTURERS)
            looks_like_company = len(manufacturer) > 4 and manufacturer[0].isupper()
            
            if (is_known or looks_like_company) and is_valid_product(manufacturer, model):
                key = (manufacturer.lower(), model.lower())
                if key not in seen:
                    seen.add(key)
                    products.append({
                        "manufacturer": manufacturer,
                        "model": model,
                        "format": "pipe"
                    })
        
        # 2. French format: "Product de Manufacturer" 
        # Improved pattern that handles multi-word product names
        de_pattern = re.compile(
            r'([A-Z][A-Za-z0-9\-\s]{2,50}?)\s+(?:de|of)\s+([A-Z][A-Za-z\-\s]+?)(?:[,\.\)]|$|\s*\n)',
            re.MULTILINE
        )
        
        for match in de_pattern.finditer(normalized_text):
            product_name = clean_product_name(match.group(1))
            manufacturer = match.group(2).strip().rstrip('.,;:)')
            
            # Check if manufacturer is known
            mfr_lower = manufacturer.lower()
            if any(known in mfr_lower for known in KNOWN_MANUFACTURERS):
                if is_valid_product(manufacturer, product_name):
                    key = (manufacturer.lower(), product_name.lower())
                    if key not in seen:
                        seen.add(key)
                        products.append({
                            "manufacturer": manufacturer,
                            "model": product_name,
                            "format": "de/of"
                        })
        
        # 3. Explicit label patterns: "Fabricant:", "Produit:", etc.
        # More restrictive - look for clear Fabricant/Produit pairs within 200 chars
        fabricant_product_pattern = re.compile(
            r'(?:Fabricant|Manufacturer)\s*[:\-]\s*([A-Z][A-Za-z\-\s\.]{3,40}?)[\n,;].{0,150}?'
            r'(?:Produit|Product|Modèle|Model|No\.?|Numéro)\s*[:\-]\s*([A-Za-z0-9][A-Za-z0-9\-\s\.]{3,40}?)(?:[,;\.)]|\s*\n)',
            re.IGNORECASE | re.DOTALL
        )
        
        for match in fabricant_product_pattern.finditer(normalized_text):
            manufacturer = match.group(1).strip().rstrip('.,;:')
            model = clean_product_name(match.group(2))
            
            # Validate: manufacturer should look like a company name
            if len(manufacturer) < 3 or manufacturer.lower() in skip_words:
                continue
            # Model should not be a generic word
            if model.lower() in skip_words or len(model) < 3:
                continue
            
            if is_valid_product(manufacturer, model):
                key = (manufacturer.lower(), model.lower())
                if key not in seen:
                    seen.add(key)
                    products.append({
                        "manufacturer": manufacturer,
                        "model": model,
                        "format": "labeled"
                    })
        
        # 4. Known manufacturer mentions: "Sherwin-Williams: ProMar 200"
        # Skip patterns that start with "ou", "or", "et", "and" - these are alternatives
        for mfr in KNOWN_MANUFACTURERS:
            mfr_pattern = re.compile(
                rf'(?<!ou\s)(?<!or\s)(?<!et\s)\b({re.escape(mfr)})\b[\s:]+([A-Z][A-Za-z0-9\-\s]{{3,50}}?)(?:[,\.]|\s+(?:ou|or|et|and)\s|\s*\n)',
                re.IGNORECASE
            )
            for match in mfr_pattern.finditer(normalized_text):
                manufacturer = match.group(1).strip()
                product = clean_product_name(match.group(2))
                
                # Skip if product starts with conjunction or is another manufacturer
                if product.lower().startswith(('ou ', 'or ', 'et ', 'and ', 'de ')):
                    continue
                # Skip if product looks like another manufacturer name  
                if any(mfr_name in product.lower() for mfr_name in ['benjamin moore', 'sherwin', 'rust-oleum']):
                    continue
                
                if is_valid_product(manufacturer, product):
                    key = (manufacturer.lower(), product.lower())
                    if key not in seen:
                        seen.add(key)
                        products.append({
                            "manufacturer": manufacturer.title(),
                            "model": product,
                            "format": "known_mfr"
                        })
        
        # 5. Pattern "telle que X de Y" (common in Quebec specs)
        telle_que_pattern = re.compile(
            r'(?:telle?\s+que|tel\s+que|comme|such\s+as)\s+([A-Za-z0-9][A-Za-z0-9\-\s]{3,50}?)\s+de\s+([A-Z][A-Za-z\-\s]+?)(?:[,\.]|$)',
            re.IGNORECASE
        )
        
        for match in telle_que_pattern.finditer(normalized_text):
            product = clean_product_name(match.group(1))
            manufacturer = match.group(2).strip().rstrip('.,;:')
            
            mfr_lower = manufacturer.lower()
            if any(known in mfr_lower for known in KNOWN_MANUFACTURERS):
                if is_valid_product(manufacturer, product):
                    key = (manufacturer.lower(), product.lower())
                    if key not in seen:
                        seen.add(key)
                        products.append({
                            "manufacturer": manufacturer,
                            "model": product,
                            "format": "telle_que"
                        })
        
        return products
    
    def extract_csi_sections_full(self) -> list[CSISection]:
        """
        Extract CSI sections with FULL TEXT CONTENT.
        Key improvement for RAG quality.
        """
        boundaries = self._find_csi_section_boundaries()
        
        if not boundaries:
            print("Warning: No CSI sections found")
            return []
        
        # Sort by page number
        boundaries.sort(key=lambda x: x[2])
        
        print(f"Found {len(boundaries)} unique CSI sections")
        
        sections = []
        
        for i, (code, title, start_page) in enumerate(boundaries):
            # End page is either next section start or document end
            if i + 1 < len(boundaries):
                end_page = boundaries[i + 1][2]
            else:
                end_page = max(self._page_texts.keys())
            
            # Collect text from start to end page
            full_text_parts = []
            for page_num in range(start_page, end_page + 1):
                if page_num in self._page_texts:
                    page_text = self._page_texts[page_num]
                    
                    # If this is the end page and next section starts here, cut before it
                    if page_num == end_page and i + 1 < len(boundaries):
                        next_code = boundaries[i + 1][0]
                        next_pattern = rf'Section\s+{next_code.replace(" ", r"\s*")}'
                        next_match = re.search(next_pattern, page_text, re.IGNORECASE)
                        if next_match:
                            page_text = page_text[:next_match.start()]
                    
                    full_text_parts.append(page_text)
            
            full_text = '\n'.join(full_text_parts)
            
            # Extract products and locals
            products = self._extract_products_from_text(full_text)
            locals_mentioned = self._extract_locals_from_text(full_text)
            
            section = CSISection(
                code=code,
                division=code.split()[0],
                title=title,
                start_page=start_page,
                end_page=end_page,
                full_text=full_text,
                products=products,
                locals_mentioned=locals_mentioned
            )
            sections.append(section)
        
        return sections
    
    def extract_sections(self) -> list[dict]:
        extractor = SectionExtractor(self.blocks)
        sections = extractor.extract_sections()
        return [s.to_dict() for s in sections]
    
    def extract_csi_sections(self) -> list[dict]:
        extractor = SectionExtractor(self.blocks)
        return extractor.extract_csi_sections()
    
    def extract_local_references(self) -> list[dict]:
        return extract_local_references(self.blocks)
    
    def extract_products(self, csi_refs: list[dict] = None) -> list[dict]:
        csi_context = {}
        if csi_refs:
            for ref in csi_refs:
                csi_context[ref["page_num"]] = ref["code"]
        
        extractor = ProductExtractor(self.blocks, csi_context)
        products = extractor.extract_products()
        return [p.to_dict() for p in products]
    
    def get_raw_text(self) -> str:
        return "\n\n".join(
            f"--- Page {num} ---\n{text}"
            for num, text in sorted(self._raw_text_pages.items())
        )
    
    def parse(self) -> dict:
        """Full parse of the document."""
        self.load()
        
        raw_text = self.get_raw_text()
        doc_hash = hashlib.sha256(raw_text.encode()).hexdigest()[:12]
        
        # Extract all components
        csi_sections_full = self.extract_csi_sections_full()
        csi_sections_legacy = self.extract_csi_sections()
        
        # Collect all products from full sections
        all_products = []
        for section in csi_sections_full:
            for product in section.products:
                product_entry = {
                    "manufacturer": product.get("manufacturer", ""),
                    "model": product.get("model", ""),
                    "csi_section": section.code,
                    "csi_title": section.title,
                    "format": product.get("format", "unknown")
                }
                all_products.append(product_entry)
        
        result = {
            "document_id": f"devis-{doc_hash}",
            "source_filename": self.pdf_path.name,
            "stats": self.stats.to_dict(),
            "sections": self.extract_sections(),
            
            # Full CSI sections with complete text
            "csi_sections_full": [s.to_dict() for s in csi_sections_full],
            
            # Legacy format
            "csi_sections": csi_sections_legacy,
            "local_references": self.extract_local_references(),
            
            # Products from both sources
            "products": all_products,
            
            # Local index
            "local_index": self._build_local_index(csi_sections_full),
            
            # Raw text (truncated)
            "raw_text": raw_text[:50000] if len(raw_text) > 50000 else raw_text
        }
        
        return result
    
    def _build_local_index(self, csi_sections: list[CSISection]) -> dict:
        """Build index: local/room -> list of CSI sections that mention it."""
        index = defaultdict(list)
        
        for section in csi_sections:
            for local_ref in section.locals_mentioned:
                index[local_ref].append({
                    "csi_code": section.code,
                    "csi_title": section.title,
                    "pages": f"{section.start_page}-{section.end_page}"
                })
        
        return dict(index)


def parse_page_range(range_str: str) -> tuple[int, int]:
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
                       help="Output only raw text")
    parser.add_argument("--stats-only", action="store_true",
                       help="Output only document statistics")
    
    args = parser.parse_args()
    
    page_range = None
    if args.pages:
        page_range = parse_page_range(args.pages)
    
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
    
    output_json = json.dumps(result, indent=2, ensure_ascii=False)
    
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output_json, encoding='utf-8')
        print(f"\nWritten to {output_path}")
        print(f"  - CSI sections (full): {len(result['csi_sections_full'])}")
        print(f"  - Products: {len(result['products'])}")
        print(f"  - Locals indexed: {len(result['local_index'])}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
