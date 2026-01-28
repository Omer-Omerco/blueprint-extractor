#!/usr/bin/env python3
"""
Quality Alert System for Blueprint Extraction.

Generates warnings, errors, and statistics based on extraction quality.
- WARNING: Uncertain data (confidence < 0.7)
- ERROR: Contradictory or missing data
- INFO: Extraction statistics

Usage:
    python alerts.py --rooms output/rooms_complete.json --output output/alerts.json
"""

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from collections import defaultdict


# Confidence thresholds
CONFIDENCE_WARNING_THRESHOLD = 0.7
CONFIDENCE_ERROR_THRESHOLD = 0.4


@dataclass
class Alert:
    """Single alert entry."""
    type: str  # LOW_CONFIDENCE, MISSING_DIMENSION, CONTRADICTORY_DATA, etc.
    item: str  # Room/product ID
    message: str
    severity: str  # WARNING, ERROR, INFO
    details: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "item": self.item,
            "message": self.message,
            "severity": self.severity,
            "details": self.details
        }


class AlertGenerator:
    """Generate quality alerts from extraction data."""
    
    def __init__(self):
        self.warnings: list[Alert] = []
        self.errors: list[Alert] = []
        self.info: list[Alert] = []
        self.stats: dict = {}
    
    def add_warning(self, alert_type: str, item: str, message: str, **details):
        """Add a WARNING level alert."""
        self.warnings.append(Alert(
            type=alert_type,
            item=item,
            message=message,
            severity="WARNING",
            details=details
        ))
    
    def add_error(self, alert_type: str, item: str, message: str, **details):
        """Add an ERROR level alert."""
        self.errors.append(Alert(
            type=alert_type,
            item=item,
            message=message,
            severity="ERROR",
            details=details
        ))
    
    def add_info(self, alert_type: str, item: str, message: str, **details):
        """Add an INFO level alert."""
        self.info.append(Alert(
            type=alert_type,
            item=item,
            message=message,
            severity="INFO",
            details=details
        ))
    
    def analyze_rooms(self, rooms_data: dict) -> None:
        """Analyze rooms for quality issues."""
        rooms = rooms_data.get("rooms", [])
        
        # Statistics counters
        total_rooms = len(rooms)
        rooms_with_confidence = 0
        rooms_low_confidence = 0
        rooms_missing_pages = 0
        rooms_single_source = 0
        confidence_sum = 0
        extraction_methods = defaultdict(int)
        
        for room in rooms:
            room_id = room.get("id", "UNKNOWN")
            confidence = room.get("confidence")
            source_pages = room.get("source_pages", room.get("pages", []))
            extraction_method = room.get("extraction_method", "unknown")
            
            # Track extraction methods
            extraction_methods[extraction_method] += 1
            
            # Check confidence
            if confidence is not None:
                rooms_with_confidence += 1
                confidence_sum += confidence
                
                if confidence < CONFIDENCE_ERROR_THRESHOLD:
                    self.add_error(
                        "VERY_LOW_CONFIDENCE",
                        room_id,
                        f"Confidence très basse ({confidence:.2f}) - vérification manuelle requise",
                        confidence=confidence,
                        threshold=CONFIDENCE_ERROR_THRESHOLD
                    )
                elif confidence < CONFIDENCE_WARNING_THRESHOLD:
                    rooms_low_confidence += 1
                    self.add_warning(
                        "LOW_CONFIDENCE",
                        room_id,
                        f"Confidence incertaine ({confidence:.2f}) - données à valider",
                        confidence=confidence,
                        threshold=CONFIDENCE_WARNING_THRESHOLD
                    )
            
            # Check source pages
            if not source_pages:
                rooms_missing_pages += 1
                self.add_error(
                    "NO_SOURCE_PAGES",
                    room_id,
                    "Aucune page source identifiée - origine inconnue",
                    room_name=room.get("name", "")
                )
            elif len(source_pages) == 1:
                rooms_single_source += 1
                self.add_warning(
                    "SINGLE_SOURCE",
                    room_id,
                    f"Une seule page source ({source_pages[0]}) - moins fiable",
                    page=source_pages[0]
                )
            
            # Check for missing dimensions (if applicable)
            if room.get("dimensions") is None and room.get("area") is None:
                # Not an error for all rooms - some don't have dimensions in plans
                pass
            
            # Check name consistency
            name = room.get("name", "")
            if name == "LOCAL" or name == "":
                self.add_warning(
                    "GENERIC_NAME",
                    room_id,
                    "Nom générique 'LOCAL' - fonction non identifiée",
                    name=name
                )
            
            # Check for extraction notes indicating issues
            notes = room.get("extraction_notes", "")
            if notes and any(kw in notes.lower() for kw in ["ambigu", "incertain", "possible", "?"]):
                self.add_warning(
                    "AMBIGUOUS_EXTRACTION",
                    room_id,
                    f"Note d'extraction indique une ambiguïté: {notes}",
                    notes=notes
                )
        
        # Calculate statistics
        avg_confidence = (confidence_sum / rooms_with_confidence) if rooms_with_confidence > 0 else 0
        
        self.stats = {
            "total_rooms": total_rooms,
            "rooms_with_confidence": rooms_with_confidence,
            "rooms_low_confidence": rooms_low_confidence,
            "rooms_missing_pages": rooms_missing_pages,
            "rooms_single_source": rooms_single_source,
            "average_confidence": round(avg_confidence, 3),
            "extraction_methods": dict(extraction_methods)
        }
        
        # Add summary info
        self.add_info(
            "EXTRACTION_SUMMARY",
            "GLOBAL",
            f"Extraction complétée: {total_rooms} locaux, confidence moyenne {avg_confidence:.2f}",
            **self.stats
        )
        
        # Coverage warning
        if rooms_with_confidence < total_rooms * 0.5:
            self.add_warning(
                "LOW_CONFIDENCE_COVERAGE",
                "GLOBAL",
                f"Seulement {rooms_with_confidence}/{total_rooms} locaux ont un score de confidence",
                coverage_ratio=rooms_with_confidence / total_rooms if total_rooms > 0 else 0
            )
    
    def analyze_products(self, products: list[dict]) -> None:
        """Analyze products for quality issues."""
        total_products = len(products)
        products_with_confidence = 0
        low_confidence_products = 0
        
        for product in products:
            product_id = f"{product.get('manufacturer', 'UNKNOWN')}_{product.get('model', 'UNKNOWN')}"
            confidence = product.get("confidence")
            
            if confidence is not None:
                products_with_confidence += 1
                
                if confidence < CONFIDENCE_WARNING_THRESHOLD:
                    low_confidence_products += 1
                    self.add_warning(
                        "LOW_PRODUCT_CONFIDENCE",
                        product_id,
                        f"Produit avec confidence faible ({confidence:.2f})",
                        manufacturer=product.get("manufacturer"),
                        model=product.get("model"),
                        confidence=confidence
                    )
        
        if total_products > 0:
            self.add_info(
                "PRODUCT_SUMMARY",
                "GLOBAL",
                f"Produits extraits: {total_products}, {products_with_confidence} avec confidence",
                total_products=total_products,
                products_with_confidence=products_with_confidence,
                low_confidence_count=low_confidence_products
            )
    
    def check_contradictions(self, rooms_data: dict) -> None:
        """Check for contradictory data across sources."""
        rooms = rooms_data.get("rooms", [])
        rooms_by_id = defaultdict(list)
        
        # Group by ID to detect duplicates
        for room in rooms:
            room_id = room.get("id")
            if room_id:
                rooms_by_id[room_id].append(room)
        
        # Check for duplicates with different data
        for room_id, entries in rooms_by_id.items():
            if len(entries) > 1:
                names = set(e.get("name", "") for e in entries)
                if len(names) > 1:
                    self.add_error(
                        "CONTRADICTORY_NAME",
                        room_id,
                        f"Noms contradictoires pour le même local: {', '.join(names)}",
                        names=list(names)
                    )
    
    def generate_report(self) -> dict:
        """Generate complete alert report."""
        return {
            "generated_at": datetime.now().isoformat(),
            "warnings": [w.to_dict() for w in self.warnings],
            "errors": [e.to_dict() for e in self.errors],
            "info": [i.to_dict() for i in self.info],
            "summary": {
                "total_warnings": len(self.warnings),
                "total_errors": len(self.errors),
                "total_info": len(self.info),
                "stats": self.stats
            }
        }


