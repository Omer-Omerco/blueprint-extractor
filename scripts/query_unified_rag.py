#!/usr/bin/env python3
"""
Query the Unified RAG for Construction Projects.

Answers questions about rooms, materials, products, etc.
Anti-hallucination: Returns "Information non trouvée" when no data matches.

Usage:
    python scripts/query_unified_rag.py "Quelle peinture pour le local A-101?"
    python scripts/query_unified_rag.py "Quels sont les produits Mapei?"
    python scripts/query_unified_rag.py --local A-101
    python scripts/query_unified_rag.py --type peinture
"""

import argparse
import json
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from collections import defaultdict


# ==============================================================================
# Configuration
# ==============================================================================

RAG_DIR = Path(__file__).parent.parent / "output" / "rag"

# CSI sections par type de matériau/travail
TYPE_CSI_MAPPING = {
    "peinture": ["09 91 00", "09 91 23", "09 90 00"],
    "plancher": ["09 65 00", "09 68 00", "09 64 00", "09 63 00", "09 62 00"],
    "porte": ["08 11 00", "08 14 00", "08 71 00", "08 12 00"],
    "fenêtre": ["08 51 00", "08 52 00", "08 53 00", "08 50 00"],
    "plafond": ["09 51 00", "09 54 00"],
    "mur": ["09 21 00", "09 22 00", "09 29 00", "04 22 00"],
    "céramique": ["09 30 00", "09 31 00"],
    "isolation": ["07 21 00", "07 22 00", "07 27 00"],
    "étanchéité": ["07 92 00", "07 90 00"],
    "toiture": ["07 50 00", "07 51 00", "07 52 00"],
    "acier": ["05 12 00", "05 21 00", "05 50 00"],
    "béton": ["03 30 00", "03 31 00"],
    "électricité": ["26 00 00", "26 05 00", "26 27 00"],
    "mécanique": ["23 00 00", "21 00 00"],
    "gicleurs": ["21 13 00", "21 13 13"],
}

# Mots-clés pour détecter le type de question
TYPE_KEYWORDS = {
    "peinture": ["peinture", "peindre", "peint", "latex", "apprêt", "primer", "couleur"],
    "plancher": ["plancher", "sol", "revêtement de sol", "flooring", "époxy", "VCT", "vinyle", "linoleum"],
    "porte": ["porte", "cadre", "serrure", "quincaillerie", "penture"],
    "fenêtre": ["fenêtre", "vitrage", "vitre", "châssis", "store"],
    "plafond": ["plafond", "tuile acoustique", "suspendu", "ceiling"],
    "mur": ["mur", "cloison", "gypse", "placoplâtre", "drywall"],
    "céramique": ["céramique", "carrelage", "carreau", "tuile", "porcelaine"],
    "isolation": ["isolation", "isolant", "thermique", "acoustique", "pare-vapeur"],
    "étanchéité": ["étanchéité", "scellant", "calfeutrage", "joint"],
}


@dataclass
class SearchResult:
    """A search result with source citation."""
    text: str
    source: str
    csi_code: Optional[str]
    csi_title: Optional[str]
    relevance: float = 1.0
    
    def format(self) -> str:
        """Format result for display."""
        source_info = f"[{self.csi_code}] {self.csi_title}" if self.csi_code else self.source
        return f"📄 Source: {source_info}\n{self.text}"


