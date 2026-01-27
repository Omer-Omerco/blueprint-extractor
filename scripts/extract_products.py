#!/usr/bin/env python3
"""
Product extractor for construction specifications (devis).
Extracts manufacturer names, product models, and specifications.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Product:
    """A product mentioned in specifications."""
    manufacturer: str
    model: Optional[str] = None
    product_type: Optional[str] = None
    specs: dict = field(default_factory=dict)
    context: str = ""
    page_num: int = 0
    csi_section: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "manufacturer": self.manufacturer,
            "model": self.model,
            "product_type": self.product_type,
            "specs": self.specs,
            "context": self.context[:200] if self.context else "",
            "page_num": self.page_num,
            "csi_section": self.csi_section
        }


class ProductExtractor:
    """
    Extracts products from specification text using pattern observation.
    No hardcoded manufacturer names - learns from document patterns.
    """
    
    # Patterns that typically introduce manufacturers
    MANUFACTURER_INTRO_PATTERNS = [
        # Quebec specs format: "Manufacturer | Product Name"
        re.compile(r'^([A-Z][A-Za-z0-9\s\-&\.]+?)\s*\|\s*(.+?)$', re.MULTILINE),
        re.compile(r'(?:fabricant|manufacturer|fournisseur)\s*[:\-]?\s*(.+?)(?:\.|$)', re.IGNORECASE),
        re.compile(r'(?:marque|brand)\s*[:\-]?\s*(.+?)(?:\.|$)', re.IGNORECASE),
        re.compile(r'(?:produit\s+de|product\s+by)\s+(.+?)(?:\.|$)', re.IGNORECASE),
        re.compile(r'(?:fabriqué\s+par|made\s+by)\s+(.+?)(?:\.|$)', re.IGNORECASE),
    ]
    
    # Quebec-style product reference: "Manufacturer | Product"
    # Requires manufacturer to start with capital and have reasonable name pattern
    PIPE_PRODUCT_PATTERN = re.compile(
        r'([A-Z][A-Za-z\.\-]+(?:\s+[A-Za-z&\.\-]+)*?)\s*\|\s*([A-Z][A-Za-z0-9\s\-\.]+)',
        re.MULTILINE
    )
    
    # Patterns for model numbers (alphanumeric with dashes)
    MODEL_PATTERN = re.compile(
        r'(?:modèle|model|série|series|type|no\.?|#)\s*[:\-]?\s*'
        r'([A-Z0-9][\w\-\.]{2,})',
        re.IGNORECASE
    )
    
    # Pattern for standalone model numbers (all caps with numbers)
    STANDALONE_MODEL = re.compile(r'\b([A-Z]{2,}[\-]?\d+[\w\-]*)\b')
    
    # Patterns for specifications
    SPEC_PATTERNS = {
        "dimension": re.compile(
            r'(\d+(?:[.,]\d+)?)\s*(?:x|×|par)\s*(\d+(?:[.,]\d+)?)'
            r'(?:\s*(?:x|×|par)\s*(\d+(?:[.,]\d+)?))?'
            r'\s*(mm|cm|m|po|pi|"|\')?',
            re.IGNORECASE
        ),
        "thickness": re.compile(
            r'(?:épaisseur|thickness|épais\.?)\s*[:\-]?\s*'
            r'(\d+(?:[.,]\d+)?)\s*(mm|cm|po|")?',
            re.IGNORECASE
        ),
        "color": re.compile(
            r'(?:couleur|color|fini|finish)\s*[:\-]?\s*([A-Za-zÀ-ÿ\s]+?)(?:\.|,|$)',
            re.IGNORECASE
        ),
        "rating": re.compile(
            r'(?:classe|class|rating|type)\s*[:\-]?\s*([A-Z0-9]+)',
            re.IGNORECASE
        ),
        "fire_rating": re.compile(
            r'(?:résistance\s+au\s+feu|fire\s+rating)\s*[:\-]?\s*'
            r'(\d+(?:[.,]\d+)?\s*(?:h|hr|heure|hour)?)',
            re.IGNORECASE
        ),
    }
    
    # Common product type indicators (observed from document structure)
    PRODUCT_TYPE_PATTERNS = [
        re.compile(r'(?:^|\s)(porte|door)s?\b', re.IGNORECASE),
        re.compile(r'(?:^|\s)(fenêtre|window)s?\b', re.IGNORECASE),
        re.compile(r'(?:^|\s)(peinture|paint)s?\b', re.IGNORECASE),
        re.compile(r'(?:^|\s)(plancher|flooring|floor)s?\b', re.IGNORECASE),
        re.compile(r'(?:^|\s)(plafond|ceiling)s?\b', re.IGNORECASE),
        re.compile(r'(?:^|\s)(isolation|insulation)\b', re.IGNORECASE),
        re.compile(r'(?:^|\s)(gypse|drywall|gyproc)\b', re.IGNORECASE),
        re.compile(r'(?:^|\s)(tuile|tile)s?\b', re.IGNORECASE),
        re.compile(r'(?:^|\s)(béton|concrete)\b', re.IGNORECASE),
        re.compile(r'(?:^|\s)(acier|steel)\b', re.IGNORECASE),
        re.compile(r'(?:^|\s)(bois|wood)\b', re.IGNORECASE),
        re.compile(r'(?:^|\s)(verre|glass)\b', re.IGNORECASE),
        re.compile(r'(?:^|\s)(quincaillerie|hardware)\b', re.IGNORECASE),
        re.compile(r'(?:^|\s)(membrane|membrane)\b', re.IGNORECASE),
        re.compile(r'(?:^|\s)(revêtement|cladding|siding)\b', re.IGNORECASE),
    ]
    
    def __init__(self, blocks: list = None, csi_context: dict = None):
        """
        Initialize extractor.
        
        Args:
            blocks: Text blocks from the document
            csi_context: Dict mapping page numbers to CSI codes
        """
        self.blocks = blocks or []
        self.csi_context = csi_context or {}
        self.discovered_manufacturers = set()
        
    def _extract_specs(self, text: str) -> dict:
        """Extract specifications from text."""
        specs = {}
        
        for spec_name, pattern in self.SPEC_PATTERNS.items():
            match = pattern.search(text)
            if match:
                if spec_name == "dimension":
                    dims = [g for g in match.groups()[:3] if g]
                    unit = match.group(4) or ""
                    specs["dimension"] = f"{' x '.join(dims)} {unit}".strip()
                else:
                    specs[spec_name] = match.group(1).strip()
        
        return specs
    
    def _detect_product_type(self, text: str) -> Optional[str]:
        """Detect product type from context."""
        for pattern in self.PRODUCT_TYPE_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1).lower()
        return None
    
    def _extract_manufacturers_from_text(self, text: str, page_num: int) -> list[Product]:
        """Extract manufacturer mentions from a text block."""
        products = []
        
        # First, try Quebec pipe format: "Manufacturer | Product"
        for match in self.PIPE_PRODUCT_PATTERN.finditer(text):
            manufacturer = match.group(1).strip()
            product_name = match.group(2).strip()
            
            # Clean up
            manufacturer = re.sub(r'\s+', ' ', manufacturer)
            manufacturer = manufacturer.rstrip('.,;:')
            product_name = product_name.rstrip('.,;:')
            
            if len(manufacturer) < 2 or len(manufacturer) > 40:
                continue
            
            # Skip common words and non-manufacturer patterns
            skip_words = {
                'ou', 'et', 'le', 'la', 'les', 'un', 'une', 'de', 'du', 'des',
                'or', 'and', 'the', 'a', 'an', 'of', 'to',
                'équivalent', 'equivalent', 'approuvé', 'approved',
                'produit', 'product', 'référence', 'reference', 'références',
                'avant', 'après', 'selon', 'avec', 'sans', 'pour',
                'des matériaux', 'avant de', 'et de', 'des granulats',
                'installations', 'conditions', 'recommandations'
            }
            if manufacturer.lower().strip() in skip_words:
                continue
            # Skip single words that are common French/English
            if re.match(r'^(et|ou|de|des|le|la|sans|avec|pour|avant|après)\s', manufacturer.lower()):
                continue
            # Skip if it looks like a sentence fragment
            if any(w in manufacturer.lower() for w in ['avant', 'après', 'selon', 'avec', 'des ', 'et de']):
                continue
            # Must start with proper capital letter
            if not manufacturer[0].isupper():
                continue
            
            self.discovered_manufacturers.add(manufacturer)
            
            # Get specs from context
            specs = self._extract_specs(text)
            
            # Get product type from context
            product_type = self._detect_product_type(text)
            
            # Get CSI context
            csi = self.csi_context.get(page_num)
            
            product = Product(
                manufacturer=manufacturer,
                model=product_name,  # In pipe format, second part is product/model
                product_type=product_type,
                specs=specs,
                context=text[:200],
                page_num=page_num,
                csi_section=csi
            )
            products.append(product)
        
        # Then try other patterns for non-pipe format
        for pattern in self.MANUFACTURER_INTRO_PATTERNS[1:]:  # Skip pipe pattern (index 0)
            for match in pattern.finditer(text):
                manufacturer = match.group(1).strip()
                # Clean up
                manufacturer = re.sub(r'\s+', ' ', manufacturer)
                manufacturer = manufacturer.rstrip('.,;:')
                
                if len(manufacturer) < 2 or len(manufacturer) > 50:
                    continue
                
                # Skip if it's just common words
                if manufacturer.lower() in {'ou', 'et', 'le', 'la', 'les', 'un', 'une',
                                             'or', 'and', 'the', 'a', 'an', 'équivalent',
                                             'equivalent', 'approuvé', 'approved'}:
                    continue
                
                self.discovered_manufacturers.add(manufacturer)
                
                # Find model if present
                model = None
                model_match = self.MODEL_PATTERN.search(text)
                if model_match:
                    model = model_match.group(1)
                
                # Get specs
                specs = self._extract_specs(text)
                
                # Get product type
                product_type = self._detect_product_type(text)
                
                # Get CSI context
                csi = self.csi_context.get(page_num)
                
                product = Product(
                    manufacturer=manufacturer,
                    model=model,
                    product_type=product_type,
                    specs=specs,
                    context=text[:200],
                    page_num=page_num,
                    csi_section=csi
                )
                products.append(product)
        
        return products
    
    def _extract_from_list_format(self, text: str, page_num: int) -> list[Product]:
        """
        Extract products from list format often found in specs.
        Example:
        - Armstrong (ou équivalent approuvé)
        - USG
        - CertainTeed
        """
        products = []
        
        # Pattern for list items that look like manufacturer names
        list_pattern = re.compile(
            r'(?:^|\n)\s*[\-•\*]\s*([A-Z][A-Za-z\s&]+?)(?:\s*\(|$|\n)',
            re.MULTILINE
        )
        
        for match in list_pattern.finditer(text):
            manufacturer = match.group(1).strip()
            
            if len(manufacturer) < 2 or len(manufacturer) > 40:
                continue
            
            # Skip common non-manufacturer phrases
            skip_words = {'ou équivalent', 'or equivalent', 'section', 'partie', 
                         'article', 'note', 'voir', 'see', 'référence'}
            if any(sw in manufacturer.lower() for sw in skip_words):
                continue
            
            self.discovered_manufacturers.add(manufacturer)
            
            product = Product(
                manufacturer=manufacturer,
                context=text[max(0, match.start()-50):match.end()+50],
                page_num=page_num,
                csi_section=self.csi_context.get(page_num)
            )
            products.append(product)
        
        return products
    
    def extract_products(self) -> list[Product]:
        """Extract all products from document blocks."""
        all_products = []
        
        for block in self.blocks:
            text = block.text if hasattr(block, 'text') else str(block)
            page_num = block.page_num if hasattr(block, 'page_num') else 0
            
            # Try different extraction methods
            products = self._extract_manufacturers_from_text(text, page_num)
            products.extend(self._extract_from_list_format(text, page_num))
            
            all_products.extend(products)
        
        # Deduplicate by manufacturer+model
        seen = set()
        unique_products = []
        for p in all_products:
            key = (p.manufacturer.lower(), p.model)
            if key not in seen:
                seen.add(key)
                unique_products.append(p)
        
        return unique_products


def extract_products_from_raw_text(text: str, page_num: int = 0) -> list[dict]:
    """
    Convenience function to extract products from raw text.
    
    Args:
        text: Raw text content
        page_num: Optional page number for context
        
    Returns:
        List of product dictionaries
    """
    
    class SimpleBlock:
        def __init__(self, text, page_num):
            self.text = text
            self.page_num = page_num
    
    blocks = [SimpleBlock(text, page_num)]
    extractor = ProductExtractor(blocks)
    products = extractor.extract_products()
    
    return [p.to_dict() for p in products]
