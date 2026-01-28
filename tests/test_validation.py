#!/usr/bin/env python3
"""
Tests pour les modules de validation.
"""

import json
import pytest
import sys
from pathlib import Path

# Ajouter scripts au path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from cross_validate import (
    cross_validate,
    normalize_room_name,
    extract_room_type,
    find_room_in_devis,
    ValidationReport,
    Match,
    Mismatch,
    Missing
)

from validate_gt import (
    validate_against_ground_truth,
    validate_room_types,
    compare_room,
    compare_product,
    normalize_string,
    GTReport
)


# ============== Fixtures ==============

@pytest.fixture
def sample_rooms():
    """Données de locaux pour tests."""
    return {
        "project": {"name": "Test Project"},
        "rooms": [
            {"id": "A-101", "name": "CLASSE", "floor": 1, "block": "A"},
            {"id": "A-102", "name": "CORRIDOR", "floor": 1, "block": "A"},
            {"id": "A-103", "name": "WC GARÇONS", "floor": 1, "block": "A"},
            {"id": "B-101", "name": "GYMNASE", "floor": 1, "block": "B"},
            {"id": "B-102", "name": "VESTIAIRE", "floor": 1, "block": "B"},
        ]
    }


@pytest.fixture
def sample_devis():
    """Données de devis pour tests."""
    return {
        "sections": [
            {
                "title": "Section 09 91 00 - Peinture",
                "content": "Local A-101: peinture latex ProMar 200\nLocal A-102: finition standard",
                "csi_code": "09 91 00",
                "page_num": 150,
                "subsections": []
            },
            {
                "title": "Section 09 65 00 - Revêtements sols",
                "content": "CLASSE: VCT Armstrong\nCORRIDOR: vinyle",
                "csi_code": "09 65 00",
                "page_num": 180,
                "subsections": []
            }
        ]
    }


@pytest.fixture
def sample_ground_truth():
    """Ground truth pour tests."""
    return {
        "project": "Test Project",
        "verified_rooms": [
            {"id": "A-101", "name": "CLASSE", "floor": 1, "block": "A", "type": "CLASSE"},
            {"id": "A-102", "name": "CORRIDOR", "floor": 1, "block": "A", "type": "CORRIDOR"},
            {"id": "A-103", "name": "WC GARÇONS", "floor": 1, "block": "A", "type": "WC"},
        ],
        "verified_products": [
            {"section": "09 91 00", "category": "Peinture", "product": "ProMar 200"}
        ],
        "room_type_distribution": {
            "CLASSE": 1,
            "CORRIDOR": 1,
            "WC": 1,
            "GYMNASE": 1
        }
    }


# ============== Tests normalize_room_name ==============

class TestNormalizeRoomName:
    def test_basic_normalization(self):
        assert normalize_room_name("classe") == "CLASSE"
        assert normalize_room_name("  CORRIDOR  ") == "CORRIDOR"
    
    def test_replacements(self):
        assert "WC" in normalize_room_name("TOILETTES")
        assert "WC" in normalize_room_name("W.C.")
        assert "RANGEMENT" in normalize_room_name("REMISE")
    
    def test_complex_names(self):
        result = normalize_room_name("Salle de classe")
        assert "CLASSE" in result


# ============== Tests extract_room_type ==============

class TestExtractRoomType:
    def test_classe(self):
        assert extract_room_type("CLASSE") == "CLASSE"
        assert extract_room_type("Salle de classe") == "CLASSE"
    
    def test_wc(self):
        assert extract_room_type("WC GARÇONS") == "WC"
        assert extract_room_type("TOILETTES") == "WC"
    
    def test_corridor(self):
        assert extract_room_type("CORRIDOR") == "CORRIDOR"
    
    def test_gymnase(self):
        assert extract_room_type("GYMNASE") == "GYMNASE"
    
    def test_technique(self):
        assert extract_room_type("ÉLECTRIQUE") == "TECHNIQUE"
        assert extract_room_type("CHAUFFERIE") == "TECHNIQUE"
    
    def test_unknown(self):
        assert extract_room_type("LOCAL SPÉCIAL XYZ") == "AUTRE"


# ============== Tests cross_validate ==============