class RAGQuery:
    """Query engine for the unified RAG."""
    
    def __init__(self, rag_dir: Path = RAG_DIR):
        self.rag_dir = rag_dir
        self.chunks = []
        self.local_index = {}
        self.product_index = {}
        self.type_index = {}
        self.unified = {}
        self._load_data()
    
    def _load_data(self):
        """Load all RAG data files."""
        # Chunks
        chunks_path = self.rag_dir / "chunks.json"
        if chunks_path.exists():
            with open(chunks_path) as f:
                data = json.load(f)
                self.chunks = data.get("chunks", [])
        
        # Local index
        local_path = self.rag_dir / "local_index.json"
        if local_path.exists():
            with open(local_path) as f:
                data = json.load(f)
                self.local_index = data.get("local_index", {})
        
        # Product index
        product_path = self.rag_dir / "product_index.json"
        if product_path.exists():
            with open(product_path) as f:
                data = json.load(f)
                self.product_index = data.get("product_index", {})
        
        # Type index (if exists)
        type_path = self.rag_dir / "type_index.json"
        if type_path.exists():
            with open(type_path) as f:
                data = json.load(f)
                self.type_index = data.get("type_index", {})
        
        # Unified index
        unified_path = self.rag_dir / "unified_index.json"
        if unified_path.exists():
            with open(unified_path) as f:
                self.unified = json.load(f)
        
        print(f"✓ Loaded {len(self.chunks)} chunks, {len(self.local_index)} locals, {len(self.product_index)} manufacturers")
    
    def _is_valid_local(self, local_ref: str) -> bool:
        """
        Check if a local reference is a valid room number.
        Filters out false positives like phone numbers, dates, plan references.
        """
        # Valid patterns: A-101, B-106, C-101, 101, 204 (but not E-101, S101 which are plans)
        
        # Plan references (E=Électrique, S=Structure, W=Mécanique, M=Mécanique, C=Civil)
        if re.match(r'^[ESWMF]-?\d+$', local_ref, re.IGNORECASE):
            return False
        
        # Single letters or very short refs
        if len(local_ref) <= 2:
            return False
        
        # Valid room patterns
        # A-101, B-106 format (block-room)
        if re.match(r'^[A-D]-\d{3}$', local_ref):
            return True
        
        # Pure 3-digit room numbers (101-999)
        if re.match(r'^\d{3}$', local_ref):
            num = int(local_ref)
            if 100 <= num <= 999:
                return True
        
        return False
    
    def query_local(self, local_ref: str) -> list[SearchResult]:
        """Query specifications for a specific room/local."""
        results = []
        
        # Normalize local ref
        local_ref = local_ref.upper().strip()
        
        # Check local index
        if local_ref in self.local_index:
            data = self.local_index[local_ref]
            
            # Get sections that mention this local
            for section in data.get("sections", []):
                csi_code = section.get("csi_code", "")
                csi_title = section.get("csi_title", "")
                
                # Find corresponding chunks
                for chunk in self.chunks:
                    meta = chunk.get("metadata", {})
                    if meta.get("csi_code") == csi_code:
                        # Check if this chunk actually mentions the local
                        if local_ref in chunk.get("text", "").upper():
                            results.append(SearchResult(
                                text=chunk["text"][:800],
                                source=f"Devis p.{meta.get('page_range', '?')}",
                                csi_code=csi_code,
                                csi_title=csi_title,
                                relevance=1.0
                            ))
            
            # Add contexts
            for ctx in data.get("contexts", [])[:3]:
                results.append(SearchResult(
                    text=ctx.get("context", ""),
                    source=f"Devis p.{ctx.get('page', '?')}",
                    csi_code=None,
                    csi_title="Contexte",
                    relevance=0.8
                ))
        
        # Also search chunks for mentions
        if not results:
            for chunk in self.chunks:
                text = chunk.get("text", "")
                if local_ref in text.upper() or local_ref.replace("-", "") in text.upper():
                    meta = chunk.get("metadata", {})
                    results.append(SearchResult(
                        text=text[:800],
                        source=f"Devis p.{meta.get('page_range', '?')}",
                        csi_code=meta.get("csi_code"),
                        csi_title=meta.get("csi_title"),
                        relevance=0.7
                    ))
                    if len(results) >= 5:
                        break
        
        return results
    
    def query_type(self, material_type: str) -> list[SearchResult]:
        """Query by material/work type (peinture, plancher, etc.)."""
        results = []
        material_type = material_type.lower().strip()
        
        # Get relevant CSI codes
        csi_codes = TYPE_CSI_MAPPING.get(material_type, [])
        
        # Also check type_index if available
        if material_type in self.type_index:
            type_data = self.type_index[material_type]
            for section in type_data.get("sections", [])[:10]:
                csi_code = section.get("csi_code", "")
                if csi_code not in csi_codes:
                    csi_codes.append(csi_code)
        
        # Search chunks with matching CSI codes
        for chunk in self.chunks:
            meta = chunk.get("metadata", {})
            chunk_csi = meta.get("csi_code", "")
            
            # Match by CSI code
            if chunk_csi and any(chunk_csi.startswith(code[:5]) for code in csi_codes):
                results.append(SearchResult(
                    text=chunk["text"][:1000],
                    source=f"Devis p.{meta.get('page_range', '?')}",
                    csi_code=chunk_csi,
                    csi_title=meta.get("csi_title"),
                    relevance=1.0
                ))
        
        # Also search by keywords in text
        keywords = TYPE_KEYWORDS.get(material_type, [material_type])
        for chunk in self.chunks:
            text = chunk.get("text", "").lower()
            meta = chunk.get("metadata", {})
            
            if any(kw in text for kw in keywords):
                # Avoid duplicates
                if not any(r.csi_code == meta.get("csi_code") and r.text[:100] == chunk["text"][:100] for r in results):
                    results.append(SearchResult(
                        text=chunk["text"][:800],
                        source=f"Devis p.{meta.get('page_range', '?')}",
                        csi_code=meta.get("csi_code"),
                        csi_title=meta.get("csi_title"),
                        relevance=0.8
                    ))
        
        # Sort by relevance and limit
        results.sort(key=lambda r: r.relevance, reverse=True)
        return results[:10]
    
    def query_product(self, manufacturer: str) -> list[SearchResult]:
        """Query by manufacturer/product."""
        results = []
        mfr = manufacturer.upper().strip()
        
        # Check product index
        for key, products in self.product_index.items():
            if mfr in key or key in mfr:
                for prod in products[:5]:
                    csi_code = prod.get("csi_code", "")
                    product_info = prod.get("product", {})
                    
                    if isinstance(product_info, dict):
                        text = f"Fabricant: {product_info.get('manufacturer', '')}\nModèle: {product_info.get('model', '')}\n{product_info.get('context', '')}"
                    else:
                        text = str(product_info)
                    
                    results.append(SearchResult(
                        text=text,
                        source=f"Section CSI {csi_code}",
                        csi_code=csi_code,
                        csi_title=prod.get("csi_title"),
                        relevance=1.0
                    ))
        
        # Search chunks for manufacturer mentions
        for chunk in self.chunks:
            text = chunk.get("text", "")
            if mfr.lower() in text.lower():
                meta = chunk.get("metadata", {})
                results.append(SearchResult(
                    text=text[:800],
                    source=f"Devis p.{meta.get('page_range', '?')}",
                    csi_code=meta.get("csi_code"),
                    csi_title=meta.get("csi_title"),
                    relevance=0.8
                ))
                if len(results) >= 10:
                    break
        
        return results[:10]
    
    def query_free_text(self, query: str) -> list[SearchResult]:
        """Free text search across all chunks."""
        results = []
        query_lower = query.lower()
        query_terms = query_lower.split()
        
        for chunk in self.chunks:
            text = chunk.get("text", "")
            text_lower = text.lower()
            
            # Calculate relevance based on term matches
            matches = sum(1 for term in query_terms if term in text_lower)
            if matches > 0:
                relevance = matches / len(query_terms)
                meta = chunk.get("metadata", {})
                
                results.append(SearchResult(
                    text=text[:800],
                    source=f"Devis p.{meta.get('page_range', '?')}",
                    csi_code=meta.get("csi_code"),
                    csi_title=meta.get("csi_title"),
                    relevance=relevance
                ))
        
        # Sort by relevance
        results.sort(key=lambda r: r.relevance, reverse=True)
        return results[:10]
    
    def analyze_question(self, question: str) -> dict:
        """Analyze a question to determine query strategy."""
        question_lower = question.lower()
        
        result = {
            "local": None,
            "type": None,
            "manufacturer": None,
            "free_text": question
        }
        
        # Detect local reference
        local_patterns = [
            r'\blocal\s+([A-D]-?\d{3})\b',
            r'\blocal\s+(\d{3})\b',
            r'\b([A-D]-\d{3})\b',
        ]
        for pattern in local_patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                result["local"] = match.group(1).upper()
                break
        
        # Detect material type
        for mat_type, keywords in TYPE_KEYWORDS.items():
            if any(kw in question_lower for kw in keywords):
                result["type"] = mat_type
                break
        
        # Detect manufacturer (common ones)
        manufacturers = ["mapei", "benjamin moore", "sherwin", "armstrong", "tarkett", 
                        "certainteed", "cgc", "lafarge", "hilti", "sika", "tremco"]
        for mfr in manufacturers:
            if mfr in question_lower:
                result["manufacturer"] = mfr.upper()
                break
        
        return result
    
    def query(self, question: str) -> list[SearchResult]:
        """
        Main query method - analyzes question and returns relevant results.
        """
        analysis = self.analyze_question(question)
        results = []
        
        # Priority: local > type > manufacturer > free text
        if analysis["local"]:
            results = self.query_local(analysis["local"])
            
            # If also asking about a type, filter results
            if analysis["type"] and results:
                type_csi = TYPE_CSI_MAPPING.get(analysis["type"], [])
                filtered = [r for r in results if r.csi_code and any(r.csi_code.startswith(c[:5]) for c in type_csi)]
                if filtered:
                    results = filtered
                else:
                    # Also get type results
                    type_results = self.query_type(analysis["type"])
                    results.extend(type_results)
        
        elif analysis["type"]:
            results = self.query_type(analysis["type"])
        
        elif analysis["manufacturer"]:
            results = self.query_product(analysis["manufacturer"])
        
        else:
            results = self.query_free_text(question)
        
        return results


