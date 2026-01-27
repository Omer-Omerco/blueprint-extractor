"""
Tests for extract_objects.py
Object extraction from blueprint pages.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import extract_objects
from extract_objects import (
    encode_image,
    get_media_type,
    extract_from_page,
    run_extraction,
    EXTRACTION_PROMPT
)


class TestExtractionPrompt:
    """Tests for the extraction prompt template."""
    
    def test_prompt_mentions_pieds_pouces(self):
        """Prompt should specify Quebec dimension format."""
        assert "pieds-pouces" in EXTRACTION_PROMPT.lower() or "pieds et pouces" in EXTRACTION_PROMPT.lower()
    
    def test_prompt_mentions_pi_carre(self):
        """Prompt should mention pi² (square feet)."""
        assert "pi²" in EXTRACTION_PROMPT
    
    def test_prompt_has_json_format(self):
        """Prompt should include JSON output format."""
        assert "rooms" in EXTRACTION_PROMPT
        assert "doors" in EXTRACTION_PROMPT
        assert "dimensions" in EXTRACTION_PROMPT
    
    def test_prompt_rejects_metric(self):
        """Prompt should explicitly reject metric dimensions."""
        assert "métrique" in EXTRACTION_PROMPT.lower() or "metric" in EXTRACTION_PROMPT.lower()


class TestEncodeImage:
    """Tests for image encoding."""
    
    def test_encodes_png_file(self, temp_dir):
        """Should encode PNG files correctly."""
        png_path = temp_dir / "test.png"
        png_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake data")
        
        result = encode_image(png_path)
        
        assert isinstance(result, str)
        assert len(result) > 0


class TestGetMediaType:
    """Tests for media type detection."""
    
    @pytest.mark.parametrize("filename,expected", [
        ("page.png", "image/png"),
        ("page.PNG", "image/png"),
        ("photo.jpg", "image/jpeg"),
        ("photo.jpeg", "image/jpeg"),
    ])
    def test_detects_common_types(self, filename, expected):
        """Should detect common image types."""
        assert get_media_type(Path(filename)) == expected


class TestExtractFromPage:
    """Tests for extract_from_page function."""
    
    def test_parses_room_extraction(self, mock_anthropic_client, temp_pages_dir):
        """Should parse room extraction from API response."""
        api_response = {
            "page_type": "PLAN",
            "rooms": [
                {
                    "id": "room-101",
                    "name": "CLASSE",
                    "number": "101",
                    "dimensions": {
                        "width": "25'-6\"",
                        "depth": "30'-0\"",
                        "area_sqft": 765
                    },
                    "confidence": 0.95
                }
            ],
            "doors": [],
            "windows": [],
            "dimensions": []
        }
        
        mock_anthropic_client.messages.create.return_value.content = [
            MagicMock(text=json.dumps(api_response))
        ]
        
        # Mock the EXTRACTION_PROMPT to avoid format() issues with JSON braces
        with patch('extract_objects.EXTRACTION_PROMPT', 'Test prompt {guide} {rules}'):
            result = extract_from_page(
                mock_anthropic_client,
                temp_pages_dir / "page-001.png",
                guide="# Test Guide",
                rules=[]
            )
        
        assert result["page_type"] == "PLAN"
        assert len(result["rooms"]) == 1
        assert result["rooms"][0]["name"] == "CLASSE"
        assert result["rooms"][0]["dimensions"]["width"] == "25'-6\""
    
    def test_parses_quebec_local_names(self, mock_anthropic_client, temp_pages_dir):
        """Should correctly parse Quebec local names."""
        api_response = {
            "page_type": "PLAN",
            "rooms": [
                {"id": "r1", "name": "CLASSE", "number": "101", "dimensions": {}, "confidence": 0.9},
                {"id": "r2", "name": "CORRIDOR", "number": "102", "dimensions": {}, "confidence": 0.9},
                {"id": "r3", "name": "S.D.B.", "number": "103", "dimensions": {}, "confidence": 0.9},
                {"id": "r4", "name": "RANGEMENT", "number": "104", "dimensions": {}, "confidence": 0.9},
                {"id": "r5", "name": "CAFÉTÉRIA", "number": "105", "dimensions": {}, "confidence": 0.9},
            ],
            "doors": [],
            "windows": [],
            "dimensions": []
        }
        
        mock_anthropic_client.messages.create.return_value.content = [
            MagicMock(text=json.dumps(api_response))
        ]
        
        with patch('extract_objects.EXTRACTION_PROMPT', 'Test prompt {guide} {rules}'):
            result = extract_from_page(
                mock_anthropic_client,
                temp_pages_dir / "page-001.png",
                guide="",
                rules=[]
            )
        
        names = [r["name"] for r in result["rooms"]]
        assert "CLASSE" in names
        assert "CORRIDOR" in names
        assert "S.D.B." in names
    
    def test_extracts_json_from_code_block(self, mock_anthropic_client, temp_pages_dir):
        """Should extract JSON from markdown code block."""
        markdown_response = """Voici l'extraction:

```json
{
  "page_type": "LEGEND",
  "rooms": [],
  "doors": [{"id": "d1", "number": "P01", "swing_angle": 90, "confidence": 0.8}],
  "windows": [],
  "dimensions": []
}
```

