#!/usr/bin/env python3
"""
Tests for validate_gt.py — Ground Truth validation.
"""

import json
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from validate_gt import (
    validate_against_ground_truth,
    validate_room_types,
    compare_room,
    compare_product,
    normalize_string,
    infer_room_type,
    _fuzzy_name_match,
    GTReport,
    GTMatch,
    GTMismatch,
)


# ============== Fixtures ==============

@pytest.fixture
def gt_data():
    return {
        "verified_rooms": [
            {"id": "A-101", "name": "CLASSE", "floor": 1, "block": "A", "type": "CLASSE"},
            {"id": "A-102", "name": "CORRIDOR", "floor": 1, "block": "A", "type": "CORRIDOR"},
            {"id": "A-103", "name": "WC GARÇONS", "floor": 1, "block": "A", "type": "WC"},
            {"id": "B-201", "name": "GYMNASE", "floor": 2, "block": "B", "type": "GYMNASE"},
        ],
        "verified_products": [
            {"section": "09 91 00", "category": "Peinture", "product": "ProMar 200", "type": "latex"},
        ],
        "room_type_distribution": {
            "CLASSE": 1,
            "CORRIDOR": 1,
            "WC": 1,
            "GYMNASE": 1,
        },
    }


@pytest.fixture
def extracted_perfect(gt_data):
    """Extracted data matching GT perfectly."""
    return {
        "rooms": [dict(r) for r in gt_data["verified_rooms"]],
        "products": [
            {"section": "09 91 00", "category": "Peinture", "product": "ProMar 200", "type": "latex"},
        ],
    }


@pytest.fixture
def extracted_partial():
    """Extracted data with partial matches."""
    return {
        "rooms": [
            {"id": "A-101", "name": "CLASSE", "floor": 1, "block": "A", "type": "CLASSE"},
            {"id": "A-102", "name": "CORRIDOR PRINCIPAL", "floor": 1, "block": "A", "type": "CORRIDOR"},
            # A-103 missing
            {"id": "B-201", "name": "GYMNASE", "floor": 2, "block": "B", "type": "AUTRE"},
            {"id": "C-100", "name": "EXTRA", "floor": 0, "block": "C"},  # Extra room
        ]
    }


# ============== normalize_string ==============

class TestNormalizeString:
    def test_basic(self):
        assert normalize_string("hello") == "HELLO"

    def test_strip(self):
        assert normalize_string("  hello  ") == "HELLO"

    def test_separators(self):
        assert normalize_string("hello-world_test") == "HELLO WORLD TEST"

    def test_empty(self):
        assert normalize_string("") == ""

    def test_none(self):
        assert normalize_string(None) == ""

    def test_already_normalized(self):
        assert normalize_string("HELLO") == "HELLO"


# ============== infer_room_type ==============

class TestInferRoomType:
    def test_classe(self):
        assert infer_room_type("CLASSE") == "CLASSE"
        assert infer_room_type("MATERNELLE") == "CLASSE"

    def test_wc(self):
        assert infer_room_type("WC") == "WC"
        assert infer_room_type("TOILETTE") == "WC"
        assert infer_room_type("S.D.B.") == "WC"
        assert infer_room_type("SALLE DE BAIN") == "WC"

    def test_corridor(self):
        assert infer_room_type("CORRIDOR") == "CORRIDOR"

    def test_gymnase(self):
        assert infer_room_type("GYMNASE") == "GYMNASE"

    def test_rangement(self):
        assert infer_room_type("RANGEMENT") == "RANGEMENT"
        assert infer_room_type("REMISE") == "RANGEMENT"
        assert infer_room_type("DÉPÔT") == "RANGEMENT"
        assert infer_room_type("ENTREPOSAGE") == "RANGEMENT"

    def test_vestiaire(self):
        assert infer_room_type("VESTIAIRE") == "VESTIAIRE"

    def test_technique(self):
        assert infer_room_type("ÉLECTRIQUE") == "TECHNIQUE"
        assert infer_room_type("MÉCANIQUE") == "TECHNIQUE"
        assert infer_room_type("CHAUFFERIE") == "TECHNIQUE"
        assert infer_room_type("TECHNIQUE") == "TECHNIQUE"

    def test_service(self):
        assert infer_room_type("CONCIERGERIE") == "SERVICE"
        assert infer_room_type("SERVICE DE GARDE") == "SERVICE"

    def test_circulation(self):
        assert infer_room_type("ESCALIER") == "CIRCULATION"
        assert infer_room_type("VESTIBULE") == "CIRCULATION"

    def test_bureau(self):
        assert infer_room_type("BUREAU") == "BUREAU"
        assert infer_room_type("SECRÉTARIAT") == "BUREAU"
        assert infer_room_type("DIRECTION") == "BUREAU"

    def test_empty(self):
        assert infer_room_type("") == ""

    def test_unknown(self):
        assert infer_room_type("LOCAL BIZARRE") == "AUTRE"


# ============== _fuzzy_name_match ==============

