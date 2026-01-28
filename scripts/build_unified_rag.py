#!/usr/bin/env python3
"""
Build Professional RAG Index for Construction Projects.

Creates:
1. chunks.json - Semantic search chunks (~1000 chars with overlap)
2. local_index.json - Room → CSI sections mapping (filtered for false positives)
3. type_index.json - Material type → sections mapping
4. product_index.json - Manufacturer → products mapping
5. unified_index.json - Complete searchable knowledge base

Features:
- Intelligent chunking with metadata preservation
- FALSE POSITIVE FILTERING: excludes phone numbers, dates, postal codes, plan references
- Room/local cross-referencing with real room validation
- Product extraction per section
- Type-based indexing (peinture, plancher, porte, etc.)
- Ready for embedding/vector search
"""

import argparse
import json
import re
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict


# ==============================================================================
# CSI Code to Type Mapping
# ==============================================================================

CSI_TYPE_MAPPING = {
    # Peinture et revêtements
    "09 91": "peinture",
    "09 90": "peinture",
    
    # Planchers
    "09 65": "plancher",
    "09 68": "plancher",
    "09 64": "plancher",
    "09 63": "plancher",
    "09 62": "plancher",
    
    # Portes et cadres
    "08 11": "porte",
    "08 14": "porte",
    "08 12": "porte",
    "08 71": "quincaillerie_porte",
    
    # Fenêtres
    "08 51": "fenêtre",
    "08 52": "fenêtre",
    "08 53": "fenêtre",
    "08 50": "fenêtre",
    
    # Plafonds
    "09 51": "plafond",
    "09 54": "plafond",
    
    # Murs et cloisons
    "09 21": "mur",
    "09 22": "mur",
    "09 29": "mur",
    "04 22": "maçonnerie",
    
    # Céramique
    "09 30": "céramique",
    "09 31": "céramique",
    
    # Isolation
    "07 21": "isolation",
    "07 22": "isolation",
    "07 27": "isolation",
    
    # Étanchéité
    "07 92": "étanchéité",
    "07 90": "étanchéité",
    
    # Toiture
    "07 50": "toiture",
    "07 51": "toiture",
    "07 52": "toiture",
    
    # Acier/Métaux
    "05 12": "acier",
    "05 21": "acier",
    "05 50": "métaux",
    
    # Béton
    "03 30": "béton",
    "03 31": "béton",
    
    # Électricité
    "26": "électricité",
    
    # Mécanique/Plomberie
    "22": "plomberie",
    "23": "mécanique",
    
    # Gicleurs
    "21 13": "gicleurs",
}

# Keywords for detecting material types in text
TYPE_KEYWORDS = {
    "peinture": ["peinture", "latex", "apprêt", "primer", "couche", "benjamin moore", "sherwin"],
    "plancher": ["plancher", "revêtement de sol", "VCT", "époxy", "vinyle", "linoleum", "tapis", "moquette"],
    "porte": ["porte", "cadre de porte", "dormant"],
    "fenêtre": ["fenêtre", "vitrage", "double vitrage", "châssis"],
    "plafond": ["plafond", "suspendu", "tuile acoustique", "armstrong"],
    "mur": ["gypse", "cloison", "placoplâtre", "drywall"],
    "céramique": ["céramique", "carrelage", "carreau", "tuile", "porcelaine"],
    "isolation": ["isolant", "isolation", "pare-vapeur", "polystyrène", "laine minérale"],
    "étanchéité": ["scellant", "calfeutrage", "étanchéité", "membrane"],
}


@dataclass
class Chunk:
    """A text chunk ready for embedding/search."""
    id: str
    text: str
    csi_code: Optional[str] = None
    csi_title: Optional[str] = None
    page_range: str = ""
    chunk_index: int = 0
    total_chunks: int = 1
    products_mentioned: list = field(default_factory=list)
    locals_mentioned: list = field(default_factory=list)
    types_mentioned: list = field(default_factory=list)
    source: str = "devis"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "metadata": {
                "csi_code": self.csi_code,
                "csi_title": self.csi_title,
                "page_range": self.page_range,
                "chunk_index": self.chunk_index,
                "total_chunks": self.total_chunks,
                "products": self.products_mentioned[:5],
                "locals": self.locals_mentioned,
                "types": self.types_mentioned,
                "source": self.source,
                "char_count": len(self.text)
            }
        }


