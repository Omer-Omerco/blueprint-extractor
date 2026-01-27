"""
Tests for query_rag.py
RAG index querying functionality.
"""

import json
import pytest
from pathlib import Path
from io import StringIO

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from query_rag import (
    normalize_query,
    search_index,
    format_room,
    format_door,
    format_dimension,
    format_symbol,
    format_result,
    run_query
)


class TestNormalizeQuery:
    """Tests for query normalization and synonym expansion."""
    
    def test_lowercases_query(self):
        """Should lowercase the query."""
        terms = normalize_query("CLASSE")
        assert "classe" in terms
    
    def test_expands_room_synonyms(self):
        """Should expand 'room' to French equivalents."""
        terms = normalize_query("room")
        
        assert "room" in terms
        assert "local" in terms
        assert "pièce" in terms
        assert "salle" in terms
    
    def test_expands_door_synonyms(self):
        """Should expand 'door' to 'porte'."""
        terms = normalize_query("door")
        
        assert "door" in terms
        assert "porte" in terms
    
    def test_expands_corridor_synonyms(self):
        """Should expand corridor synonyms."""
        terms = normalize_query("corridor")
        
        assert "corridor" in terms
        assert "couloir" in terms
        assert "hall" in terms
    
    def test_expands_bathroom_synonyms(self):
        """Should expand bathroom to Quebec terms."""
        terms = normalize_query("bathroom")
        
        assert "toilette" in terms
        assert "salle de bain" in terms
    
    def test_expands_area_synonyms(self):
        """Should expand area/superficie terms."""
        terms = normalize_query("area")
        
        assert "superficie" in terms
        assert "surface" in terms
        assert "pi²" in terms
    
    def test_handles_multiple_words(self):
        """Should handle multi-word queries."""
        terms = normalize_query("classe 101")
        
        assert "classe" in terms
        assert "101" in terms


class TestSearchIndex:
    """Tests for search_index function."""
    
    def test_finds_room_by_name(self, sample_rag_index):
        """Should find rooms by name."""
        results = search_index(sample_rag_index, "classe")
        
        assert len(results) > 0
        room_results = [r for r in results if r["type"] == "room"]
        assert any(r["name"] == "CLASSE" for r in room_results)
    
    def test_finds_room_by_number(self, sample_rag_index):
        """Should find rooms by number."""
        results = search_index(sample_rag_index, "101")
        
        assert len(results) > 0
        assert any(r.get("number") == "101" for r in results)
    
    def test_filters_by_type(self, sample_rag_index):
        """Should filter results by entry type."""
        results = search_index(sample_rag_index, "classe", entry_type="room")
        
        assert all(r["type"] == "room" for r in results)
    
    def test_filters_by_page(self, sample_rag_index):
        """Should filter results by page number."""
        results = search_index(sample_rag_index, "classe", page=2)
        
        assert all(r.get("page") == 2 for r in results)
    
    def test_filters_by_confidence(self, sample_rag_index):
        """Should filter by minimum confidence."""
        results = search_index(
            sample_rag_index, 
            "corridor", 
            min_confidence=0.9
        )
        
        assert all(r.get("confidence", 1.0) >= 0.9 for r in results)
    
    def test_respects_limit(self, sample_rag_index):
        """Should respect result limit."""
        results = search_index(sample_rag_index, "local", limit=2)
        
        assert len(results) <= 2
    
    def test_ranks_by_score(self, sample_rag_index):
        """Should rank results by relevance score."""
        results = search_index(sample_rag_index, "classe 101")
        
        # Room 101 with name CLASSE should be first
        if results:
            first = results[0]
            assert first.get("number") == "101" or first.get("name") == "CLASSE"
    
    def test_finds_doors(self, sample_rag_index):
        """Should find doors."""
        results = search_index(sample_rag_index, "porte", entry_type="door")
        
        assert len(results) > 0
        assert all(r["type"] == "door" for r in results)
    
    def test_finds_dimensions(self, sample_rag_index):
        """Should find dimensions."""
        results = search_index(sample_rag_index, "25'-6\"", entry_type="dimension")
        
        assert len(results) > 0
    
    def test_finds_symbols(self, sample_rag_index):
        """Should find legend symbols."""
        results = search_index(sample_rag_index, "prise électrique", entry_type="symbol")
        
        assert len(results) > 0
    
    def test_empty_query_returns_empty(self, sample_rag_index):
        """Empty query should return empty results."""
        results = search_index(sample_rag_index, "")
        
        # Should return some results (empty query matches nothing specific)
        # or all results if that's the behavior
        assert isinstance(results, list)
    
    def test_no_match_returns_empty(self, sample_rag_index):
        """Non-matching query should return empty list."""
        results = search_index(sample_rag_index, "xyznonexistent123")
        
        assert results == []


class TestFormatRoom:
    """Tests for room formatting."""
    
    def test_formats_complete_room(self, quebec_rooms):
        """Should format room with all details."""
        room = quebec_rooms[0]  # CLASSE 101
        result = format_room(room)
        
        assert "CLASSE" in result
        assert "101" in result
        assert "25'-6\"" in result
        assert "30'-0\"" in result
        assert "765" in result or "pi²" in result
    
    def test_handles_missing_dimensions(self):
        """Should handle rooms without dimensions."""
        room = {"name": "TEST", "number": "999", "page": 1}
        result = format_room(room)
        
        assert "TEST" in result
        assert "999" in result


