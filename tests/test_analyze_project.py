"""
Tests for analyze_project.py
4-Agent Pipeline for blueprint analysis.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from analyze_project import (
    load_prompt,
    encode_image,
    get_media_type,
    select_pages,
    call_agent,
    run_pipeline
)


class TestLoadPrompt:
    """Tests for load_prompt function."""
    
    def test_fallback_prompts_available(self):
        """Should have fallback prompts for all agents."""
        prompts = ["guide_builder", "guide_applier", "self_validator", "consolidator"]
        
        for prompt_name in prompts:
            result = load_prompt(prompt_name)
            assert result != "", f"Missing fallback for {prompt_name}"
            assert len(result) > 50, f"Prompt {prompt_name} seems too short"
    
    def test_guide_builder_mentions_pieds_pouces(self):
        """Guide builder prompt should mention Quebec dimension format."""
        prompt = load_prompt("guide_builder")
        assert "pieds" in prompt.lower() or "feet" in prompt.lower()
    
    def test_unknown_prompt_returns_empty(self):
        """Should return empty string for unknown prompts."""
        result = load_prompt("nonexistent_prompt")
        assert result == ""


class TestEncodeImage:
    """Tests for encode_image function."""
    
    def test_encodes_to_base64(self, temp_dir):
        """Should encode image file to base64 string."""
        # Create a test image file
        img_path = temp_dir / "test.png"
        img_path.write_bytes(b"fake image data")
        
        result = encode_image(img_path)
        
        assert isinstance(result, str)
        # Base64 should not contain newlines or special chars
        assert "\n" not in result
        assert " " not in result
    
    def test_output_is_decodable(self, temp_dir):
        """Encoded data should be valid base64."""
        import base64
        
        original_data = b"test image content 12345"
        img_path = temp_dir / "test.png"
        img_path.write_bytes(original_data)
        
        encoded = encode_image(img_path)
        decoded = base64.standard_b64decode(encoded)
        
        assert decoded == original_data


class TestGetMediaType:
    """Tests for get_media_type function."""
    
    @pytest.mark.parametrize("extension,expected", [
        (".png", "image/png"),
        (".PNG", "image/png"),
        (".jpg", "image/jpeg"),
        (".JPG", "image/jpeg"),
        (".jpeg", "image/jpeg"),
        (".gif", "image/gif"),
        (".webp", "image/webp"),
    ])
    def test_known_extensions(self, extension, expected):
        """Should return correct media type for known extensions."""
        path = Path(f"/test/image{extension}")
        assert get_media_type(path) == expected
    
    def test_unknown_extension_defaults_to_png(self):
        """Should default to image/png for unknown extensions."""
        path = Path("/test/image.bmp")
        assert get_media_type(path) == "image/png"


class TestSelectPages:
    """Tests for select_pages function."""
    
    def test_returns_all_if_under_count(self, sample_manifest):
        """Should return all pages if total <= count."""
        # Modify manifest to have fewer pages
        manifest = sample_manifest.copy()
        manifest["pages"] = manifest["pages"][:3]
        
        selected = select_pages(manifest, count=5)
        
        assert len(selected) == 3
    
    def test_balanced_includes_first_page(self, sample_manifest):
        """Balanced strategy should always include first page (often legend)."""
        selected = select_pages(sample_manifest, count=5, strategy="balanced")
        
        assert selected[0]["number"] == 1
    
    def test_balanced_spreads_evenly(self, sample_manifest):
        """Balanced strategy should spread pages evenly."""
        selected = select_pages(sample_manifest, count=5, strategy="balanced")
        
        assert len(selected) == 5
        # Should include first and last
        page_numbers = [p["number"] for p in selected]
        assert 1 in page_numbers
    
    def test_respects_count_limit(self, sample_manifest):
        """Should not return more pages than requested."""
        selected = select_pages(sample_manifest, count=3)
        assert len(selected) <= 3


class TestCallAgent:
    """Tests for call_agent function with mocked API."""
    
    def test_parses_json_response(self, mock_anthropic_client, temp_pages_dir):
        """Should parse JSON from Claude response."""
        expected_response = {
            "observations": [{"type": "test", "description": "test obs"}],
            "candidate_rules": []
        }
        
        mock_anthropic_client.messages.create.return_value.content = [
            MagicMock(text=json.dumps(expected_response))
        ]
        
        images = [temp_pages_dir / "page-001.png"]
        result = call_agent(
            mock_anthropic_client,
            "Test prompt",
            images
        )
        
        assert result["observations"] == expected_response["observations"]
    
    def test_extracts_json_from_markdown(self, mock_anthropic_client, temp_pages_dir):
        """Should extract JSON from markdown code blocks."""
        json_content = {"test": "value", "number": 42}
        markdown_response = f"""Here's my analysis:

```json
{json.dumps(json_content)}
```