class LocalValidator:
    """Validates room/local references and filters false positives."""
    
    # Known plan prefixes to exclude
    PLAN_PREFIXES = {'E', 'S', 'W', 'M', 'F', 'P', 'G'}
    
    # Phone number patterns
    PHONE_PATTERNS = [
        r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # 450-651-0515
        r'\(\d{3}\)\s?\d{3}[-.\s]?\d{4}',   # (450) 651-0515
    ]
    
    # Postal code pattern (Canadian)
    POSTAL_PATTERN = r'[A-Z]\d[A-Z]\s?\d[A-Z]\d'
    
    # Date patterns
    DATE_PATTERNS = [
        r'\d{4}[-/]\d{2}[-/]\d{2}',  # 2025-09-15
        r'\d{2}[-/]\d{2}[-/]\d{4}',  # 15/09/2025
    ]
    
    def __init__(self, valid_rooms: list[str] = None):
        """
        Initialize with optional list of known valid rooms.
        Format: ["A-101", "B-106", "C-101", ...]
        """
        self.valid_rooms = set(r.upper() for r in (valid_rooms or []))
        self._false_positive_cache = {}
    
    def add_valid_rooms(self, rooms: list[str]):
        """Add rooms from room extraction."""
        for room in rooms:
            if isinstance(room, dict):
                room_id = room.get("id", "")
            else:
                room_id = str(room)
            if room_id:
                self.valid_rooms.add(room_id.upper())
    
    def is_false_positive(self, text: str, ref: str) -> bool:
        """
        Check if a reference is a false positive.
        Returns True if it should be excluded.
        """
        ref_upper = ref.upper()
        
        # Check cache
        cache_key = (text[:100], ref)
        if cache_key in self._false_positive_cache:
            return self._false_positive_cache[cache_key]
        
        result = self._check_false_positive(text, ref, ref_upper)
        self._false_positive_cache[cache_key] = result
        return result
    
    def _check_false_positive(self, text: str, ref: str, ref_upper: str) -> bool:
        """Internal false positive check."""
        
        # 1. Plan references: E-101, S269, W117, M200, etc.
        if re.match(r'^[ESWMFPG]-?\d+$', ref_upper):
            return True
        
        # 2. Very short refs (DE, AB, etc.)
        if len(ref) <= 2:
            return True
        
        # 3. Phone number context
        context_window = 50
        ref_pos = text.upper().find(ref_upper)
        if ref_pos >= 0:
            context = text[max(0, ref_pos-context_window):ref_pos+len(ref)+context_window]
            
            # Check for phone indicators
            phone_indicators = ['téléphone', 'tel:', 'tél:', 'phone', 'fax', 'cell']
            if any(ind in context.lower() for ind in phone_indicators):
                return True
            
            # Check if ref looks like part of a phone number
            for pattern in self.PHONE_PATTERNS:
                if re.search(pattern, context):
                    # Check if ref is embedded in the phone
                    if ref in re.search(pattern, context).group():
                        return True
        
        # 4. Postal code context
        if re.search(self.POSTAL_PATTERN, text.upper()):
            # If ref could be part of postal code
            if re.match(r'^[A-Z]\d[A-Z]$|^\d[A-Z]\d$', ref_upper):
                return True
        
        # 5. Address context (local 240 is address, not room)
        address_indicators = ['adresse', 'address', 'rue', 'boulevard', 'avenue', 'paul-lussier']
        if ref_pos >= 0:
            context = text[max(0, ref_pos-100):ref_pos+len(ref)+50].lower()
            if any(ind in context for ind in address_indicators):
                return True
        
        # 6. CSI code false positive (looks like 09 91 00)
        if re.match(r'^\d{2}$', ref):
            return True
        
        # 7. Year/date
        if re.match(r'^(19|20)\d{2}$', ref):
            return True
        if re.match(r'^\d{2}-\d{2,4}$', ref):  # 23-333 (project code)
            return True
        
        return False
    
    def is_valid_local(self, ref: str, context: str = "") -> bool:
        """
        Check if reference is a valid room number.
        """
        ref_upper = ref.upper()
        
        # If we have a list of valid rooms, check against it
        if self.valid_rooms:
            # Exact match
            if ref_upper in self.valid_rooms:
                return True
            # Try with hyphen
            if f"{ref_upper[0]}-{ref_upper[1:]}" in self.valid_rooms:
                return True
        
        # Check for false positive
        if context and self.is_false_positive(context, ref):
            return False
        
        # Pattern-based validation
        # A-101, B-106, C-101 format (preferred)
        if re.match(r'^[A-D]-\d{3}$', ref_upper):
            return True
        
        # 3-digit room numbers (100-999) without block letter
        if re.match(r'^\d{3}$', ref):
            num = int(ref)
            if 100 <= num <= 999:
                # Additional context check for pure numbers
                if context:
                    # Make sure it's in a room context
                    ctx_lower = context.lower()
                    room_indicators = ['local', 'salle', 'bureau', 'classe', 'pièce', 'room']
                    if any(ind in ctx_lower for ind in room_indicators):
                        return True
                return False  # Pure numbers need context validation
        
        return False
    
    def extract_locals(self, text: str) -> list[str]:
        """
        Extract valid local references from text.
        Returns deduplicated list of valid room numbers.
        """
        candidates = set()
        
        # Pattern 1: "local A-101" or "LOCAL A-101"
        for match in re.finditer(r'\blocal\s+([A-D]-?\d{3})\b', text, re.IGNORECASE):
            ref = match.group(1).upper()
            if '-' not in ref:
                ref = f"{ref[0]}-{ref[1:]}"
            candidates.add(ref)
        
        # Pattern 2: Standalone A-101 format
        for match in re.finditer(r'\b([A-D]-\d{3})\b', text):
            candidates.add(match.group(1).upper())
        
        # Pattern 3: "locaux 101, 102, 103" - only if preceded by "local"
        for match in re.finditer(r'\blocaux?\s+([\d,\s]+(?:\d{3}))', text, re.IGNORECASE):
            numbers = re.findall(r'\d{3}', match.group(1))
            for num in numbers:
                # These need validation
                if self.is_valid_local(num, text):
                    candidates.add(num)
        
        # Validate all candidates
        valid = []
        for ref in candidates:
            if self.is_valid_local(ref, text):
                valid.append(ref)
        
        return sorted(set(valid))