class TestCrossValidate:
    def test_basic_validation(self, sample_rooms, sample_devis):
        report = cross_validate(sample_rooms, sample_devis)
        
        assert isinstance(report, ValidationReport)
        assert len(report.matches) > 0
        assert "total_rooms" in report.stats
        assert report.stats["total_rooms"] == 5
    
    def test_finds_matches(self, sample_rooms, sample_devis):
        report = cross_validate(sample_rooms, sample_devis)
        
        # A-101 devrait être trouvé (mentionné directement)
        a101_matches = [m for m in report.matches if m.room_id == "A-101"]
        assert len(a101_matches) > 0
    
    def test_report_to_dict(self, sample_rooms, sample_devis):
        report = cross_validate(sample_rooms, sample_devis)
        result = report.to_dict()
        
        assert "matches" in result
        assert "mismatches" in result
        assert "missing" in result
        assert "stats" in result
    
    def test_summary_output(self, sample_rooms, sample_devis):
        report = cross_validate(sample_rooms, sample_devis)
        summary = report.summary()
        
        assert "Rapport de Cross-Validation" in summary
        assert "Matches:" in summary


# ============== Tests find_room_in_devis ==============

class TestFindRoomInDevis:
    def test_direct_id_match(self, sample_devis):
        matches = find_room_in_devis("A-101", "CLASSE", sample_devis)
        assert len(matches) > 0
        assert any(m["match_type"] == "direct" for m in matches)
    
    def test_name_match(self, sample_devis):
        matches = find_room_in_devis("X-999", "CLASSE", sample_devis)
        assert len(matches) > 0
        assert any(m["match_type"] == "name" for m in matches)
    
    def test_no_match(self, sample_devis):
        matches = find_room_in_devis("Z-999", "INEXISTANT", sample_devis)
        assert len(matches) == 0


# ============== Tests validate_against_ground_truth ==============

class TestValidateAgainstGroundTruth:
    def test_basic_validation(self, sample_rooms, sample_ground_truth):
        report = validate_against_ground_truth(sample_rooms, sample_ground_truth)
        
        assert isinstance(report, GTReport)
        assert "accuracy" in report.metrics
        assert "precision" in report.metrics
        assert "recall" in report.metrics
        assert "f1" in report.metrics
    
    def test_perfect_match(self, sample_ground_truth):
        # Créer des données qui correspondent parfaitement au GT
        perfect_rooms = {
            "rooms": sample_ground_truth["verified_rooms"].copy()
        }
        
        report = validate_against_ground_truth(perfect_rooms, sample_ground_truth)
        
        assert report.metrics["recall"] == 1.0
        assert len(report.missing_in_extraction) == 0
    
    def test_missing_detection(self, sample_ground_truth):
        # Données avec locaux manquants
        incomplete_rooms = {
            "rooms": [
                {"id": "A-101", "name": "CLASSE", "floor": 1, "block": "A"}
            ]
        }
        
        report = validate_against_ground_truth(incomplete_rooms, sample_ground_truth)
        
        assert len(report.missing_in_extraction) > 0
        assert report.metrics["recall"] < 1.0
    
    def test_report_summary(self, sample_rooms, sample_ground_truth):
        report = validate_against_ground_truth(sample_rooms, sample_ground_truth)
        summary = report.summary()
        
        assert "Ground Truth" in summary
        assert "Accuracy:" in summary
        assert "F1 Score:" in summary


# ============== Tests compare_room ==============

class TestCompareRoom:
    def test_perfect_match(self):
        extracted = {"id": "A-101", "name": "CLASSE", "block": "A", "floor": 1, "type": "CLASSE"}
        ground_truth = {"id": "A-101", "name": "CLASSE", "block": "A", "floor": 1, "type": "CLASSE"}
        
        score, matched, mismatched = compare_room(extracted, ground_truth)
        
        assert score == 1.0
        assert len(mismatched) == 0
    
    def test_partial_match(self):
        extracted = {"id": "A-101", "name": "CLASSE", "block": "A", "floor": 1, "type": "AUTRE"}
        ground_truth = {"id": "A-101", "name": "CLASSE", "block": "A", "floor": 1, "type": "CLASSE"}
        
        score, matched, mismatched = compare_room(extracted, ground_truth)
        
        assert 0 < score < 1.0
        assert len(mismatched) > 0
        assert any(m["field"] == "type" for m in mismatched)
    
    def test_name_normalization(self):
        extracted = {"id": "A-101", "name": "classe", "block": "a", "floor": 1}
        ground_truth = {"id": "A-101", "name": "CLASSE", "block": "A", "floor": 1}
        
        score, matched, mismatched = compare_room(extracted, ground_truth)
        
        # Devrait matcher malgré la casse différente
        assert "name" in matched or score > 0.5


