#!/usr/bin/env python3
"""
Section extractor for construction specifications (devis).
Detects sections by analyzing font patterns and formatting changes.

IMPROVED: Full content extraction for CSI sections.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from collections import Counter


@dataclass
class FontStats:
    """Statistics about fonts in a document."""
    fonts: Counter = field(default_factory=Counter)
    sizes: Counter = field(default_factory=Counter)
    
    @property
    def dominant_font(self) -> Optional[tuple]:
        """Returns (font_name, size) for the most common text."""
        if not self.fonts:
            return None
        return self.fonts.most_common(1)[0][0]
    
    @property
    def title_fonts(self) -> list:
        """Returns fonts that are likely titles (larger than dominant)."""
        if not self.sizes:
            return []
        dominant_size = self.sizes.most_common(1)[0][0]
        return [
            (font, size) for (font, size), count in self.fonts.items()
            if size > dominant_size
        ]


@dataclass
class CSISectionFull:
    """A complete CSI section with full text content for RAG."""
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
class TextBlock:
    """A block of text with its formatting."""
    text: str
    font_name: str
    font_size: float
    x0: float
    y0: float
    x1: float
    y1: float
    page_num: int
    is_bold: bool = False
    is_italic: bool = False
    
    @property
    def font_key(self) -> tuple:
        return (self.font_name, round(self.font_size, 1))


@dataclass
class Section:
    """A detected section in the document."""
    title: str
    level: int  # 1 = main, 2 = sub, 3 = sub-sub
    page_num: int
    start_y: float
    content: str = ""
    subsections: list = field(default_factory=list)
    csi_code: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "level": self.level,
            "page_num": self.page_num,
            "csi_code": self.csi_code,
            "content": self.content[:500] if self.content else "",
            "subsections": [s.to_dict() for s in self.subsections]
        }


class SectionExtractor:
    """Extracts sections from text blocks by analyzing formatting patterns."""
    
    # CSI MasterFormat pattern: XX XX XX or XX-XX-XX
    CSI_PATTERN = re.compile(r'\b(\d{2})[\s\-]+(\d{2})[\s\-]+(\d{2})\b')
    
    # Common section title patterns (observed, not hardcoded content)
    SECTION_PATTERNS = [
        re.compile(r'^SECTION\s+\d+', re.IGNORECASE),
        re.compile(r'^PARTIE\s+\d+', re.IGNORECASE),
        re.compile(r'^ARTICLE\s+\d+', re.IGNORECASE),
        re.compile(r'^\d+\.\d+', re.IGNORECASE),
    ]
    
    def __init__(self, blocks: list[TextBlock]):
        self.blocks = blocks
        self.font_stats = self._analyze_fonts()
        self.dominant_font = self.font_stats.dominant_font
        self.title_fonts = set(self.font_stats.title_fonts)
        
    def _analyze_fonts(self) -> FontStats:
        """Analyze font usage across all blocks."""
        stats = FontStats()
        for block in self.blocks:
            stats.fonts[block.font_key] += len(block.text)
            stats.sizes[round(block.font_size, 1)] += len(block.text)
        return stats
    
    def _is_title_block(self, block: TextBlock) -> bool:
        """Determine if a block is likely a title based on formatting."""
        # Larger than dominant font
        if self.dominant_font and block.font_size > self.dominant_font[1]:
            return True
        # Bold text (often indicated in font name)
        if 'bold' in block.font_name.lower() or block.is_bold:
            return True
        # All caps text longer than a few chars
        if block.text.isupper() and len(block.text.strip()) > 3:
            return True
        return False
    
    def _detect_title_level(self, block: TextBlock) -> int:
        """Detect the hierarchical level of a title (1-3)."""
        size_diff = block.font_size - (self.dominant_font[1] if self.dominant_font else 10)
        
        if size_diff >= 4:
            return 1  # Main section
        elif size_diff >= 2:
            return 2  # Subsection
        elif 'bold' in block.font_name.lower() or block.is_bold:
            return 3  # Sub-subsection
        return 2
    
    def _extract_csi_code(self, text: str) -> Optional[str]:
        """Extract CSI MasterFormat code from text."""
        match = self.CSI_PATTERN.search(text)
        if match:
            return f"{match.group(1)} {match.group(2)} {match.group(3)}"
        return None
    
    def extract_sections(self) -> list[Section]:
        """Extract all sections from the document."""
        sections = []
        current_section = None
        content_buffer = []
        
        for block in sorted(self.blocks, key=lambda b: (b.page_num, b.y0, b.x0)):
            text = block.text.strip()
            if not text:
                continue
            
            is_title = self._is_title_block(block)
            
            if is_title:
                # Save previous section's content
                if current_section and content_buffer:
                    current_section.content = "\n".join(content_buffer)
                    content_buffer = []
                
                level = self._detect_title_level(block)
                csi_code = self._extract_csi_code(text)
                
                section = Section(
                    title=text,
                    level=level,
                    page_num=block.page_num,
                    start_y=block.y0,
                    csi_code=csi_code
                )
                
                # Handle hierarchy
                if level == 1 or not current_section:
                    sections.append(section)
                    current_section = section
                elif level == 2 and current_section:
                    current_section.subsections.append(section)
                    current_section = section
                else:
                    # Level 3 or deeper
                    if current_section:
                        current_section.subsections.append(section)
            else:
                # Regular content
                content_buffer.append(text)
        
        # Don't forget last section's content
        if current_section and content_buffer:
            current_section.content = "\n".join(content_buffer)
        
        return sections
    
    def extract_csi_sections(self) -> list[dict]:
        """Extract all CSI MasterFormat references with extended context."""
        csi_refs = []
        
        # Group blocks by page for better context extraction
        blocks_by_page = {}
        for block in self.blocks:
            if block.page_num not in blocks_by_page:
                blocks_by_page[block.page_num] = []
            blocks_by_page[block.page_num].append(block)
        
        for block in self.blocks:
            text = block.text.strip()
            for match in self.CSI_PATTERN.finditer(text):
                code = f"{match.group(1)} {match.group(2)} {match.group(3)}"
                
                # Get extended context: look for title before the code
                context_parts = []
                
                # Check blocks before this one on same page
                page_blocks = blocks_by_page.get(block.page_num, [])
                sorted_blocks = sorted(page_blocks, key=lambda b: (b.y0, b.x0))
                
                # Find this block's position
                block_idx = -1
                for i, b in enumerate(sorted_blocks):
                    if b.text == block.text and abs(b.y0 - block.y0) < 1:
                        block_idx = i
                        break
                
                # Get 3 blocks before for context (title usually above)
                if block_idx > 0:
                    for i in range(max(0, block_idx - 3), block_idx):
                        prev_text = sorted_blocks[i].text.strip()
                        if prev_text and len(prev_text) > 3:
                            context_parts.append(prev_text)
                
                context_parts.append(text)
                
                # Get 2 blocks after for more context
                for i in range(block_idx + 1, min(len(sorted_blocks), block_idx + 3)):
                    next_text = sorted_blocks[i].text.strip()
                    if next_text and len(next_text) > 3:
                        context_parts.append(next_text)
                
                extended_context = ' | '.join(context_parts)
                
                # Try to extract title (usually ALL CAPS line before Section XX XX XX)
                title = ""
                for part in context_parts[:-1]:  # Exclude the CSI code line
                    if part.isupper() and len(part) > 5 and not part.startswith('SECTION'):
                        title = part
                        break
                
                csi_refs.append({
                    "code": code,
                    "division": match.group(1),
                    "title": title,
                    "context": extended_context[:500],
                    "page_num": block.page_num,
                    "is_header": self._is_title_block(block)
                })
        
        # Deduplicate by code while keeping first occurrence with title
        seen = {}
        for ref in csi_refs:
            code = ref["code"]
            if code not in seen:
                seen[code] = ref
            elif ref.get("title") and not seen[code].get("title"):
                # Prefer entry with title
                seen[code] = ref
        
        return list(seen.values())


def extract_local_references(blocks: list[TextBlock]) -> list[dict]:
    """
    Extract local room/space references (e.g., 101, 204, CLASSE-101).
    These are typically room numbers referenced in specs.
    """
    # Pattern for room numbers with plan references
    ROOM_PATTERN = re.compile(
        r'\b(?:'
        r'(?:local|pièce|salle|classe|bureau)[\s\-]*(\d{3,})|'  # local 101
        r'([A-Z]{1,2}[\-]?\d{3}(?:[a-zA-Z])?)|'  # A-101, E-150, 101A (plan refs)
        r'(?:plan|dessin|drawing)\s+([A-Z][\-]?\d+)'  # plan A-1
        r')',
        re.IGNORECASE
    )
    
    # Standards/norms to exclude (CSA, ASTM, etc.)
    EXCLUDE_PATTERNS = re.compile(
        r'\b(?:'
        r'(?:CSA|ASTM|CAN|ISO|ANSI|NFPA|ULC)[\s\-]*[A-Z]?\d+|'  # CSA-A371
        r'[A-Z]\d{3,5}|'  # standalone codes like C979
        r'\d{4,}'  # 4+ digit numbers (years, codes)
        r')\b',
        re.IGNORECASE
    )
    
    references = []
    
    for block in blocks:
        text = block.text
        for match in ROOM_PATTERN.finditer(text):
            # Get the matched room number
            room_num = match.group(1) or match.group(2) or match.group(3)
            if not room_num:
                continue
            
            # Skip if it looks like a standard/norm reference
            if EXCLUDE_PATTERNS.match(room_num):
                continue
            
            # Get surrounding context
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 50)
            context = text[start:end].strip()
            
            # Skip if context mentions standards
            if any(std in context.upper() for std in ['CSA', 'ASTM', 'ANSI', 'ISO', 'NORME', 'NORM']):
                continue
            
            references.append({
                "room_ref": room_num,
                "context": context,
                "page_num": block.page_num
            })
    
    # Deduplicate
    seen = set()
    unique_refs = []
    for ref in references:
        key = ref["room_ref"]
        if key not in seen:
            seen.add(key)
            unique_refs.append(ref)
    
    return unique_refs