class ChunkBuilder:
    """Creates optimized chunks for semantic search."""
    
    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk_text(self, text: str, base_id: str, metadata: dict = None) -> list[Chunk]:
        """Split text into overlapping chunks."""
        metadata = metadata or {}
        chunks = []
        
        text = self._clean_text(text)
        
        if len(text) <= self.chunk_size:
            chunk = Chunk(
                id=f"{base_id}_0",
                text=text,
                csi_code=metadata.get("csi_code"),
                csi_title=metadata.get("csi_title"),
                page_range=metadata.get("page_range", ""),
                chunk_index=0,
                total_chunks=1,
                products_mentioned=metadata.get("products", []),
                locals_mentioned=metadata.get("locals", []),
                types_mentioned=metadata.get("types", [])
            )
            chunks.append(chunk)
            return chunks
        
        break_points = self._find_break_points(text)
        
        start = 0
        chunk_num = 0
        
        while start < len(text):
            ideal_end = start + self.chunk_size
            
            if ideal_end >= len(text):
                end = len(text)
            else:
                end = self._find_best_break(break_points, ideal_end, start)
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                chunks.append(Chunk(
                    id=f"{base_id}_{chunk_num}",
                    text=chunk_text,
                    csi_code=metadata.get("csi_code"),
                    csi_title=metadata.get("csi_title"),
                    page_range=metadata.get("page_range", ""),
                    chunk_index=chunk_num,
                    total_chunks=0,
                    products_mentioned=metadata.get("products", []),
                    locals_mentioned=metadata.get("locals", []),
                    types_mentioned=metadata.get("types", [])
                ))
                chunk_num += 1
            
            start = end - self.overlap
            if start <= 0 or end == len(text):
                break
            start = max(start, 1)
        
        for chunk in chunks:
            chunk.total_chunks = len(chunks)
        
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """Clean text for chunking."""
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        text = re.sub(r'Centre de services scolaire.*?\n', '', text)
        text = re.sub(r'Page \d+ / \d+\s*\n?', '', text)
        return text.strip()
    
    def _find_break_points(self, text: str) -> list[int]:
        """Find good points to break text."""
        breaks = []
        
        for match in re.finditer(r'\n\n', text):
            breaks.append(match.end())
        
        for match in re.finditer(r'[.!?]\s+', text):
            breaks.append(match.end())
        
        for match in re.finditer(r'\n\.\d+\s', text):
            breaks.append(match.start())
        
        return sorted(set(breaks))
    
    def _find_best_break(self, breaks: list[int], target: int, min_pos: int) -> int:
        """Find the best break point near target but after min_pos."""
        candidates = [b for b in breaks if min_pos + 100 < b <= target + 100]
        
        if not candidates:
            return target
        
        before_target = [b for b in candidates if b <= target]
        if before_target:
            return max(before_target)
        
        return min(candidates)