That's the result."""
        
        mock_anthropic_client.messages.create.return_value.content = [
            MagicMock(text=markdown_response)
        ]
        
        images = [temp_pages_dir / "page-001.png"]
        result = call_agent(mock_anthropic_client, "Test", images)
        
        assert result["test"] == "value"
        assert result["number"] == 42
    
    def test_returns_raw_on_invalid_json(self, mock_anthropic_client, temp_pages_dir):
        """Should return raw response if JSON parsing fails."""
        mock_anthropic_client.messages.create.return_value.content = [
            MagicMock(text="This is not JSON at all!")
        ]
        
        images = [temp_pages_dir / "page-001.png"]
        result = call_agent(mock_anthropic_client, "Test", images)
        
        assert "raw_response" in result
    
    def test_includes_context_when_provided(self, mock_anthropic_client, temp_pages_dir):
        """Should include context in the prompt."""
        mock_anthropic_client.messages.create.return_value.content = [
            MagicMock(text='{"result": "ok"}')
        ]
        
        images = [temp_pages_dir / "page-001.png"]
        call_agent(
            mock_anthropic_client,
            "Main prompt",
            images,
            context="Previous context here"
        )
        
        # Check that the message was created with both context and prompt
        call_args = mock_anthropic_client.messages.create.call_args
        message_content = call_args.kwargs["messages"][0]["content"]
        
        # Find the text part
        text_part = next(p for p in message_content if p["type"] == "text")
        assert "Previous context here" in text_part["text"]
        assert "Main prompt" in text_part["text"]


class TestRunPipeline:
    """Integration tests for run_pipeline with mocked API."""
    
    def test_pipeline_creates_output_files(self, temp_pages_dir, temp_output_dir, mock_anthropic_client):
        """Pipeline should create guide.json and guide.md."""
        # Mock all agent responses
        responses = [
            # Agent 1: Builder
            {
                "observations": [{"type": "dimension", "description": "Pieds-pouces", "page": 1}],
                "candidate_rules": [{"rule": "Format X'-Y\"", "confidence": 0.9}],
                "legend_extractions": [{"symbol": "▢", "meaning": "Prise"}],
                "provisional_guide": "# Guide provisoire"
            },
            # Agent 2: Applier
            {
                "validation_reports": [
                    {"rule": "Format X'-Y\"", "status": "CONFIRMED", "evidence": "25'-6\"", "page": 2}
                ]
            },
            # Agent 3: Validator
            {
                "can_generate_final": True,
                "confidence_score": 0.85,
                "stable_count": 1,
                "partial_count": 0,
                "unstable_count": 0,
                "stable_rules": ["Format X'-Y\""],
                "issues": []
            },
            # Agent 4: Consolidator
            {
                "stable_guide": "# Guide Final\n\nDimensions en pieds-pouces.",
                "stable_rules_json": [{"kind": "dimension", "pattern": "\\d+'-\\d+\""}]
            }
        ]
        
        call_count = [0]
        
        def mock_create(**kwargs):
            result = MagicMock()
            result.content = [MagicMock(text=json.dumps(responses[min(call_count[0], 3)]))]
            call_count[0] += 1
            return result
        
        mock_anthropic_client.messages.create = mock_create
        
        with patch('analyze_project.anthropic.Anthropic', return_value=mock_anthropic_client):
            result = run_pipeline(
                str(temp_pages_dir),
                str(temp_output_dir),
                api_key="test-key"
            )
        
        # Check outputs
        assert (temp_output_dir / "guide.json").exists()
        assert (temp_output_dir / "guide.md").exists()
        assert (temp_output_dir / "legend.json").exists()
        
        assert result["status"] == "VALIDATED"
        assert result["confidence_score"] == 0.85
    
    def test_pipeline_handles_low_confidence(self, temp_pages_dir, temp_output_dir, mock_anthropic_client):
        """Pipeline should mark as PROVISIONAL_ONLY with low confidence."""
        responses = [
            {"observations": [], "candidate_rules": [], "legend_extractions": [], "provisional_guide": ""},
            {"validation_reports": []},
            {"can_generate_final": False, "confidence_score": 0.3, "stable_count": 0, "partial_count": 0, "unstable_count": 3, "stable_rules": [], "issues": ["Trop d'incertitude"]},
            {"stable_guide": "# Guide incertain", "stable_rules_json": []}
        ]
        
        call_count = [0]
        
        def mock_create(**kwargs):
            result = MagicMock()
            result.content = [MagicMock(text=json.dumps(responses[min(call_count[0], 3)]))]
            call_count[0] += 1
            return result
        
        mock_anthropic_client.messages.create = mock_create
        
        with patch('analyze_project.anthropic.Anthropic', return_value=mock_anthropic_client):
            result = run_pipeline(
                str(temp_pages_dir),
                str(temp_output_dir),
                api_key="test-key"
            )
        
        assert result["status"] == "PROVISIONAL_ONLY"