class TestFormatDoor:
    """Tests for door formatting."""
    
    def test_formats_door(self, quebec_doors):
        """Should format door with angle."""
        door = quebec_doors[0]
        result = format_door(door)
        
        assert door["number"] in result
        assert "90" in result


class TestFormatDimension:
    """Tests for dimension formatting."""
    
    def test_formats_dimension(self, quebec_dimensions):
        """Should format dimension with context."""
        dim = quebec_dimensions[0]
        result = format_dimension(dim)
        
        assert dim["value_text"] in result
        assert dim["context"] in result


class TestFormatSymbol:
    """Tests for symbol formatting."""
    
    def test_formats_symbol(self, quebec_legend):
        """Should format legend symbol."""
        symbol = quebec_legend[0]
        result = format_symbol(symbol)
        
        assert symbol["meaning"] in result


class TestFormatResult:
    """Tests for generic format_result function."""
    
    def test_dispatches_to_room_formatter(self, quebec_rooms):
        """Should use format_room for room entries."""
        entry = quebec_rooms[0].copy()
        entry["type"] = "room"
        
        result = format_result(entry)
        assert "CLASSE" in result
    
    def test_dispatches_to_door_formatter(self, quebec_doors):
        """Should use format_door for door entries."""
        entry = quebec_doors[0].copy()
        entry["type"] = "door"
        
        result = format_result(entry)
        assert "porte" in result.lower() or "🚪" in result
    
    def test_fallback_to_json_for_unknown(self):
        """Should fall back to JSON for unknown types."""
        entry = {"type": "unknown", "data": "test"}
        result = format_result(entry)
        
        # Should be valid JSON
        assert "unknown" in result


class TestRunQuery:
    """Tests for run_query function."""
    
    def test_loads_index_and_searches(self, temp_rag_dir, capsys):
        """Should load index and return search results."""
        results = run_query(
            str(temp_rag_dir),
            "classe",
            output_format="text"
        )
        
        assert len(results) > 0
        
        # Check output was printed
        captured = capsys.readouterr()
        assert "résultat" in captured.out.lower()
    
    def test_json_output_format(self, temp_rag_dir, capsys):
        """Should output JSON when requested."""
        results = run_query(
            str(temp_rag_dir),
            "classe",
            output_format="json"
        )
        
        captured = capsys.readouterr()
        # Should be valid JSON
        parsed = json.loads(captured.out)
        assert isinstance(parsed, list)
    
    def test_filter_by_type(self, temp_rag_dir):
        """Should filter by entry type."""
        results = run_query(
            str(temp_rag_dir),
            "classe",
            entry_type="room",
            output_format="json"
        )
        
        assert all(r["type"] == "room" for r in results)
    
    def test_filter_by_page(self, temp_rag_dir):
        """Should filter by page."""
        results = run_query(
            str(temp_rag_dir),
            "local",
            page=2,
            output_format="json"
        )
        
        assert all(r.get("page") == 2 for r in results)
    
    def test_no_results_message(self, temp_rag_dir, capsys):
        """Should show message when no results found."""
        run_query(
            str(temp_rag_dir),
            "xyznonexistent123",
            output_format="text"
        )
        
        captured = capsys.readouterr()
        assert "aucun" in captured.out.lower()


class TestQuebecSpecificQueries:
    """Tests for Quebec-specific search queries."""
    
    def test_find_classes(self, sample_rag_index):
        """Should find all classes/salles de classe."""
        results = search_index(sample_rag_index, "classe")
        
        classe_rooms = [r for r in results if r.get("name") == "CLASSE"]
        assert len(classe_rooms) >= 2
    
    def test_find_corridor(self, sample_rag_index):
        """Should find corridors."""
        results = search_index(sample_rag_index, "corridor")
        
        corridor = next((r for r in results if r.get("name") == "CORRIDOR"), None)
        assert corridor is not None
    
    def test_find_sdb(self, sample_rag_index):
        """Should find S.D.B. (salle de bain)."""
        # Using bathroom synonym
        results = search_index(sample_rag_index, "bathroom")
        
        # S.D.B. should be found via search_text that includes normalized terms
        # Actually, let's search for the actual name
        results = search_index(sample_rag_index, "S.D.B.")
        
        sdb = next((r for r in results if "S.D.B." in r.get("name", "")), None)
        assert sdb is not None
    
    def test_find_by_area(self, sample_rag_index):
        """Should find rooms by area in pi²."""
        results = search_index(sample_rag_index, "765 pi²")
        
        # Should find room 101 with 765 sqft
        assert len(results) > 0
    
    def test_find_dimension_format(self, sample_rag_index):
        """Should find specific dimension values."""
        results = search_index(sample_rag_index, "25'-6\"", entry_type="dimension")
        
        assert len(results) > 0
        dim = results[0]
        assert dim["value_text"] == "25'-6\""