# ============== Tests validate_room_types ==============

class TestValidateRoomTypes:
    def test_distribution_match(self, sample_rooms, sample_ground_truth):
        comparison = validate_room_types(sample_rooms, sample_ground_truth)
        
        assert "CLASSE" in comparison
        assert "extracted" in comparison["CLASSE"]
        assert "ground_truth" in comparison["CLASSE"]
    
    def test_detects_differences(self, sample_ground_truth):
        # Rooms avec distribution différente
        rooms = {
            "rooms": [
                {"id": "A-101", "name": "CLASSE", "floor": 1, "block": "A"},
                {"id": "A-102", "name": "CLASSE", "floor": 1, "block": "A"},  # 2 classes au lieu de 1
            ]
        }
        
        comparison = validate_room_types(rooms, sample_ground_truth)
        
        assert comparison["CLASSE"]["difference"] != 0


# ============== Tests normalize_string ==============

class TestNormalizeString:
    def test_uppercase(self):
        assert normalize_string("hello") == "HELLO"
    
    def test_strips(self):
        assert normalize_string("  hello  ") == "HELLO"
    
    def test_replaces_separators(self):
        assert normalize_string("hello-world_test") == "HELLO WORLD TEST"
    
    def test_empty(self):
        assert normalize_string("") == ""
        assert normalize_string(None) == ""


# ============== Tests d'intégration ==============

class TestIntegration:
    def test_full_validation_workflow(self, sample_rooms, sample_devis, sample_ground_truth):
        """Test du workflow complet de validation."""
        # 1. Cross-validation
        cross_report = cross_validate(sample_rooms, sample_devis)
        assert cross_report.stats["total_rooms"] == len(sample_rooms["rooms"])
        
        # 2. Validation GT
        gt_report = validate_against_ground_truth(sample_rooms, sample_ground_truth)
        assert gt_report.metrics["f1"] >= 0  # F1 doit être calculé
        
        # 3. Distribution des types
        type_dist = validate_room_types(sample_rooms, sample_ground_truth)
        assert len(type_dist) > 0


# ============== Tests avec données réelles ==============

@pytest.fixture
def real_data_paths():
    """Chemins vers les données réelles du projet EMJ."""
    base = Path(__file__).parent.parent
    return {
        "rooms": base / "output" / "rooms_complete.json",
        "devis": base / "output" / "devis_final.json",
        "ground_truth": base / "ground_truth" / "emj.json"
    }


class TestWithRealData:
    def test_real_rooms_validation(self, real_data_paths):
        """Test avec les vraies données du projet EMJ."""
        rooms_path = real_data_paths["rooms"]
        gt_path = real_data_paths["ground_truth"]
        
        if not rooms_path.exists() or not gt_path.exists():
            pytest.skip("Données réelles non disponibles")
        
        with open(rooms_path) as f:
            rooms = json.load(f)
        with open(gt_path) as f:
            gt = json.load(f)
        
        report = validate_against_ground_truth(rooms, gt)
        
        # Le recall devrait être élevé (tous les GT trouvés)
        assert report.metrics["recall"] >= 0.8
        
        # L'accuracy devrait être acceptable
        assert report.metrics["accuracy"] >= 0.7
    
    def test_real_cross_validation(self, real_data_paths):
        """Test de cross-validation avec données réelles."""
        rooms_path = real_data_paths["rooms"]
        devis_path = real_data_paths["devis"]
        
        if not rooms_path.exists() or not devis_path.exists():
            pytest.skip("Données réelles non disponibles")
        
        with open(rooms_path) as f:
            rooms = json.load(f)
        with open(devis_path) as f:
            devis = json.load(f)
        
        report = cross_validate(rooms, devis)
        
        # Devrait avoir des matches
        assert len(report.matches) > 0
        
        # Le taux de match devrait être raisonnable
        assert report.stats["match_rate"] >= 0.3
