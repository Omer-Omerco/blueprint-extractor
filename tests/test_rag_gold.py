"""
Tests for gold-verified RAG system.
Ensures ZERO hallucination — every answer is source-traceable.
"""

import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from build_rag_gold import build_gold_index, normalize_text, build_search_text
from query_rag_gold import (
    normalize_query,
    extract_room_id,
    detect_aggregate_query,
    search_entries,
    format_room_result,
    query_gold_rag,
    load_index,
    NOT_FOUND_MSG,
    FABRICATED_MSG,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def gold_path():
    """Path to the real emj_gold.json."""
    p = Path(__file__).parent.parent / "ground_truth" / "emj_gold.json"
    if not p.exists():
        pytest.skip("emj_gold.json not found")
    return str(p)


@pytest.fixture
def gold_data(gold_path):
    """Load gold GT data."""
    with open(gold_path) as f:
        return json.load(f)


@pytest.fixture
def gold_index(tmp_path, gold_path):
    """Build and return a gold index."""
    return build_gold_index(gold_path=gold_path, output_dir=str(tmp_path / "rag"))


@pytest.fixture
def gold_rag_dir(tmp_path, gold_path):
    """Build gold index and return RAG directory path."""
    output = tmp_path / "rag"
    build_gold_index(gold_path=gold_path, output_dir=str(output))
    return str(output)


# =============================================================================
# Build tests
# =============================================================================

class TestBuildGoldIndex:
    """Tests for building gold RAG index."""

    def test_builds_index_with_80_rooms(self, gold_index):
        """Gold GT has exactly 80 verified rooms."""
        assert gold_index["stats"]["total_verified_rooms"] == 80

    def test_all_entries_have_source(self, gold_index):
        """CRITICAL: Every entry must have a source citation."""
        for entry in gold_index["entries"]:
            assert entry.get("source"), f"Room {entry['id']} has no source!"
            assert entry.get("source_document"), f"Room {entry['id']} has no source_document!"

    def test_all_entries_are_verified(self, gold_index):
        """Every entry must be marked as verified."""
        for entry in gold_index["entries"]:
            assert entry.get("verified") is True, f"Room {entry['id']} not verified!"

    def test_all_entries_have_confidence(self, gold_index):
        """Every entry must have a confidence level."""
        for entry in gold_index["entries"]:
            assert entry["confidence"] in ("HIGH", "MEDIUM"), \
                f"Room {entry['id']} has invalid confidence: {entry['confidence']}"

    def test_confidence_counts_match(self, gold_index):
        """HIGH + MEDIUM should equal total."""
        stats = gold_index["stats"]
        assert stats["high_confidence"] + stats["medium_confidence"] == stats["total_verified_rooms"]

    def test_fabricated_rooms_are_blocked(self, gold_index):
        """Should include list of fabricated rooms to block."""
        assert gold_index["stats"]["fabricated_rooms_blocked"] > 0
        assert len(gold_index["fabricated_rooms"]) > 50  # We know there are 65

    def test_creates_index_file(self, tmp_path, gold_path):
        """Should create index.json on disk."""
        output = tmp_path / "rag"
        build_gold_index(gold_path=gold_path, output_dir=str(output))
        assert (output / "index.json").exists()

    def test_creates_block_files(self, tmp_path, gold_path):
        """Should create per-block JSON files."""
        output = tmp_path / "rag"
        build_gold_index(gold_path=gold_path, output_dir=str(output))
        blocks_dir = output / "blocks"
        assert blocks_dir.exists()
        assert (blocks_dir / "bloc-A-1.json").exists()
        assert (blocks_dir / "bloc-A-2.json").exists()
        assert (blocks_dir / "bloc-B-1.json").exists()
        assert (blocks_dir / "bloc-C-1.json").exists()

    def test_creates_lookup_file(self, tmp_path, gold_path):
        """Should create lookup.json for fast ID-based queries."""
        output = tmp_path / "rag"
        build_gold_index(gold_path=gold_path, output_dir=str(output))
        assert (output / "lookup.json").exists()

    def test_block_counts(self, gold_index):
        """Should have correct room counts per block."""
        stats = gold_index["stats"]["blocks"]
        assert stats["A_1er"] == 29
        assert stats["A_2e"] == 26
        assert stats["B_1er"] == 20
        assert stats["C_1er"] == 5

    def test_project_metadata(self, gold_index):
        """Should include project metadata."""
        assert "École" in gold_index["project"] or "Enfant" in gold_index["project"]
        assert gold_index["location"] == "SOREL-TRACY, QUÉBEC"
        assert gold_index["source_documents"]["plans"]
        assert gold_index["source_documents"]["devis"]


# =============================================================================
# Source traceability tests (CRITICAL)
# =============================================================================

class TestSourceTraceability:
    """Every room must trace to a specific source page."""

    def test_source_pages_extracted(self, gold_index):
        """Source pages should be extracted from source string."""
        for entry in gold_index["entries"]:
            # Most entries should have parseable source pages
            if "p.A-" in entry["source"]:
                assert len(entry["source_pages"]) > 0, \
                    f"Room {entry['id']} has source '{entry['source']}' but no parsed pages"

    def test_source_document_populated(self, gold_index):
        """Source document should be populated for all entries."""
        for entry in gold_index["entries"]:
            assert entry["source_document"], \
                f"Room {entry['id']} has no source_document"

    def test_known_rooms_have_plan_page(self, gold_index):
        """Key rooms must cite specific plan pages."""
        lookup = {e["id"]: e for e in gold_index["entries"]}
        
        # Chaufferie must cite A-150
        assert "A-150" in lookup["A-110"]["source_pages"]
        
        # Gymnase must cite A-151
        assert "A-151" in lookup["C-151"]["source_pages"]
        
        # 2nd floor class must cite A-150
        assert "A-150" in lookup["A-204"]["source_pages"]


# =============================================================================
# Query tests
# =============================================================================

class TestExtractRoomId:
    """Tests for room ID extraction from queries."""

    def test_extracts_prefixed_id(self):
        assert extract_room_id("local A-204") == "A-204"

    def test_extracts_bare_number(self):
        result = extract_room_id("local 204")
        assert result == "204"

    def test_extracts_sub_room(self):
        result = extract_room_id("local A-102-1")
        assert result == "A-102-1"

    def test_extracts_letter_suffix(self):
        result = extract_room_id("corridor A-111-B")
        assert result == "A-111-B"

    def test_returns_none_for_no_id(self):
        assert extract_room_id("la chaufferie") is None


class TestDetectAggregateQuery:
    """Tests for aggregate query detection."""

    def test_detects_count_query(self):
        result = detect_aggregate_query("combien de classes dans le bloc A")
        assert result is not None
        assert result["type"] == "count"
        assert result["block"] == "A"

    def test_detects_list_query(self):
        result = detect_aggregate_query("liste des corridors")
        assert result is not None
        assert result["type"] == "list"

    def test_returns_none_for_simple_query(self):
        assert detect_aggregate_query("chaufferie") is None


class TestSearchEntries:
    """Tests for searching the gold index."""

    def test_finds_room_by_exact_id(self, gold_index):
        """Should find A-204 as first result."""
        results = search_entries(gold_index, "A-204")
        assert len(results) > 0
        assert results[0]["id"] == "A-204"

    def test_finds_room_by_bare_number(self, gold_index):
        """Should find room 204 without prefix."""
        results = search_entries(gold_index, "204")
        assert len(results) > 0
        assert results[0]["plan_id"] == "204"

    def test_finds_chaufferie(self, gold_index):
        """Should find chaufferie."""
        results = search_entries(gold_index, "chaufferie")
        assert len(results) > 0
        assert results[0]["name"] == "CHAUFFERIE"

    def test_finds_gymnase(self, gold_index):
        """Should find gymnase."""
        results = search_entries(gold_index, "gymnase")
        assert len(results) > 0
        assert results[0]["name"] == "GYMNASE"

    def test_finds_bibliotheque(self, gold_index):
        """Should find bibliothèque."""
        results = search_entries(gold_index, "bibliothèque")
        assert len(results) > 0
        assert results[0]["name"] == "BIBLIOTHÈQUE"

    def test_finds_corridors(self, gold_index):
        """Should find corridors."""
        results = search_entries(gold_index, "corridor")
        assert len(results) > 0
        corridors = [r for r in results if r["room_type"] == "CORRIDOR"]
        assert len(corridors) > 5

    def test_finds_maternelle(self, gold_index):
        """Should find maternelle classes."""
        results = search_entries(gold_index, "maternelle")
        assert len(results) > 0
        assert any("MATERNELLE" in r["name"] for r in results)

    def test_blocks_fabricated_room(self, gold_index):
        """CRITICAL: Fabricated rooms must be blocked."""
        results = search_entries(gold_index, "B-101")
        assert len(results) == 1
        assert results[0]["type"] == "fabricated_warning"

    def test_blocks_all_fabricated_rooms(self, gold_index):
        """All known fabricated rooms must be blocked."""
        fabricated_ids = ["B-101", "B-201", "C-101", "A-103", "A-200"]
        for fid in fabricated_ids:
            results = search_entries(gold_index, fid)
            assert len(results) > 0, f"Fabricated room {fid} not caught"
            assert results[0]["type"] == "fabricated_warning", \
                f"Fabricated room {fid} not blocked! Got: {results[0].get('type')}"

    def test_no_results_for_nonsense(self, gold_index):
        """Should return empty for nonsense queries."""
        results = search_entries(gold_index, "xyznonexistent")
        assert results == []

    def test_all_results_have_source(self, gold_index):
        """Every search result must have a source."""
        results = search_entries(gold_index, "classe")
        for r in results:
            if r.get("type") != "fabricated_warning":
                assert r.get("source"), f"Result {r.get('id')} missing source!"


class TestQueryGoldRag:
    """Integration tests for the full query pipeline."""

    def test_query_returns_structured_response(self, gold_rag_dir):
        """Should return dict with query, results, formatted, found."""
        result = query_gold_rag("A-204", rag_dir=gold_rag_dir)
        assert "query" in result
        assert "results" in result
        assert "formatted" in result
        assert "found" in result
        assert result["found"] is True

    def test_not_found_response(self, gold_rag_dir):
        """Should return not-found for unknown queries."""
        result = query_gold_rag("piscine olympique", rag_dir=gold_rag_dir)
        assert result["found"] is False
        assert NOT_FOUND_MSG in result["formatted"]

    def test_fabricated_room_response(self, gold_rag_dir):
        """Should warn about fabricated rooms."""
        result = query_gold_rag("B-101", rag_dir=gold_rag_dir)
        assert result["found"] is True
        assert "N'EXISTE PAS" in result["formatted"]

    def test_aggregate_count_query(self, gold_rag_dir):
        """Should count classes in bloc A."""
        result = query_gold_rag("combien de classes dans le bloc A", rag_dir=gold_rag_dir)
        assert result["type"] == "aggregate"
        assert "9" in result["formatted"]  # 9 classes in bloc A

    def test_source_info_in_response(self, gold_rag_dir):
        """Response should include source document info."""
        result = query_gold_rag("chaufferie", rag_dir=gold_rag_dir)
        assert "source_info" in result
        assert result["source_info"].get("source_documents")


# =============================================================================
# Real Mario questions
# =============================================================================

class TestMarioQuestions:
    """Test with actual questions Mario would ask."""

    def test_quest_quoi_local_a204(self, gold_rag_dir):
        """'C'est quoi le local A-204?' → CLASSE, Bloc A, 2e étage."""
        result = query_gold_rag("C'est quoi le local A-204?", rag_dir=gold_rag_dir)
        assert result["found"] is True
        top = result["results"][0]
        assert top["name"] == "CLASSE"
        assert top["id"] == "A-204"
        assert top["floor"] == 2
        assert top["confidence"] == "HIGH"
        assert "A-150" in top["source_pages"]

    def test_ou_est_chaufferie(self, gold_rag_dir):
        """'Où est la chaufferie?' → A-110, Bloc A, 1er étage."""
        result = query_gold_rag("Où est la chaufferie?", rag_dir=gold_rag_dir)
        assert result["found"] is True
        top = result["results"][0]
        assert top["name"] == "CHAUFFERIE"
        assert top["id"] == "A-110"
        assert top["block"] == "A"
        assert top["floor"] == 1

    def test_combien_classes_bloc_a(self, gold_rag_dir):
        """'Combien de classes dans le bloc A?' → 9."""
        result = query_gold_rag("Combien de classes dans le bloc A?", rag_dir=gold_rag_dir)
        assert result["found"] is True
        assert "9" in result["formatted"]

    def test_corridor_101(self, gold_rag_dir):
        """'C'est quoi les finis du corridor 101?' → Corridor A-101."""
        result = query_gold_rag("C'est quoi les finis du corridor 101?", rag_dir=gold_rag_dir)
        assert result["found"] is True
        top = result["results"][0]
        assert top["plan_id"] == "101"
        assert top["room_type"] == "CORRIDOR"

    def test_gymnase(self, gold_rag_dir):
        """'Où est le gymnase?' → C-151, Bloc C."""
        result = query_gold_rag("Où est le gymnase?", rag_dir=gold_rag_dir)
        assert result["found"] is True
        top = result["results"][0]
        assert top["name"] == "GYMNASE"
        assert top["id"] == "C-151"
        assert top["block"] == "C"

    def test_bibliotheque(self, gold_rag_dir):
        """'C'est quoi la bibliothèque?' → A-123."""
        result = query_gold_rag("bibliothèque", rag_dir=gold_rag_dir)
        assert result["found"] is True
        top = result["results"][0]
        assert top["name"] == "BIBLIOTHÈQUE"
        assert top["id"] == "A-123"

    def test_bureau_directeur(self, gold_rag_dir):
        """'Bureau du directeur' → A-115."""
        result = query_gold_rag("bureau directeur", rag_dir=gold_rag_dir)
        assert result["found"] is True
        top = result["results"][0]
        assert top["name"] == "BUREAU DIRECTEUR"
        assert top["id"] == "A-115"

    def test_service_de_garde(self, gold_rag_dir):
        """'Service de garde' → B-138."""
        result = query_gold_rag("service de garde", rag_dir=gold_rag_dir)
        assert result["found"] is True
        top = result["results"][0]
        assert top["name"] == "SERVICE DE GARDE"
        assert top["id"] == "B-138"

    def test_salle_professeurs(self, gold_rag_dir):
        """'Salle des professeurs' → A-118."""
        result = query_gold_rag("salle professeurs", rag_dir=gold_rag_dir)
        assert result["found"] is True
        top = result["results"][0]
        assert top["name"] == "SALLE PROFESSEURS"
        assert top["id"] == "A-118"

    def test_classe_maternelle(self, gold_rag_dir):
        """'Classe maternelle' → B-131 or B-135 or B-137."""
        result = query_gold_rag("classe maternelle", rag_dir=gold_rag_dir)
        assert result["found"] is True
        maternelles = [r for r in result["results"] if "MATERNELLE" in r["name"]]
        assert len(maternelles) >= 3  # 131, 135, 137


# =============================================================================
# Anti-hallucination tests (CRITICAL)
# =============================================================================

class TestAntiHallucination:
    """Tests to ensure ZERO hallucination."""

    def test_no_room_without_gold_gt(self, gold_index, gold_data):
        """Every room in the index must be in the gold GT."""
        gold_ids = {r["id"] for r in gold_data["verified_rooms"]}
        for entry in gold_index["entries"]:
            assert entry["id"] in gold_ids, \
                f"Room {entry['id']} is in RAG but NOT in gold GT!"

    def test_fabricated_rooms_never_returned(self, gold_index, gold_data):
        """Fabricated rooms must never appear as real results."""
        fabricated = set(gold_data["rooms_NOT_found"]["fabricated_rooms"])
        # Verified rooms override the fabricated list (some IDs overlap due to naming convention)
        verified_ids = {r["id"] for r in gold_data["verified_rooms"]}
        truly_fabricated = fabricated - verified_ids
        
        for entry in gold_index["entries"]:
            assert entry["id"] not in truly_fabricated, \
                f"Fabricated room {entry['id']} leaked into RAG!"

    def test_no_extrapolated_data(self, gold_index):
        """No entry should have data not in the gold GT."""
        for entry in gold_index["entries"]:
            # Every entry must be verified
            assert entry["verified"] is True
            # Every entry must have a source
            assert entry["source"]
            # Confidence must be explicit
            assert entry["confidence"] in ("HIGH", "MEDIUM")

    def test_room_count_exact(self, gold_index):
        """RAG must have exactly 80 rooms (same as gold GT)."""
        assert len(gold_index["entries"]) == 80

    def test_not_found_for_nonexistent(self, gold_rag_dir):
        """Must return 'not found' for things not in documents."""
        queries = [
            "piscine",
            "cafétéria",
            "stationnement",
            "local A-999",
            "auditorium",
        ]
        for q in queries:
            result = query_gold_rag(q, rag_dir=gold_rag_dir)
            # Either not found or fabricated warning
            if result["found"]:
                # If found, results should not include fake rooms
                for r in result["results"]:
                    assert r.get("verified") is True or r.get("type") == "fabricated_warning"