Extraction terminée."""
        
        mock_anthropic_client.messages.create.return_value.content = [
            MagicMock(text=markdown_response)
        ]
        
        with patch('extract_objects.EXTRACTION_PROMPT', 'Test prompt {guide} {rules}'):
            result = extract_from_page(
                mock_anthropic_client,
                temp_pages_dir / "page-001.png",
                guide="",
                rules=[]
            )
        
        assert result["page_type"] == "LEGEND"
        assert len(result["doors"]) == 1


class TestRunExtraction:
    """Integration tests for run_extraction."""
    
    def test_creates_output_files(self, temp_pages_dir, temp_output_dir, sample_guide, mock_anthropic_client):
        """Should create rooms.json, doors.json, etc."""
        # Write guide file
        guide_path = temp_output_dir / "guide.json"
        with open(guide_path, "w") as f:
            json.dump(sample_guide, f)
        
        # Mock API responses
        api_response = {
            "page_type": "PLAN",
            "rooms": [{"id": "r1", "name": "CLASSE", "number": "101", "dimensions": {"width": "25'-6\"", "depth": "30'-0\"", "area_sqft": 765}, "confidence": 0.9}],
            "doors": [{"id": "d1", "number": "P01", "swing_angle": 90, "confidence": 0.85}],
            "windows": [],
            "dimensions": [{"id": "dim1", "value_text": "25'-6\"", "value_inches": 306, "context": "largeur", "confidence": 0.9}]
        }
        
        mock_anthropic_client.messages.create.return_value.content = [
            MagicMock(text=json.dumps(api_response))
        ]
        
        with patch('extract_objects.anthropic.Anthropic', return_value=mock_anthropic_client), \
             patch('extract_objects.EXTRACTION_PROMPT', 'Test prompt {guide} {rules}'):
            result = run_extraction(
                str(guide_path),
                str(temp_pages_dir),
                str(temp_output_dir),
                max_pages=2,
                api_key="test-key"
            )
        
        # Check output files exist
        assert (temp_output_dir / "rooms.json").exists()
        assert (temp_output_dir / "doors.json").exists()
        assert (temp_output_dir / "windows.json").exists()
        assert (temp_output_dir / "dimensions.json").exists()
        assert (temp_output_dir / "extraction_summary.json").exists()
        
        # Check summary
        assert result["pages_processed"] == 2
        assert result["summary"]["total_rooms"] >= 1
    
    def test_adds_page_numbers_to_objects(self, temp_pages_dir, temp_output_dir, sample_guide, mock_anthropic_client):
        """Should add page number to each extracted object."""
        guide_path = temp_output_dir / "guide.json"
        with open(guide_path, "w") as f:
            json.dump(sample_guide, f)
        
        api_response = {
            "page_type": "PLAN",
            "rooms": [{"id": "r1", "name": "TEST", "number": "999", "dimensions": {}, "confidence": 0.9}],
            "doors": [],
            "windows": [],
            "dimensions": []
        }
        
        mock_anthropic_client.messages.create.return_value.content = [
            MagicMock(text=json.dumps(api_response))
        ]
        
        with patch('extract_objects.anthropic.Anthropic', return_value=mock_anthropic_client):
            run_extraction(
                str(guide_path),
                str(temp_pages_dir),
                str(temp_output_dir),
                max_pages=1,
                api_key="test-key"
            )
        
        with open(temp_output_dir / "rooms.json") as f:
            rooms = json.load(f)
        
        assert all("page" in room for room in rooms)
    
    def test_handles_extraction_errors(self, temp_pages_dir, temp_output_dir, sample_guide, mock_anthropic_client):
        """Should handle and log extraction errors gracefully."""
        guide_path = temp_output_dir / "guide.json"
        with open(guide_path, "w") as f:
            json.dump(sample_guide, f)
        
        # First call succeeds, second fails
        call_count = [0]
        
        def mock_create(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                result = MagicMock()
                result.content = [MagicMock(text='{"page_type": "PLAN", "rooms": [], "doors": [], "windows": [], "dimensions": []}')]
                return result
            else:
                raise Exception("API Error")
        
        mock_anthropic_client.messages.create = mock_create
        
        with patch('extract_objects.anthropic.Anthropic', return_value=mock_anthropic_client), \
             patch('extract_objects.EXTRACTION_PROMPT', 'Test prompt {guide} {rules}'):
            result = run_extraction(
                str(guide_path),
                str(temp_pages_dir),
                str(temp_output_dir),
                max_pages=2,
                api_key="test-key"
            )
        
        # Should still complete with partial results
        assert result["pages_processed"] == 2
        
        # Check page_results for errors
        error_pages = [p for p in result["page_results"] if "error" in p]
        assert len(error_pages) == 1


class TestQuebecDimensionFormats:
    """Tests for Quebec-specific dimension formats in extraction."""
    
    @pytest.mark.parametrize("dimension,expected_inches", [
        ("25'-6\"", 306),
        ("12'-0\"", 144),
        ("8'-0\"", 96),
        ("30'-0\"", 360),
        ("8'-6\"", 102),
    ])
    def test_dimension_parsing_in_response(self, dimension, expected_inches, mock_anthropic_client, temp_pages_dir):
        """Should correctly handle Quebec dimension formats."""
        api_response = {
            "page_type": "PLAN",
            "rooms": [],
            "doors": [],
            "windows": [],
            "dimensions": [
                {
                    "id": "d1",
                    "value_text": dimension,
                    "value_inches": expected_inches,
                    "context": "test dimension",
                    "confidence": 0.9
                }
            ]
        }
        
        mock_anthropic_client.messages.create.return_value.content = [
            MagicMock(text=json.dumps(api_response))
        ]
        
        with patch('extract_objects.EXTRACTION_PROMPT', 'Test prompt {guide} {rules}'):
            result = extract_from_page(
                mock_anthropic_client,
                temp_pages_dir / "page-001.png",
                guide="",
                rules=[]
            )
        
        assert result["dimensions"][0]["value_text"] == dimension
        assert result["dimensions"][0]["value_inches"] == expected_inches