def load_json(path: Path) -> dict:
    """Load JSON file safely."""
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def extract_products_names(products: list) -> list[str]:
    """Extract manufacturer names from product list."""
    names = []
    for p in products:
        if isinstance(p, dict):
            mfr = p.get("manufacturer", "")
            model = p.get("model", "")
            if mfr:
                names.append(f"{mfr} {model}".strip())
        elif isinstance(p, str):
            names.append(p)
    return names[:10]


def detect_types_from_csi(csi_code: str) -> list[str]:
    """Detect material types from CSI code."""
    types = []
    if not csi_code:
        return types
    
    for prefix, mat_type in CSI_TYPE_MAPPING.items():
        if csi_code.startswith(prefix):
            types.append(mat_type)
            break
    
    return types


def detect_types_from_text(text: str) -> list[str]:
    """Detect material types from text content."""
    types = set()
    text_lower = text.lower()
    
    for mat_type, keywords in TYPE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            types.add(mat_type)
    
    return list(types)


def build_chunks(devis_data: dict, chunk_builder: ChunkBuilder, local_validator: LocalValidator) -> list[dict]:
    """Build search chunks from devis data."""
    all_chunks = []
    
    csi_sections = devis_data.get("csi_sections_full", [])
    
    for section in csi_sections:
        code = section.get("code", "unknown")
        title = section.get("title", "")
        text = section.get("full_text", "")
        
        if not text or len(text) < 50:
            continue
        
        # Extract and validate locals
        raw_locals = section.get("locals_mentioned", [])
        valid_locals = []
        for loc in raw_locals:
            if local_validator.is_valid_local(loc, text):
                valid_locals.append(loc)
        
        # Also extract from text
        text_locals = local_validator.extract_locals(text)
        valid_locals = sorted(set(valid_locals + text_locals))
        
        # Detect types
        types = detect_types_from_csi(code)
        types.extend(detect_types_from_text(text))
        types = list(set(types))
        
        metadata = {
            "csi_code": code,
            "csi_title": title,
            "page_range": f"{section.get('start_page', '?')}-{section.get('end_page', '?')}",
            "products": extract_products_names(section.get("products", [])),
            "locals": valid_locals,
            "types": types
        }
        
        safe_code = code.replace(" ", "_")
        base_id = f"csi_{safe_code}"
        
        chunks = chunk_builder.chunk_text(text, base_id, metadata)
        all_chunks.extend([c.to_dict() for c in chunks])
    
    # Product chunks
    products_chunks = []
    for product in devis_data.get("products", []):
        context = product.get("context", "")
        if context and len(context) > 50:
            products_chunks.append({
                "id": f"product_{len(products_chunks)}",
                "text": f"Produit: {product.get('manufacturer', '')} | {product.get('model', '')}. {context}",
                "metadata": {
                    "csi_code": product.get("csi_section"),
                    "source": "product",
                    "manufacturer": product.get("manufacturer"),
                    "model": product.get("model")
                }
            })
    
    all_chunks.extend(products_chunks[:50])
    
    return all_chunks


def build_local_index(devis_data: dict, local_validator: LocalValidator) -> dict:
    """Build room/local → specs index with false positive filtering."""
    index = defaultdict(lambda: {"sections": [], "products": [], "contexts": []})
    
    for section in devis_data.get("csi_sections_full", []):
        text = section.get("full_text", "")
        
        # Extract valid locals
        valid_locals = local_validator.extract_locals(text)
        
        for local_ref in valid_locals:
            index[local_ref]["sections"].append({
                "csi_code": section.get("code"),
                "csi_title": section.get("title"),
                "pages": f"{section.get('start_page')}-{section.get('end_page')}"
            })
    
    # From local references (with validation)
    for ref in devis_data.get("local_references", []):
        room = ref.get("room_ref", "")
        context = ref.get("context", "")
        
        if room and local_validator.is_valid_local(room, context):
            index[room]["contexts"].append({
                "context": context,
                "page": ref.get("page_num")
            })
    
    # Clean up and deduplicate
    result = {}
    for local_ref, data in index.items():
        seen_sections = set()
        unique_sections = []
        for s in data["sections"]:
            key = s.get("csi_code", "")
            if key and key not in seen_sections:
                seen_sections.add(key)
                unique_sections.append(s)
        
        result[local_ref] = {
            "sections": unique_sections,
            "contexts": data["contexts"][:5]
        }
    
    return result