def format_response(question: str, results: list[SearchResult]) -> str:
    """Format results for display."""
    if not results:
        return "❌ Information non trouvée dans le devis.\n\nLa question n'a retourné aucun résultat. Vérifiez:\n- Le numéro de local (format: A-101, B-106, etc.)\n- L'orthographe des termes recherchés"
    
    output = [f"🔍 Question: {question}\n"]
    output.append(f"📊 {len(results)} résultat(s) trouvé(s):\n")
    output.append("=" * 60 + "\n")
    
    for i, result in enumerate(results[:5], 1):
        output.append(f"\n--- Résultat {i} ---")
        output.append(result.format())
        output.append("")
    
    if len(results) > 5:
        output.append(f"\n... et {len(results) - 5} autres résultats")
    
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="Query the unified RAG")
    parser.add_argument("question", nargs="?", help="Question en français")
    parser.add_argument("--local", help="Query by local/room number")
    parser.add_argument("--type", help="Query by material type (peinture, plancher, etc.)")
    parser.add_argument("--product", help="Query by manufacturer/product")
    parser.add_argument("--rag-dir", default=str(RAG_DIR), help="RAG directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    rag = RAGQuery(Path(args.rag_dir))
    
    results = []
    question = ""
    
    if args.local:
        question = f"Spécifications pour local {args.local}"
        results = rag.query_local(args.local)
    elif args.type:
        question = f"Sections concernant: {args.type}"
        results = rag.query_type(args.type)
    elif args.product:
        question = f"Produits du fabricant: {args.product}"
        results = rag.query_product(args.product)
    elif args.question:
        question = args.question
        results = rag.query(args.question)
    else:
        parser.print_help()
        return
    
    if args.json:
        output = {
            "question": question,
            "results_count": len(results),
            "results": [
                {
                    "text": r.text,
                    "source": r.source,
                    "csi_code": r.csi_code,
                    "csi_title": r.csi_title,
                    "relevance": r.relevance
                }
                for r in results
            ]
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(format_response(question, results))


if __name__ == "__main__":
    main()