class TestFuzzyNameMatch:
    def test_wc_synonyms(self):
        assert _fuzzy_name_match("WC", "TOILETTES")
        assert _fuzzy_name_match("TOILETTE", "WC")

    def test_rangement_synonyms(self):
        assert _fuzzy_name_match("RANGEMENT", "REMISE")
        assert _fuzzy_name_match("DÉPÔT", "ENTREPOSAGE")

    def test_technique_synonyms(self):
        assert _fuzzy_name_match("TECHNIQUE", "LOCAL TECHNIQUE")

    def test_no_match(self):
        assert not _fuzzy_name_match("CLASSE", "CORRIDOR")
        assert not _fuzzy_name_match("GYMNASE", "WC")

    def test_same_value(self):
        assert _fuzzy_name_match("WC", "WC")


# ============== compare_room ==============

class TestCompareRoom:
    def test_perfect_match(self):
        room = {"id": "A-101", "name": "CLASSE", "block": "A", "floor": 1, "type": "CLASSE"}
        gt = {"id": "A-101", "name": "CLASSE", "block": "A", "floor": 1, "type": "CLASSE"}
        score, matched, mismatched = compare_room(room, gt)
        assert score == 1.0
        assert len(mismatched) == 0
        assert "id" in matched
        assert "name" in matched

    def test_case_insensitive(self):
        room = {"id": "A-101", "name": "classe", "block": "a", "floor": 1}
        gt = {"id": "A-101", "name": "CLASSE", "block": "A", "floor": 1}
        score, matched, mismatched = compare_room(room, gt)
        assert "name" in matched
        assert "block" in matched

    def test_partial_name_match(self):
        room = {"id": "A-102", "name": "CORRIDOR PRINCIPAL", "block": "A", "floor": 1}
        gt = {"id": "A-102", "name": "CORRIDOR", "block": "A", "floor": 1}
        score, matched, mismatched = compare_room(room, gt)
        assert "name" in matched  # Partial name match

    def test_type_inferred_from_name(self):
        """When type is missing, it should be inferred from name."""
        room = {"id": "A-101", "name": "CLASSE", "block": "A", "floor": 1}
        gt = {"id": "A-101", "name": "CLASSE", "block": "A", "floor": 1, "type": "CLASSE"}
        score, matched, mismatched = compare_room(room, gt)
        assert "type" in matched

    def test_mismatch_details(self):
        room = {"id": "A-101", "name": "CLASSE", "block": "A", "floor": 2, "type": "CLASSE"}
        gt = {"id": "A-101", "name": "CLASSE", "block": "A", "floor": 1, "type": "CLASSE"}
        score, matched, mismatched = compare_room(room, gt)
        assert any(m["field"] == "floor" for m in mismatched)
        assert score < 1.0

    def test_empty_fields(self):
        room = {"id": "A-101"}
        gt = {"id": "A-101"}
        score, matched, mismatched = compare_room(room, gt)
        assert "id" in matched

    def test_synonym_names(self):
        """Fuzzy name matching for synonyms."""
        room = {"id": "A-103", "name": "TOILETTES"}
        gt = {"id": "A-103", "name": "WC"}
        score, matched, mismatched = compare_room(room, gt)
        # Should match via fuzzy synonyms
        assert "name" in matched


# ============== compare_product ==============

class TestCompareProduct:
    def test_perfect_match(self):
        ext = {"section": "09 91 00", "category": "Peinture", "product": "ProMar 200", "type": "latex"}
        gt = {"section": "09 91 00", "category": "Peinture", "product": "ProMar 200", "type": "latex"}
        score, matched, mismatched = compare_product(ext, gt)
        assert score == 1.0

    def test_partial_match(self):
        ext = {"section": "09 91 00", "category": "Peinture", "product": "ProMar 200 Interior", "type": "latex"}
        gt = {"section": "09 91 00", "category": "Peinture", "product": "ProMar 200", "type": "latex"}
        score, matched, mismatched = compare_product(ext, gt)
        assert score > 0.5  # partial product name match

    def test_no_match(self):
        ext = {"section": "09 65 00", "category": "Sol", "product": "Armstrong VCT", "type": "vinyle"}
        gt = {"section": "09 91 00", "category": "Peinture", "product": "ProMar 200", "type": "latex"}
        score, matched, mismatched = compare_product(ext, gt)
        assert score < 0.5

    def test_empty_fields(self):
        ext = {"section": "09 91 00"}
        gt = {"section": "09 91 00"}
        score, matched, mismatched = compare_product(ext, gt)
        assert "section" in matched


# ============== validate_against_ground_truth ==============

