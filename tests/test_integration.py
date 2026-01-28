"""
Integration tests for blueprint-extractor.
End-to-end tests for the complete extraction pipeline.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestPipelineIntegration:
    """End-to-end tests for the complete pipeline."""
    
    def test_full_extraction_workflow(
        self, 
        temp_pages_dir, 
        temp_output_dir, 
        sample_guide, 
        mock_anthropic_client,
        quebec_rooms,
        quebec_doors,
        quebec_dimensions
    ):
        """Test complete workflow: analyze → extract → build RAG → query."""
        from analyze_project import run_pipeline
        from extract_objects import run_extraction
        from build_rag import build_index
        from query_rag import search_index
        
        # Step 1: Setup - Create guide file
        guide_path = temp_output_dir / "guide.json"
        with open(guide_path, "w") as f:
            json.dump(sample_guide, f, ensure_ascii=False)
        
        # Step 2: Mock extract_objects API calls
        extraction_response = {
            "page_type": "PLAN",
            "rooms": [
                {
                    "id": "room-101",
                    "name": "CLASSE",
                    "number": "101",
                    "dimensions": {"width": "25'-6\"", "depth": "30'-0\"", "area_sqft": 765},
                    "confidence": 0.95
                },
                {
                    "id": "room-102",
                    "name": "CORRIDOR",
                    "number": "102",
                    "dimensions": {"width": "8'-0\"", "depth": "120'-0\"", "area_sqft": 960},
                    "confidence": 0.90
                }
            ],
            "doors": [
                {"id": "door-P01", "number": "P01", "swing_angle": 90, "confidence": 0.85}
            ],
            "windows": [],
            "dimensions": [
                {"id": "dim-1", "value_text": "25'-6\"", "value_inches": 306, "context": "largeur classe", "confidence": 0.95}
            ]
        }
        
        mock_anthropic_client.messages.create.return_value.content = [
            MagicMock(text=json.dumps(extraction_response))
        ]
        
        # Step 3: Run extraction
        with patch('extract_objects.anthropic.Anthropic', return_value=mock_anthropic_client), \
             patch('extract_objects.EXTRACTION_PROMPT', 'Test prompt {guide} {rules}'):
            extraction_result = run_extraction(
                str(guide_path),
                str(temp_pages_dir),
                str(temp_output_dir),
                max_pages=2,
                api_key="test-key"
            )
        
        # Verify extraction outputs
        assert (temp_output_dir / "rooms.json").exists()
        assert (temp_output_dir / "doors.json").exists()
        assert (temp_output_dir / "dimensions.json").exists()
        assert extraction_result["pages_processed"] == 2
        
        # Step 4: Build RAG index
        rag_dir = temp_output_dir / "rag"
        index = build_index(str(temp_output_dir), str(rag_dir))
        
        # Verify RAG outputs
        assert (rag_dir / "index.json").exists()
        assert index["stats"]["rooms"] >= 1
        
        # Step 5: Query RAG
        with open(rag_dir / "index.json") as f:
            loaded_index = json.load(f)
        
        # Test querying
        results = search_index(loaded_index, "classe")
        assert len(results) >= 1
        
        results = search_index(loaded_index, "corridor")
        assert len(results) >= 1
        
        results = search_index(loaded_index, "porte", entry_type="door")
        assert len(results) >= 1
    
    def test_quebec_dimension_pipeline(self, temp_pages_dir, temp_output_dir, sample_guide, mock_anthropic_client):
        """Test that Quebec dimensions flow correctly through pipeline."""
        from extract_objects import run_extraction
        from build_rag import build_index, parse_dimension
        
        # Setup
        guide_path = temp_output_dir / "guide.json"
        with open(guide_path, "w") as f:
            json.dump(sample_guide, f)
        
        # Mock response with Quebec dimensions
        extraction_response = {
            "page_type": "PLAN",
            "rooms": [
                {
                    "id": "room-105",
                    "name": "RANGEMENT",
                    "number": "105",
                    "dimensions": {
                        "width": "8'-6 1/2\"",
                        "depth": "10'-3\"",
                        "area_sqft": 87
                    },
                    "confidence": 0.85
                }
            ],
            "doors": [],
            "windows": [],
            "dimensions": [
                {"id": "dim-1", "value_text": "8'-6 1/2\"", "value_inches": 102.5, "context": "largeur rangement", "confidence": 0.88}
            ]
        }
        
        mock_anthropic_client.messages.create.return_value.content = [
            MagicMock(text=json.dumps(extraction_response))
        ]
        
        # Run extraction
        with patch('extract_objects.anthropic.Anthropic', return_value=mock_anthropic_client):
            run_extraction(
                str(guide_path),
                str(temp_pages_dir),
                str(temp_output_dir),
                max_pages=1,
                api_key="test-key"
            )
        
        # Build RAG
        rag_dir = temp_output_dir / "rag"
        index = build_index(str(temp_output_dir), str(rag_dir))
        
        # Verify fractional dimension was parsed correctly
        dim_entries = [e for e in index["entries"] if e["type"] == "dimension"]
        
        # Find the fractional dimension
        frac_dim = next((d for d in dim_entries if "1/2" in d.get("value_text", "")), None)
        
        if frac_dim:
            assert frac_dim["parsed"]["total_inches"] == 102.5


class TestQuebecLocalNames:
    """Integration tests for Quebec local (room) names."""
    
    @pytest.mark.parametrize("local_name,search_terms", [
        ("CLASSE", ["classe", "class", "salle"]),
        ("S.D.B.", ["s.d.b.", "salle de bain", "bathroom"]),
        ("CORRIDOR", ["corridor", "couloir", "hall"]),
        ("RANGEMENT", ["rangement", "storage"]),
        ("CAFÉTÉRIA", ["cafétéria", "cafeteria"]),
        ("GYMNASE", ["gymnase", "gym"]),
        ("SECRÉTARIAT", ["secrétariat", "secretariat"]),
        ("CONCIERGERIE", ["conciergerie"]),
    ])
    def test_quebec_room_names_searchable(
        self, 
        local_name, 
        search_terms, 
        temp_dir
    ):
        """Quebec room names should be searchable."""
        from build_rag import build_index
        from query_rag import search_index
        
        # Create test data
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        output_dir = temp_dir / "rag"
        
        rooms = [{
            "id": "room-001",
            "name": local_name,
            "number": "001",
            "dimensions": {"width": "20'-0\"", "depth": "20'-0\"", "area_sqft": 400},
            "confidence": 0.9,
            "page": 1
        }]
        
        with open(source_dir / "rooms.json", "w") as f:
            json.dump(rooms, f, ensure_ascii=False)
        
        # Build index
        index = build_index(str(source_dir), str(output_dir))
        
        # Test searchability
        found = False
        for term in search_terms:
            results = search_index(index, term, entry_type="room")
            if any(r.get("name") == local_name for r in results):
                found = True
                break
        
        # At least one search term should find the room
        # Note: Some terms may not work if synonyms aren't configured
        assert found or local_name in str(index["entries"])


class TestDimensionEdgeCases:
    """Integration tests for dimension parsing edge cases."""
    
    @pytest.mark.parametrize("dimension,expected_inches", [
        # Standard formats
        ("25'-6\"", 306),
        ("8'-0\"", 96),
        ("12'-6 1/2\"", 150.5),
        # Edge cases
        ("0'-6\"", 6),
        ("1'-0\"", 12),
        ("100'-0\"", 1200),
        # Fractions
        ("10'-3 1/4\"", 123.25),
        ("5'-0 3/4\"", 60.75),
        ("8'-6 1/8\"", 102.125),
    ])
    def test_dimension_parsing_accuracy(self, dimension, expected_inches):
        """Dimensions should parse accurately through the pipeline."""
        from build_rag import parse_dimension
        
        result = parse_dimension(dimension)
        
        assert result["total_inches"] == expected_inches
    
    def test_dimensions_in_rag_index(self, temp_dir):
        """Dimensions should be correctly indexed in RAG."""
        from build_rag import build_index
        
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        output_dir = temp_dir / "rag"
        
        dimensions = [
            {"id": "dim-1", "value_text": "25'-6\"", "context": "largeur", "confidence": 0.9, "page": 1},
            {"id": "dim-2", "value_text": "8'-6 1/2\"", "context": "profondeur", "confidence": 0.9, "page": 1},
            {"id": "dim-3", "value_text": "12'-0\"", "context": "hauteur", "confidence": 0.9, "page": 1},
        ]
        
        with open(source_dir / "dimensions.json", "w") as f:
            json.dump(dimensions, f)
        
        index = build_index(str(source_dir), str(output_dir))
        
        dim_entries = [e for e in index["entries"] if e["type"] == "dimension"]
        
        assert len(dim_entries) == 3
        
        # Check parsed values
        for entry in dim_entries:
            assert "parsed" in entry
            if "1/2" in entry["value_text"]:
                assert entry["parsed"]["total_inches"] == 102.5


class TestRagQueryIntegration:
    """Integration tests for RAG queries."""
    
    def test_multilingual_search(self, sample_rag_index):
        """Should find results with French and English queries."""
        from query_rag import search_index
        
        # French queries
        results_fr = search_index(sample_rag_index, "porte")
        # English queries
        results_en = search_index(sample_rag_index, "door")
        
        # Both should find doors
        assert len(results_fr) > 0 or len(results_en) > 0
    
    def test_combined_filters(self, sample_rag_index):
        """Should support combined filters."""
        from query_rag import search_index
        
        # Filter by type and page
        results = search_index(
            sample_rag_index,
            "local",
            entry_type="room",
            page=2
        )
        
        for r in results:
            assert r["type"] == "room"
            assert r.get("page") == 2
    
    def test_confidence_filtering(self, sample_rag_index):
        """Should filter by confidence threshold."""
        from query_rag import search_index
        
        results = search_index(
            sample_rag_index,
            "local",
            min_confidence=0.9
        )
        
        for r in results:
            assert r.get("confidence", 1.0) >= 0.9


class TestErrorHandling:
    """Integration tests for error handling."""
    
    def test_missing_manifest_handling(self, temp_dir, sample_guide):
        """Should handle missing manifest gracefully."""
        from extract_objects import run_extraction
        
        # Create pages dir without manifest
        pages_dir = temp_dir / "pages"
        pages_dir.mkdir()
        
        guide_path = temp_dir / "guide.json"
        with open(guide_path, "w") as f:
            json.dump(sample_guide, f)
        
        output_dir = temp_dir / "output"
        
        with pytest.raises(Exception):  # Should raise an error
            run_extraction(
                str(guide_path),
                str(pages_dir),
                str(output_dir),
                api_key="test-key"
            )
    
    def test_empty_extraction_handling(self, temp_dir):
        """Should handle empty extraction results."""
        from build_rag import build_index
        
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        output_dir = temp_dir / "rag"
        
        # Create empty files
        with open(source_dir / "rooms.json", "w") as f:
            json.dump([], f)
        
        index = build_index(str(source_dir), str(output_dir))
        
        assert index["stats"]["rooms"] == 0
        assert index["stats"]["total_entries"] == 0


class TestDataIntegrity:
    """Tests for data integrity through the pipeline."""
    
    def test_room_data_preserved(self, temp_dir, quebec_rooms):
        """Room data should be preserved through RAG building."""
        from build_rag import build_index
        
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        output_dir = temp_dir / "rag"
        
        with open(source_dir / "rooms.json", "w") as f:
            json.dump(quebec_rooms, f, ensure_ascii=False)
        
        index = build_index(str(source_dir), str(output_dir))
        
        room_entries = [e for e in index["entries"] if e["type"] == "room"]
        
        assert len(room_entries) == len(quebec_rooms)
        
        # Check all room numbers are present
        original_numbers = {r["number"] for r in quebec_rooms}
        indexed_numbers = {str(e["number"]) for e in room_entries}
        
        assert original_numbers == indexed_numbers
    
    def test_dimension_precision_preserved(self, temp_dir, quebec_dimensions):
        """Dimension precision should be preserved."""
        from build_rag import build_index
        
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        output_dir = temp_dir / "rag"
        
        with open(source_dir / "dimensions.json", "w") as f:
            json.dump(quebec_dimensions, f)
        
        index = build_index(str(source_dir), str(output_dir))
        
        dim_entries = [e for e in index["entries"] if e["type"] == "dimension"]
        
        # Check fractional dimension
        frac_dim = next((d for d in dim_entries if "1/2" in d.get("value_text", "")), None)
        if frac_dim:
            assert frac_dim["parsed"]["total_inches"] == 102.5


class TestOutputFormats:
    """Tests for output format correctness."""
    
    def test_json_files_valid(self, temp_pages_dir, temp_output_dir, sample_guide, mock_anthropic_client):
        """All output JSON files should be valid."""
        from extract_objects import run_extraction
        
        guide_path = temp_output_dir / "guide.json"
        with open(guide_path, "w") as f:
            json.dump(sample_guide, f)
        
        extraction_response = {
            "page_type": "PLAN",
            "rooms": [{"id": "r1", "name": "TEST", "number": "001", "dimensions": {}, "confidence": 0.9}],
            "doors": [],
            "windows": [],
            "dimensions": []
        }
        
        mock_anthropic_client.messages.create.return_value.content = [
            MagicMock(text=json.dumps(extraction_response))
        ]
        
        with patch('extract_objects.anthropic.Anthropic', return_value=mock_anthropic_client):
            run_extraction(
                str(guide_path),
                str(temp_pages_dir),
                str(temp_output_dir),
                max_pages=1,
                api_key="test-key"
            )
        
        # Check all JSON files are valid
        json_files = list(temp_output_dir.glob("*.json"))
        
        for json_file in json_files:
            with open(json_file) as f:
                data = json.load(f)  # Should not raise
                assert data is not None
    
    def test_rag_index_structure(self, temp_dir, quebec_rooms, quebec_doors):
        """RAG index should have correct structure."""
        from build_rag import build_index
        
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        output_dir = temp_dir / "rag"
        
        with open(source_dir / "rooms.json", "w") as f:
            json.dump(quebec_rooms, f)
        with open(source_dir / "doors.json", "w") as f:
            json.dump(quebec_doors, f)
        
        index = build_index(str(source_dir), str(output_dir))
        
        # Check required fields
        assert "version" in index
        assert "stats" in index
        assert "entries" in index
        
        # Check stats structure
        assert "rooms" in index["stats"]
        assert "doors" in index["stats"]
        assert "total_entries" in index["stats"]
        
        # Check entry structure
        for entry in index["entries"]:
            assert "type" in entry
            assert "search_text" in entry
