#!/usr/bin/env python3
"""
Tests for pipeline_orchestrator.py — 4-agent pipeline.
"""

import json
import pytest
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from pipeline_orchestrator import (
    PipelineConfig,
    PipelineResult,
    PipelineOrchestrator,
)
from agents.guide_builder import GuideBuilderOutput, CandidateRule
from agents.guide_applier import GuideApplierOutput, ValidationReport as ApplierValidationReport, RuleValidation, ValidationStatus
from agents.self_validator import ConfidenceReport, RuleConfidence
from agents.consolidator import ConsolidatorOutput, StableRule


# ============== Fixtures ==============

@pytest.fixture
def config():
    return PipelineConfig(confidence_threshold=0.7, min_validation_pages=2)


@pytest.fixture
def mock_guide_builder_output():
    return GuideBuilderOutput(
        provisional_guide="# Guide Test\n\nRègle 1: Les locaux commencent par A-",
        candidate_rules=[
            CandidateRule(
                rule_id="R1",
                pattern="room_id_prefix",
                description="Room IDs start with block letter",
                source_pages=["page-001.png"],
                confidence=0.8,
            ),
            CandidateRule(
                rule_id="R2",
                pattern="dimension_format",
                description="Dimensions in pieds-pouces",
                source_pages=["page-002.png"],
                confidence=0.9,
            ),
        ],
        source_images=["page-001.png", "page-002.png"],
    )


@pytest.fixture
def mock_applier_output():
    return GuideApplierOutput(
        validation_reports=[
            ApplierValidationReport(
                page="page-003.png",
                rule_validations=[
                    RuleValidation(rule_id="R1", status=ValidationStatus.CONFIRMED, page="page-003.png"),
                    RuleValidation(rule_id="R2", status=ValidationStatus.CONFIRMED, page="page-003.png"),
                ],
            ),
            ApplierValidationReport(
                page="page-004.png",
                rule_validations=[
                    RuleValidation(rule_id="R1", status=ValidationStatus.CONFIRMED, page="page-004.png"),
                    RuleValidation(rule_id="R2", status=ValidationStatus.CONTRADICTED, page="page-004.png"),
                ],
            ),
        ],
    )


@pytest.fixture
def mock_confidence_report():
    return ConfidenceReport(
        overall_score=0.85,
        can_generate_final=True,
        rule_confidences=[
            RuleConfidence(rule_id="R1", confidence=0.9, confirmed_count=2),
            RuleConfidence(rule_id="R2", confidence=0.8, confirmed_count=1, contradicted_count=1),
        ],
        issues=[],
    )


@pytest.fixture
def mock_consolidator_success():
    return ConsolidatorOutput(
        success=True,
        stable_guide="# Final Guide\n\nStable rules applied.",
        stable_rules=[
            StableRule(
                rule_id="R1",
                pattern="room_id_prefix",
                description="Room IDs start with block letter",
                confidence=0.9,
                validation_count=2,
            ),
        ],
        rejection_message=None,
    )


@pytest.fixture
def mock_consolidator_failure():
    return ConsolidatorOutput(
        success=False,
        stable_guide="",
        stable_rules=[],
        rejection_message="Confidence too low: 0.45 < 0.70",
    )


@pytest.fixture
def temp_pages(tmp_path):
    """Create temp fake page images."""
    pages = []
    for i in range(1, 4):
        p = tmp_path / f"page-{i:03d}.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        pages.append(str(p))
    return pages


# ============== PipelineConfig ==============

class TestPipelineConfig:
    def test_defaults(self):
        config = PipelineConfig()
        assert config.confidence_threshold == 0.7
        assert config.min_validation_pages == 2
        assert config.output_format == "json"

    def test_custom(self):
        config = PipelineConfig(confidence_threshold=0.9, output_format="markdown")
        assert config.confidence_threshold == 0.9
        assert config.output_format == "markdown"


# ============== PipelineResult ==============