class TestValidateAgainstGroundTruth:
    def test_perfect_extraction(self, extracted_perfect, gt_data):
        report = validate_against_ground_truth(extracted_perfect, gt_data)
        assert isinstance(report, GTReport)
        assert report.metrics["recall"] == 1.0
        assert len(report.missing_in_extraction) == 0

    def test_partial_extraction(self, extracted_partial, gt_data):
        report = validate_against_ground_truth(extracted_partial, gt_data)
        assert report.metrics["recall"] < 1.0
        assert len(report.missing_in_extraction) > 0  # A-103 missing
        assert "A-103" in report.missing_in_extraction

    def test_extra_rooms(self, extracted_partial, gt_data):
        report = validate_against_ground_truth(extracted_partial, gt_data)
        assert len(report.extra_in_extraction) > 0  # C-100 extra
        assert "C-100" in report.extra_in_extraction

    def test_metrics_computed(self, extracted_perfect, gt_data):
        report = validate_against_ground_truth(extracted_perfect, gt_data)
        m = report.metrics
        assert "accuracy" in m
        assert "precision" in m
        assert "recall" in m
        assert "f1" in m
        assert "ground_truth_count" in m
        assert "extracted_count" in m
        assert "perfect_matches" in m
        assert "partial_matches" in m

    def test_f1_score(self, extracted_perfect, gt_data):
        report = validate_against_ground_truth(extracted_perfect, gt_data)
        f1 = report.metrics["f1"]
        assert 0 <= f1 <= 1.0

    def test_empty_extraction(self, gt_data):
        report = validate_against_ground_truth({"rooms": []}, gt_data)
        assert report.metrics["recall"] == 0
        assert report.metrics["precision"] == 0
        assert len(report.missing_in_extraction) == 4

    def test_empty_gt(self):
        report = validate_against_ground_truth(
            {"rooms": [{"id": "A-101", "name": "CLASSE"}]},
            {"verified_rooms": []},
        )
        assert report.metrics["ground_truth_count"] == 0
        assert len(report.extra_in_extraction) == 1

    def test_product_validation(self, extracted_perfect, gt_data):
        report = validate_against_ground_truth(extracted_perfect, gt_data)
        product_matches = [m for m in report.matches if m.item_type == "product"]
        assert len(product_matches) > 0

    def test_report_to_dict(self, extracted_perfect, gt_data):
        report = validate_against_ground_truth(extracted_perfect, gt_data)
        d = report.to_dict()
        assert "matches" in d
        assert "mismatches" in d
        assert "missing_in_extraction" in d
        assert "extra_in_extraction" in d
        assert "metrics" in d

    def test_report_summary(self, extracted_perfect, gt_data):
        report = validate_against_ground_truth(extracted_perfect, gt_data)
        summary = report.summary()
        assert "Ground Truth" in summary
        assert "Accuracy" in summary
        assert "F1 Score" in summary

    def test_mismatches_recorded(self, extracted_partial, gt_data):
        report = validate_against_ground_truth(extracted_partial, gt_data)
        # B-201 has type AUTRE vs GYMNASE → mismatch
        type_mismatches = [m for m in report.mismatches if m.field == "type"]
        assert len(type_mismatches) > 0


# ============== validate_room_types ==============

class TestValidateRoomTypes:
    def test_distribution_match(self, gt_data):
        rooms = {"rooms": gt_data["verified_rooms"]}
        comp = validate_room_types(rooms, gt_data)
        assert "CLASSE" in comp
        assert comp["CLASSE"]["match"] is True

    def test_detects_difference(self, gt_data):
        rooms = {
            "rooms": [
                {"id": "A-101", "name": "CLASSE"},
                {"id": "A-102", "name": "CLASSE"},  # Extra
            ]
        }
        comp = validate_room_types(rooms, gt_data)
        assert comp["CLASSE"]["difference"] != 0

    def test_empty_rooms(self, gt_data):
        comp = validate_room_types({"rooms": []}, gt_data)
        for room_type, data in comp.items():
            assert data["extracted"] == 0

    def test_all_types_covered(self, gt_data):
        rooms = {"rooms": gt_data["verified_rooms"]}
        comp = validate_room_types(rooms, gt_data)
        all_types = set(gt_data["room_type_distribution"].keys())
        assert all_types.issubset(set(comp.keys()))


# ============== Data classes ==============

class TestGTDataClasses:
    def test_gt_match(self):
        m = GTMatch(
            item_id="A-101",
            item_type="room",
            extracted_value={"id": "A-101"},
            ground_truth_value={"id": "A-101"},
            fields_matched=["id", "name"],
            fields_mismatched=[],
            score=1.0,
        )
        assert m.score == 1.0

    def test_gt_mismatch(self):
        m = GTMismatch(
            item_id="A-101",
            item_type="room",
            field="type",
            extracted_value="AUTRE",
            expected_value="CLASSE",
            severity="critical",
        )
        assert m.severity == "critical"

    def test_gt_report_empty(self):
        r = GTReport()
        assert r.matches == []
        assert r.mismatches == []
        assert r.metrics == {}

    def test_gt_report_summary_with_mismatches(self):
        r = GTReport(
            mismatches=[
                GTMismatch("A-101", "room", "type", "AUTRE", "CLASSE", "critical")
            ],
            missing_in_extraction=["B-201"],
            metrics={
                "accuracy": 0.8,
                "precision": 0.9,
                "recall": 0.75,
                "f1": 0.82,
                "ground_truth_count": 4,
                "extracted_count": 3,
                "perfect_matches": 2,
                "partial_matches": 1,
                "missing": 1,
            },
        )
        summary = r.summary()
        assert "Principales différences" in summary
        assert "Manquants dans l'extraction" in summary