def build_type_index(devis_data: dict, chunks: list[dict]) -> dict:
    """
    Build material type → sections index.
    Enables: "Quelles sont les spécifications de peinture?"
    """
    index = defaultdict(lambda: {"sections": [], "chunks": [], "products": []})
    
    # From CSI sections
    for section in devis_data.get("csi_sections_full", []):
        code = section.get("code", "")
        title = section.get("title", "")
        text = section.get("full_text", "")
        
        types = detect_types_from_csi(code)
        types.extend(detect_types_from_text(text))
        
        for mat_type in set(types):
            index[mat_type]["sections"].append({
                "csi_code": code,
                "csi_title": title,
                "pages": f"{section.get('start_page')}-{section.get('end_page')}"
            })
    
    # From chunks
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        for mat_type in meta.get("types", []):
            if chunk["id"] not in [c["chunk_id"] for c in index[mat_type]["chunks"]]:
                index[mat_type]["chunks"].append({
                    "chunk_id": chunk["id"],
                    "csi_code": meta.get("csi_code")
                })
    
    # Deduplicate sections
    result = {}
    for mat_type, data in index.items():
        seen = set()
        unique_sections = []
        for s in data["sections"]:
            key = s.get("csi_code", "")
            if key and key not in seen:
                seen.add(key)
                unique_sections.append(s)
        
        result[mat_type] = {
            "sections": unique_sections,
            "chunk_count": len(data["chunks"])
        }
    
    return result


def build_product_index(devis_data: dict) -> dict:
    """Build product → sections index."""
    index = defaultdict(list)
    
    for section in devis_data.get("csi_sections_full", []):
        for product in section.get("products", []):
            mfr = product.get("manufacturer", "") if isinstance(product, dict) else str(product)
            if mfr:
                mfr_key = mfr.upper().split()[0]
                index[mfr_key].append({
                    "csi_code": section.get("code"),
                    "csi_title": section.get("title"),
                    "product": product
                })
    
    for product in devis_data.get("products", []):
        mfr = product.get("manufacturer", "")
        if mfr:
            mfr_key = mfr.upper().split()[0]
            index[mfr_key].append({
                "csi_code": product.get("csi_section"),
                "product": {
                    "manufacturer": mfr,
                    "model": product.get("model"),
                    "context": product.get("context", "")[:200]
                }
            })
    
    result = {}
    for mfr, entries in index.items():
        seen = set()
        unique = []
        for e in entries:
            key = (e.get("csi_code", ""), str(e.get("product", "")))
            if key not in seen:
                seen.add(key)
                unique.append(e)
        result[mfr] = unique[:20]
    
    return result