def analyze_extraction(rooms_path: Path, products_path: Optional[Path] = None) -> dict:
    """
    Main analysis function.
    
    Args:
        rooms_path: Path to rooms_complete.json
        products_path: Optional path to products JSON
    
    Returns:
        Alert report dictionary
    """
    generator = AlertGenerator()
    
    # Load and analyze rooms
    if rooms_path.exists():
        with open(rooms_path) as f:
            rooms_data = json.load(f)
        generator.analyze_rooms(rooms_data)
        generator.check_contradictions(rooms_data)
    else:
        generator.add_error(
            "FILE_NOT_FOUND",
            str(rooms_path),
            f"Fichier rooms non trouvé: {rooms_path}"
        )
    
    # Load and analyze products if available
    if products_path and products_path.exists():
        with open(products_path) as f:
            products_data = json.load(f)
        products = products_data.get("products", products_data if isinstance(products_data, list) else [])
        generator.analyze_products(products)
    
    return generator.generate_report()


def main():
    parser = argparse.ArgumentParser(description="Generate quality alerts for extraction")
    parser.add_argument("--rooms", default="output/rooms_complete.json",
                       help="Path to rooms_complete.json")
    parser.add_argument("--products", default=None,
                       help="Path to products JSON (optional)")
    parser.add_argument("-o", "--output", default="output/alerts.json",
                       help="Output path for alerts JSON")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Print detailed output")
    
    args = parser.parse_args()
    
    rooms_path = Path(args.rooms)
    products_path = Path(args.products) if args.products else None
    output_path = Path(args.output)
    
    # Generate report
    report = analyze_extraction(rooms_path, products_path)
    
    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # Print summary
    summary = report["summary"]
    print("\n" + "="*60)
    print("QUALITY ALERT REPORT")
    print("="*60)
    print(f"Errors:   {summary['total_errors']}")
    print(f"Warnings: {summary['total_warnings']}")
    print(f"Info:     {summary['total_info']}")
    print(f"Output:   {output_path}")
    print("="*60)
    
    if args.verbose:
        print("\nERRORS:")
        for err in report["errors"]:
            print(f"  [{err['type']}] {err['item']}: {err['message']}")
        
        print("\nWARNINGS:")
        for warn in report["warnings"][:10]:  # Limit output
            print(f"  [{warn['type']}] {warn['item']}: {warn['message']}")
        if len(report["warnings"]) > 10:
            print(f"  ... and {len(report['warnings']) - 10} more")
    
    # Return exit code based on errors
    return 1 if summary["total_errors"] > 0 else 0


if __name__ == "__main__":
    exit(main())
