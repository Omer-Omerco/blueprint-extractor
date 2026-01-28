#!/usr/bin/env python3
"""
Tests pour le pipeline E2E (scripts/run_pipeline.py).
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from run_pipeline import (
    run_pipeline,
    step_generate_summary,
)


class TestRunPipelineBasic:
    """Tests de base pour run_pipeline."""

    def test_missing_pdf_returns_error(self, tmp_path):
        """Pipeline retourne erreur si PDF inexistant."""
        result = run_pipeline(
            str(tmp_path / "nonexistent.pdf"),
            str(tmp_path / "output"),
        )
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_output_dir_created(self, tmp_path):
        """Le répertoire de sortie est créé automatiquement."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        out = tmp_path / "new_output"

        # Will fail at vector extraction but dir should be created
        result = run_pipeline(str(pdf), str(out))
        assert out.exists()

    def test_report_structure(self, tmp_path):
        """Le rapport a la bonne structure."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        result = run_pipeline(str(pdf), str(tmp_path / "output"))

        assert "success" in result
        assert "input_pdf" in result
        assert "output_dir" in result
        assert "timestamp" in result
        assert "steps" in result
        assert "errors" in result
        assert "duration_seconds" in result


class TestStepGenerateSummary:
    """Tests pour la génération du résumé."""

    def test_generates_json_and_markdown(self, tmp_path):
        """Génère les fichiers summary JSON et report MD."""
        report = {
            "timestamp": "2025-01-01T00:00:00",
            "input_pdf": "test.pdf",
            "duration_seconds": 5.0,
            "steps": {
                "vectors": {
                    "output_file": "vectors.json",
                    "pages_extracted": 10,
                    "total_text_blocks": 500,
                    "total_drawings": 200,
                },
                "rooms": {
                    "output_file": "rooms.json",
                    "rooms_detected": 25,
                },
                "dimensions": {
                    "output_file": "dims.json",
                    "dimensions_detected": 100,
                },
                "doors": {
                    "output_file": "doors.json",
                    "doors_detected": 30,
                },
                "validation": {
                    "confidence_file": "conf.json",
                    "alerts_file": "alerts.json",
                    "avg_confidence": 0.85,
                    "total_alerts": 3,
                    "errors": 1,
                    "warnings": 2,
                },
            },
        }

        result = step_generate_summary(tmp_path, report)

        summary_path = Path(result["summary_file"])
        report_path = Path(result["report_file"])

        assert summary_path.exists()
        assert report_path.exists()

        # Verify JSON is valid
        with open(summary_path) as f:
            data = json.load(f)
        assert data["input_pdf"] == "test.pdf"

        # Verify markdown has key content
        md = report_path.read_text()
        assert "Blueprint Extractor" in md
        assert "10" in md  # pages
        assert "25" in md  # rooms
        assert "5.0s" in md  # duration

    def test_handles_empty_steps(self, tmp_path):
        """Gère un rapport avec steps vides."""
        report = {
            "timestamp": "2025-01-01",
            "input_pdf": "test.pdf",
            "duration_seconds": 0.1,
            "steps": {},
        }

        result = step_generate_summary(tmp_path, report)
        assert Path(result["summary_file"]).exists()
        assert Path(result["report_file"]).exists()


class TestPipelineWithMocks:
    """Tests du pipeline avec mocks pour isoler les étapes."""

    @patch("run_pipeline.step_extract_vectors")
    @patch("run_pipeline.step_detect_rooms")
    @patch("run_pipeline.step_detect_dimensions")
    @patch("run_pipeline.step_detect_doors")
    @patch("run_pipeline.step_build_rag")
    @patch("run_pipeline.step_validate")
    @patch("run_pipeline.step_generate_summary")
    def test_all_steps_called(
        self,
        mock_summary,
        mock_validate,
        mock_rag,
        mock_doors,
        mock_dims,
        mock_rooms,
        mock_vectors,
        tmp_path,
    ):
        """Toutes les étapes sont appelées dans l'ordre."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        mock_vectors.return_value = {
            "output_file": "v.json",
            "pages_extracted": 5,
            "total_text_blocks": 100,
            "total_drawings": 50,
        }
        mock_rooms.return_value = {"output_file": "r.json", "rooms_detected": 10, "stats": {}}
        mock_dims.return_value = {"output_file": "d.json", "dimensions_detected": 20}
        mock_doors.return_value = {"output_file": "do.json", "doors_detected": 5}
        mock_rag.return_value = {"output_dir": "rag/", "index_entries": 35}
        mock_validate.return_value = {
            "confidence_file": "c.json",
            "alerts_file": "a.json",
            "avg_confidence": 0.9,
            "total_alerts": 0,
            "errors": 0,
            "warnings": 0,
        }
        mock_summary.return_value = {
            "summary_file": "s.json",
            "report_file": "r.md",
        }

        result = run_pipeline(str(pdf), str(tmp_path / "output"))

        assert result["success"] is True
        mock_vectors.assert_called_once()
        mock_rooms.assert_called_once()
        mock_dims.assert_called_once()
        mock_doors.assert_called_once()
        mock_rag.assert_called_once()
        mock_validate.assert_called_once()
        mock_summary.assert_called_once()

    @patch("run_pipeline.step_extract_vectors")
    def test_stops_on_vector_failure(self, mock_vectors, tmp_path):
        """Le pipeline s'arrête si l'extraction vectorielle échoue."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        mock_vectors.side_effect = RuntimeError("PDF corrupt")

        result = run_pipeline(str(pdf), str(tmp_path / "output"))

        assert result["success"] is False
        assert any("Vector extraction" in e for e in result["errors"])

    @patch("run_pipeline.step_extract_vectors")
    @patch("run_pipeline.step_detect_rooms")
    @patch("run_pipeline.step_detect_dimensions")
    @patch("run_pipeline.step_detect_doors")
    @patch("run_pipeline.step_build_rag")
    @patch("run_pipeline.step_validate")
    @patch("run_pipeline.step_generate_summary")
    def test_continues_on_detection_failure(
        self,
        mock_summary,
        mock_validate,
        mock_rag,
        mock_doors,
        mock_dims,
        mock_rooms,
        mock_vectors,
        tmp_path,
    ):
        """Le pipeline continue si une détection échoue (pas bloquant)."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        mock_vectors.return_value = {
            "output_file": "v.json",
            "pages_extracted": 5,
            "total_text_blocks": 100,
            "total_drawings": 50,
        }
        mock_rooms.side_effect = RuntimeError("Room detection error")
        mock_dims.return_value = {"output_file": "d.json", "dimensions_detected": 20}
        mock_doors.return_value = {"output_file": "do.json", "doors_detected": 5}
        mock_rag.return_value = {"output_dir": "rag/", "index_entries": 25}
        mock_validate.return_value = {
            "confidence_file": "c.json",
            "alerts_file": "a.json",
            "avg_confidence": 0.8,
            "total_alerts": 1,
            "errors": 0,
            "warnings": 1,
        }
        mock_summary.return_value = {"summary_file": "s.json", "report_file": "r.md"}

        result = run_pipeline(str(pdf), str(tmp_path / "output"))

        # Pipeline completes but with errors
        assert result["success"] is False
        assert len(result["errors"]) >= 1
        # Other steps still ran
        mock_dims.assert_called_once()
        mock_doors.assert_called_once()
