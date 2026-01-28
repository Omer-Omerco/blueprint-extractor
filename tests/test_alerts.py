"""
Tests for the alerts.py quality alert system.
"""

import json
import pytest
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from alerts import AlertGenerator, analyze_extraction, CONFIDENCE_WARNING_THRESHOLD


class TestAlertGenerator:
    """Test AlertGenerator class."""
    
    def test_add_warning(self):
        """Test adding a warning alert."""
        gen = AlertGenerator()
        gen.add_warning("LOW_CONFIDENCE", "A-101", "Test warning", confidence=0.5)
        
        assert len(gen.warnings) == 1
        assert gen.warnings[0].type == "LOW_CONFIDENCE"
        assert gen.warnings[0].item == "A-101"
        assert gen.warnings[0].severity == "WARNING"
        assert gen.warnings[0].details["confidence"] == 0.5
    
    def test_add_error(self):
        """Test adding an error alert."""
        gen = AlertGenerator()
        gen.add_error("MISSING_DIMENSION", "B-101", "Test error")
        
        assert len(gen.errors) == 1
        assert gen.errors[0].type == "MISSING_DIMENSION"
        assert gen.errors[0].severity == "ERROR"
    
    def test_add_info(self):
        """Test adding an info alert."""
        gen = AlertGenerator()
        gen.add_info("EXTRACTION_SUMMARY", "GLOBAL", "Test info", total=10)
        
        assert len(gen.info) == 1
        assert gen.info[0].type == "EXTRACTION_SUMMARY"
        assert gen.info[0].severity == "INFO"


class TestAnalyzeRooms:
    """Test room analysis."""
    
    @pytest.fixture
    def sample_rooms_data(self):
        """Sample rooms data for testing."""
        return {
            "rooms": [
                {"id": "A-101", "name": "CLASSE", "confidence": 0.95, "source_pages": [4, 9, 30]},
                {"id": "A-102", "name": "CORRIDOR", "confidence": 0.65, "source_pages": [4]},
                {"id": "A-103", "name": "LOCAL", "confidence": 0.35, "source_pages": []},
                {"id": "A-104", "name": "TOILETTE", "confidence": 0.80, "source_pages": [9, 30]},
            ]
        }
    
    def test_analyze_rooms_generates_alerts(self, sample_rooms_data):
        """Test that room analysis generates appropriate alerts."""
        gen = AlertGenerator()
        gen.analyze_rooms(sample_rooms_data)
        
        # Should have warnings for low confidence and generic name
        assert len(gen.warnings) >= 2
        
        # Should have errors for very low confidence and no source pages
        assert len(gen.errors) >= 2
        
        # Should have info summary
        assert len(gen.info) >= 1
    
    def test_low_confidence_warning(self, sample_rooms_data):
        """Test that low confidence triggers warning."""
        gen = AlertGenerator()
        gen.analyze_rooms(sample_rooms_data)
        
        warning_types = [w.type for w in gen.warnings]
        assert "LOW_CONFIDENCE" in warning_types
    
    def test_no_source_pages_error(self, sample_rooms_data):
        """Test that missing source pages triggers error."""
        gen = AlertGenerator()
        gen.analyze_rooms(sample_rooms_data)
        
        error_types = [e.type for e in gen.errors]
        assert "NO_SOURCE_PAGES" in error_types
    
    def test_stats_calculation(self, sample_rooms_data):
        """Test statistics calculation."""
        gen = AlertGenerator()
        gen.analyze_rooms(sample_rooms_data)
        
        assert gen.stats["total_rooms"] == 4
        assert gen.stats["rooms_with_confidence"] == 4
        assert 0 < gen.stats["average_confidence"] < 1


class TestGenerateReport:
    """Test report generation."""
    
    def test_generate_report_structure(self):
        """Test that report has correct structure."""
        gen = AlertGenerator()
        gen.add_warning("TEST", "item", "message")
        gen.add_error("TEST", "item", "message")
        gen.add_info("TEST", "item", "message")
        
        report = gen.generate_report()
        
        assert "generated_at" in report
        assert "warnings" in report
        assert "errors" in report
        assert "info" in report
        assert "summary" in report
        
        assert report["summary"]["total_warnings"] == 1
        assert report["summary"]["total_errors"] == 1
        assert report["summary"]["total_info"] == 1


class TestAnalyzeExtraction:
    """Test full extraction analysis."""
    
    def test_analyze_missing_file(self, tmp_path):
        """Test handling of missing file."""
        report = analyze_extraction(tmp_path / "nonexistent.json")
        
        assert report["summary"]["total_errors"] >= 1
    
    def test_analyze_valid_file(self, tmp_path):
        """Test analysis of valid file."""
        rooms_file = tmp_path / "rooms.json"
        rooms_data = {
            "rooms": [
                {"id": "A-101", "name": "CLASSE", "confidence": 0.9, "source_pages": [1, 2]},
                {"id": "A-102", "name": "BUREAU", "confidence": 0.85, "source_pages": [1]},
            ]
        }
        
        with open(rooms_file, "w") as f:
            json.dump(rooms_data, f)
        
        report = analyze_extraction(rooms_file)
        
        assert "warnings" in report
        assert "errors" in report
        assert report["summary"]["stats"]["total_rooms"] == 2


class TestProductAnalysis:
    """Test product analysis."""
    
    def test_analyze_products_with_confidence(self, tmp_path):
        """Test product analysis with confidence scores."""
        products_file = tmp_path / "products.json"
        products_data = {
            "products": [
                {"manufacturer": "Sherwin-Williams", "model": "ProMar 200", "confidence": 0.95},
                {"manufacturer": "Unknown", "model": "Generic", "confidence": 0.45},
            ]
        }
        
        with open(products_file, "w") as f:
            json.dump(products_data, f)
        
        rooms_file = tmp_path / "rooms.json"
        with open(rooms_file, "w") as f:
            json.dump({"rooms": []}, f)
        
        report = analyze_extraction(rooms_file, products_file)
        
        # Should have warning for low confidence product
        product_warnings = [w for w in report["warnings"] if "PRODUCT" in w["type"]]
        assert len(product_warnings) >= 1