def build_unified_index(
    rooms_path: str,
    devis_path: str,
    guide_path: str,
    output_dir: str,
    chunk_size: int = 1000,
    overlap: int = 200
) -> dict:
    """Build complete RAG index with all components."""
    
    rooms_path = Path(rooms_path)
    devis_path = Path(devis_path)
    guide_path = Path(guide_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load sources
    rooms_data = load_json(rooms_path)
    devis_data = load_json(devis_path)
    guide_data = load_json(guide_path)
    
    print(f"Loaded devis: {len(devis_data.get('csi_sections_full', []))} full sections")
    
    # Initialize local validator with known rooms
    local_validator = LocalValidator()
    if rooms_data.get("rooms"):
        local_validator.add_valid_rooms(rooms_data["rooms"])
        print(f"Loaded {len(local_validator.valid_rooms)} valid room references")
    
    # Build chunks
    chunk_builder = ChunkBuilder(chunk_size=chunk_size, overlap=overlap)
    chunks = build_chunks(devis_data, chunk_builder, local_validator)
    
    # Build indexes
    local_index = build_local_index(devis_data, local_validator)
    type_index = build_type_index(devis_data, chunks)
    product_index = build_product_index(devis_data)
    
    # Save chunks.json
    chunks_path = output_dir / "chunks.json"
    with open(chunks_path, "w") as f:
        json.dump({
            "chunks": chunks,
            "stats": {
                "total_chunks": len(chunks),
                "avg_chunk_size": sum(len(c["text"]) for c in chunks) // max(len(chunks), 1),
                "chunk_size_target": chunk_size,
                "overlap": overlap
            }
        }, f, indent=2, ensure_ascii=False)
    print(f"✓ chunks.json: {len(chunks)} chunks")
    
    # Save local_index.json
    local_path = output_dir / "local_index.json"
    with open(local_path, "w") as f:
        json.dump({
            "local_index": local_index,
            "stats": {
                "total_locals": len(local_index),
                "locals_with_sections": sum(1 for v in local_index.values() if v.get("sections")),
                "false_positives_filtered": "Yes - phone numbers, dates, postal codes, plan refs excluded"
            }
        }, f, indent=2, ensure_ascii=False)
    print(f"✓ local_index.json: {len(local_index)} rooms indexed (filtered)")
    
    # Save type_index.json
    type_path = output_dir / "type_index.json"
    with open(type_path, "w") as f:
        json.dump({
            "type_index": type_index,
            "stats": {
                "total_types": len(type_index),
                "types_available": list(type_index.keys())
            }
        }, f, indent=2, ensure_ascii=False)
    print(f"✓ type_index.json: {len(type_index)} material types indexed")
    
    # Save product_index.json
    product_path = output_dir / "product_index.json"
    with open(product_path, "w") as f:
        json.dump({
            "product_index": product_index,
            "stats": {
                "total_manufacturers": len(product_index),
                "total_products": sum(len(v) for v in product_index.values())
            }
        }, f, indent=2, ensure_ascii=False)
    print(f"✓ product_index.json: {len(product_index)} manufacturers")
    
    # Build unified index
    unified = {
        "meta": {
            "project": devis_data.get("stats", {}).get("project", rooms_data.get("project", "Unknown Project")),
            "created_at": datetime.now().isoformat(),
            "sources": {
                "plans": str(rooms_path) if rooms_path.exists() else None,
                "devis": str(devis_path) if devis_path.exists() else None
            },
            "features": {
                "false_positive_filtering": True,
                "type_indexing": True,
                "cross_reference": True
            }
        },
        
        # From Plans
        "rooms": rooms_data.get("rooms", []),
        
        # CSI Sections (summary only)
        "csi_sections": [
            {
                "code": s.get("code"),
                "title": s.get("title"),
                "pages": f"{s.get('start_page')}-{s.get('end_page')}",
                "products_count": len(s.get("products", [])),
                "locals_mentioned": s.get("locals_mentioned", []),
                "types": detect_types_from_csi(s.get("code", ""))
            }
            for s in devis_data.get("csi_sections_full", [])
        ],
        
        # Products
        "products": devis_data.get("products", [])[:500],
        
        # Indexes
        "local_index": local_index,
        "type_index": type_index,
        "product_index": product_index,
        
        # Stats
        "stats": {
            "total_rooms": len(rooms_data.get("rooms", [])),
            "total_csi_sections": len(devis_data.get("csi_sections_full", [])),
            "total_products": len(devis_data.get("products", [])),
            "total_chunks": len(chunks),
            "total_locals_indexed": len(local_index),
            "total_types_indexed": len(type_index),
            "total_manufacturers": len(product_index)
        }
    }
    
    # Save unified_index.json
    unified_path = output_dir / "unified_index.json"
    with open(unified_path, "w") as f:
        json.dump(unified, f, indent=2, ensure_ascii=False)
    print(f"✓ unified_index.json: complete knowledge base")
    
    # Print summary
    print("\n" + "="*60)
    print("RAG INDEX SUMMARY")
    print("="*60)
    print(f"Total chunks for search: {len(chunks)}")
    print(f"Rooms indexed (filtered): {len(local_index)}")
    print(f"Material types indexed: {len(type_index)} ({', '.join(type_index.keys())})")
    print(f"Manufacturers indexed: {len(product_index)}")
    print(f"CSI sections: {len(devis_data.get('csi_sections_full', []))}")
    print("="*60)
    
    return unified


def main():
    parser = argparse.ArgumentParser(description="Build professional RAG index with false positive filtering")
    parser.add_argument("--rooms", default="output/rooms_extracted.json")
    parser.add_argument("--devis", default="output/devis_parsed.json")
    parser.add_argument("--guide", default="output/stable_rules.json")
    parser.add_argument("-o", "--output", default="output/rag")
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--overlap", type=int, default=200)
    
    args = parser.parse_args()
    build_unified_index(
        args.rooms, 
        args.devis, 
        args.guide, 
        args.output,
        args.chunk_size,
        args.overlap
    )


if __name__ == "__main__":
    main()