class TestPipelineResult:
    def test_success_result(self, mock_confidence_report, mock_consolidator_success):
        result = PipelineResult(
            success=True,
            stage_completed="consolidator",
            confidence_report=mock_confidence_report,
            consolidator_output=mock_consolidator_success,
            execution_time_ms=1234.5,
        )
        assert result.success is True
        assert result.execution_time_ms > 0

    def test_failure_result(self):
        result = PipelineResult(
            success=False,
            stage_completed="error",
            error_message="API call failed",
            execution_time_ms=100.0,
        )
        assert result.success is False
        assert result.error_message == "API call failed"

    def test_to_dict_success(self, mock_confidence_report, mock_consolidator_success):
        result = PipelineResult(
            success=True,
            stage_completed="consolidator",
            confidence_report=mock_confidence_report,
            consolidator_output=mock_consolidator_success,
            execution_time_ms=500.0,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert "final_guide" in d
        assert "confidence_score" in d
        assert d["confidence_score"] == 0.85
        assert d["can_generate_final"] is True
        assert d["stable_rules_count"] == 1

    def test_to_dict_failure(self, mock_consolidator_failure):
        result = PipelineResult(
            success=False,
            stage_completed="consolidator",
            consolidator_output=mock_consolidator_failure,
            execution_time_ms=300.0,
        )
        d = result.to_dict()
        assert d["success"] is False
        assert "rejection" in d

    def test_to_dict_error(self):
        result = PipelineResult(
            success=False,
            stage_completed="error",
            error_message="Boom",
        )
        d = result.to_dict()
        assert d["error"] == "Boom"

    def test_to_dict_minimal(self):
        result = PipelineResult(success=False, stage_completed="error")
        d = result.to_dict()
        assert "success" in d
        assert "stage_completed" in d


# ============== PipelineOrchestrator ==============

class TestPipelineOrchestrator:
    def test_init_default_config(self):
        orch = PipelineOrchestrator()
        assert orch.config.confidence_threshold == 0.7

    def test_init_custom_config(self, config):
        orch = PipelineOrchestrator(config)
        assert orch.config.confidence_threshold == 0.7

    def test_run_success(
        self,
        temp_pages,
        mock_guide_builder_output,
        mock_applier_output,
        mock_confidence_report,
        mock_consolidator_success,
    ):
        orch = PipelineOrchestrator()
        orch.guide_builder = MagicMock()
        orch.guide_builder.run.return_value = mock_guide_builder_output
        orch.guide_applier = MagicMock()
        orch.guide_applier.run.return_value = mock_applier_output
        orch.self_validator = MagicMock()
        orch.self_validator.run.return_value = mock_confidence_report
        orch.consolidator = MagicMock()
        orch.consolidator.run.return_value = mock_consolidator_success

        result = orch.run(temp_pages)

        assert result.success is True
        assert result.stage_completed == "consolidator"
        assert result.guide_builder_output == mock_guide_builder_output
        assert result.confidence_report.overall_score == 0.85
        orch.guide_builder.run.assert_called_once()
        orch.guide_applier.run.assert_called_once()
        orch.self_validator.run.assert_called_once()
        orch.consolidator.run.assert_called_once()

    def test_run_failure(
        self,
        temp_pages,
        mock_guide_builder_output,
        mock_applier_output,
        mock_confidence_report,
        mock_consolidator_failure,
    ):
        orch = PipelineOrchestrator()
        orch.guide_builder = MagicMock()
        orch.guide_builder.run.return_value = mock_guide_builder_output
        orch.guide_applier = MagicMock()
        orch.guide_applier.run.return_value = mock_applier_output
        orch.self_validator = MagicMock()
        orch.self_validator.run.return_value = mock_confidence_report
        orch.consolidator = MagicMock()
        orch.consolidator.run.return_value = mock_consolidator_failure

        result = orch.run(temp_pages)

        assert result.success is False
        assert result.consolidator_output.rejection_message is not None

    def test_run_exception(self, temp_pages):
        orch = PipelineOrchestrator()
        orch.guide_builder = MagicMock()
        orch.guide_builder.run.side_effect = RuntimeError("API exploded")

        result = orch.run(temp_pages)

        assert result.success is False
        assert result.stage_completed == "error"
        assert "API exploded" in result.error_message

    def test_run_uses_same_pages_for_validation(self, temp_pages, mock_guide_builder_output):
        """If no validation_pages given, uses same pages."""
        orch = PipelineOrchestrator()
        orch.guide_builder = MagicMock()
        orch.guide_builder.run.return_value = mock_guide_builder_output
        orch.guide_applier = MagicMock()
        orch.guide_applier.run.return_value = MagicMock(validation_reports=[])
        orch.self_validator = MagicMock()
        orch.self_validator.run.return_value = MagicMock(overall_score=0.5)
        orch.consolidator = MagicMock()
        orch.consolidator.run.return_value = MagicMock(success=False, rejection_message="low", stable_rules=[], stable_guide="")

        orch.run(temp_pages)

        # guide_applier should receive the same pages as validation_pages
        call_args = orch.guide_applier.run.call_args
        assert call_args.kwargs.get("validation_pages") == temp_pages or \
               (len(call_args.args) > 1 and call_args.args[1] == temp_pages) or \
               call_args[1].get("validation_pages") == temp_pages

    def test_run_with_separate_validation_pages(
        self,
        tmp_path,
        mock_guide_builder_output,
    ):
        # Create two sets of pages
        train_pages = [str(tmp_path / "train1.png")]
        val_pages = [str(tmp_path / "val1.png")]
        for p in train_pages + val_pages:
            Path(p).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        orch = PipelineOrchestrator()
        orch.guide_builder = MagicMock()
        orch.guide_builder.run.return_value = mock_guide_builder_output
        orch.guide_applier = MagicMock()
        orch.guide_applier.run.return_value = MagicMock(validation_reports=[])
        orch.self_validator = MagicMock()
        orch.self_validator.run.return_value = MagicMock(overall_score=0.5)
        orch.consolidator = MagicMock()
        orch.consolidator.run.return_value = MagicMock(success=False, rejection_message="low", stable_rules=[], stable_guide="")

        orch.run(train_pages, validation_pages=val_pages)

        # guide_builder gets train pages
        orch.guide_builder.run.assert_called_once_with(train_pages)


# ============== save_results ==============

class TestSaveResults:
    def test_save_success(self, tmp_path, mock_confidence_report, mock_consolidator_success):
        orch = PipelineOrchestrator()
        result = PipelineResult(
            success=True,
            stage_completed="consolidator",
            confidence_report=mock_confidence_report,
            consolidator_output=mock_consolidator_success,
            execution_time_ms=500.0,
        )

        saved = orch.save_results(result, tmp_path / "output")

        assert "summary" in saved
        assert saved["summary"].exists()
        assert "guide" in saved
        assert saved["guide"].exists()
        assert "rules" in saved
        assert saved["rules"].exists()

        # Verify JSON content
        with open(saved["summary"]) as f:
            data = json.load(f)
        assert data["success"] is True

        # Verify guide content
        assert saved["guide"].read_text().startswith("# Final Guide")

        # Verify rules
        with open(saved["rules"]) as f:
            rules = json.load(f)
        assert len(rules) == 1
        assert rules[0]["rule_id"] == "R1"

    def test_save_failure(self, tmp_path, mock_consolidator_failure):
        orch = PipelineOrchestrator()
        result = PipelineResult(
            success=False,
            stage_completed="consolidator",
            consolidator_output=mock_consolidator_failure,
            execution_time_ms=200.0,
        )

        saved = orch.save_results(result, tmp_path / "output")

        assert "summary" in saved
        assert "guide" not in saved  # No guide for failure
        assert "rules" not in saved

    def test_save_creates_directory(self, tmp_path):
        orch = PipelineOrchestrator()
        result = PipelineResult(success=False, stage_completed="error")

        output_dir = tmp_path / "nested" / "deep" / "output"
        saved = orch.save_results(result, output_dir)

        assert output_dir.exists()
        assert "summary" in saved
