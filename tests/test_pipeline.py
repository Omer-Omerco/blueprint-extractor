"""
Tests pour le pipeline à 4 agents.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.agents import (
    GuideBuilder,
    GuideApplier,
    SelfValidator,
    Consolidator,
)
from scripts.agents.guide_builder import GuideBuilderOutput, CandidateRule
from scripts.agents.guide_applier import (
    GuideApplierOutput,
    ValidationReport,
    RuleValidation,
    ValidationStatus,
)
from scripts.agents.self_validator import ConfidenceReport, RuleConfidence
from scripts.agents.consolidator import ConsolidatorOutput, StableRule
from scripts.pipeline_orchestrator import (
    PipelineOrchestrator,
    PipelineConfig,
    PipelineResult,
)


class TestGuideBuilder:
    """Tests pour l'agent GuideBuilder."""

    def test_init_with_default_client(self):
        """Test initialisation avec client mocké par défaut."""
        builder = GuideBuilder()
        assert builder.llm_client is not None

    def test_run_returns_output(self):
        """Test que run() retourne un GuideBuilderOutput."""
        builder = GuideBuilder()
        result = builder.run(["page1.png", "page2.png"])

        assert isinstance(result, GuideBuilderOutput)
        assert result.provisional_guide is not None
        assert len(result.provisional_guide) > 0
        assert isinstance(result.candidate_rules, list)
        assert len(result.candidate_rules) > 0

    def test_candidate_rules_structure(self):
        """Test la structure des règles candidates."""
        builder = GuideBuilder()
        result = builder.run(["page1.png"])

        for rule in result.candidate_rules:
            assert isinstance(rule, CandidateRule)
            assert rule.rule_id.startswith("R")
            assert rule.pattern is not None
            assert rule.description is not None
            assert 0.0 <= rule.confidence <= 1.0

    def test_source_images_preserved(self):
        """Test que les images sources sont préservées."""
        pages = ["img1.png", "img2.png", "img3.png"]
        builder = GuideBuilder()
        result = builder.run(pages)

        assert result.source_images == pages


class TestGuideApplier:
    """Tests pour l'agent GuideApplier."""

    def test_run_returns_validation_reports(self):
        """Test que run() retourne des rapports de validation."""
        applier = GuideApplier()
        result = applier.run(
            provisional_guide="# Test Guide\n## Rules\n- R001: Test rule",
            validation_pages=["val1.png", "val2.png"]
        )

        assert isinstance(result, GuideApplierOutput)
        assert len(result.validation_reports) == 2

    def test_validation_status_values(self):
        """Test que les status de validation sont valides."""
        applier = GuideApplier()
        result = applier.run(
            provisional_guide="# Guide with R001, R002, R003",
            validation_pages=["page.png"]
        )

        for report in result.validation_reports:
            for validation in report.rule_validations:
                assert validation.status in ValidationStatus

    def test_summary_computed(self):
        """Test que le résumé est calculé."""
        applier = GuideApplier()
        result = applier.run(
            provisional_guide="# Guide",
            validation_pages=["p1.png", "p2.png", "p3.png"]
        )

        assert "pages_validated" in result.summary
        assert result.summary["pages_validated"] == 3

    def test_candidate_rules_parameter(self):
        """Test avec règles candidates explicites."""
        applier = GuideApplier()
        rules = [
            {"rule_id": "CUSTOM001", "pattern": "test"},
            {"rule_id": "CUSTOM002", "pattern": "test2"},
        ]
        result = applier.run(
            provisional_guide="# Guide",
            validation_pages=["page.png"],
            candidate_rules=rules
        )

        rule_ids = {v.rule_id for r in result.validation_reports for v in r.rule_validations}
        assert "CUSTOM001" in rule_ids
        assert "CUSTOM002" in rule_ids


class TestSelfValidator:
    """Tests pour l'agent SelfValidator."""

    def test_run_returns_confidence_report(self):
        """Test que run() retourne un ConfidenceReport."""
        validator = SelfValidator()

        # Créer un mock GuideApplierOutput
        applier_output = GuideApplierOutput(
            validation_reports=[
                ValidationReport(
                    page="page1.png",
                    rule_validations=[
                        RuleValidation(
                            rule_id="R001",
                            status=ValidationStatus.CONFIRMED,
                            page="page1.png"
                        )
                    ]
                )
            ]
        )

        result = validator.run("# Guide", applier_output)

        assert isinstance(result, ConfidenceReport)
        assert 0.0 <= result.overall_score <= 1.0
        assert isinstance(result.can_generate_final, bool)

    def test_confidence_threshold_configurable(self):
        """Test que le seuil de confiance est configurable."""
        validator = SelfValidator(confidence_threshold=0.9)
        assert validator.threshold == 0.9

    def test_contradictions_lower_confidence(self):
        """Test que les contradictions diminuent la confiance."""
        validator = SelfValidator()

        # Output avec contradictions
        applier_output = GuideApplierOutput(
            validation_reports=[
                ValidationReport(
                    page="page1.png",
                    rule_validations=[
                        RuleValidation(
                            rule_id="R001",
                            status=ValidationStatus.CONTRADICTED,
                            page="page1.png"
                        )
                    ]
                )
            ]
        )

        result = validator.run("# Guide", applier_output)

        # Avec une contradiction, can_generate_final devrait être False
        assert result.can_generate_final is False

    def test_issues_identified(self):
        """Test que les problèmes sont identifiés."""
        validator = SelfValidator()

        applier_output = GuideApplierOutput(
            validation_reports=[
                ValidationReport(
                    page="page1.png",
                    rule_validations=[
                        RuleValidation(
                            rule_id="R001",
                            status=ValidationStatus.CONTRADICTED,
                            page="page1.png"
                        )
                    ]
                )
            ]
        )

        result = validator.run("# Guide", applier_output)

        assert len(result.issues) > 0


class TestConsolidator:
    """Tests pour l'agent Consolidator."""

    def test_success_when_confident(self):
        """Test consolidation réussie avec haute confiance."""
        consolidator = Consolidator()

        confidence_report = ConfidenceReport(
            overall_score=0.85,
            can_generate_final=True,
            rule_confidences=[
                RuleConfidence(
                    rule_id="R001",
                    confidence=0.9,
                    confirmed_count=5,
                    contradicted_count=0,
                    variation_count=1
                )
            ]
        )

        result = consolidator.run("# Provisional Guide", confidence_report)

        assert isinstance(result, ConsolidatorOutput)
        assert result.success is True
        assert result.stable_guide is not None
        assert len(result.stable_rules) > 0

    def test_rejection_when_low_confidence(self):
        """Test rejet avec faible confiance."""
        consolidator = Consolidator()

        confidence_report = ConfidenceReport(
            overall_score=0.4,
            can_generate_final=False,
            rule_confidences=[
                RuleConfidence(
                    rule_id="R001",
                    confidence=0.3,
                    confirmed_count=1,
                    contradicted_count=2,
                    variation_count=0
                )
            ]
        )

        result = consolidator.run("# Provisional Guide", confidence_report)

        assert result.success is False
        assert result.rejection_message is not None
        assert result.stable_guide is None

    def test_custom_threshold(self):
        """Test avec seuil personnalisé."""
        consolidator = Consolidator(confidence_threshold=0.5)

        confidence_report = ConfidenceReport(
            overall_score=0.6,
            can_generate_final=True,
            rule_confidences=[
                RuleConfidence(
                    rule_id="R001",
                    confidence=0.6,
                    confirmed_count=3,
                    contradicted_count=0,
                    variation_count=2
                )
            ]
        )

        result = consolidator.run("# Guide", confidence_report)
        assert result.success is True


class TestPipelineOrchestrator:
    """Tests pour l'orchestrateur de pipeline."""

    def test_full_pipeline_execution(self):
        """Test l'exécution complète du pipeline."""
        orchestrator = PipelineOrchestrator()
        result = orchestrator.run(pages=["page1.png", "page2.png"])

        assert isinstance(result, PipelineResult)
        assert result.stage_completed == "consolidator"
        assert result.guide_builder_output is not None
        assert result.guide_applier_output is not None
        assert result.confidence_report is not None
        assert result.consolidator_output is not None

    def test_pipeline_with_config(self):
        """Test pipeline avec configuration personnalisée."""
        config = PipelineConfig(confidence_threshold=0.5)
        orchestrator = PipelineOrchestrator(config)

        result = orchestrator.run(pages=["page.png"])

        assert orchestrator.config.confidence_threshold == 0.5

    def test_pipeline_with_validation_pages(self):
        """Test pipeline avec pages de validation séparées."""
        orchestrator = PipelineOrchestrator()
        result = orchestrator.run(
            pages=["build1.png", "build2.png"],
            validation_pages=["val1.png", "val2.png", "val3.png"]
        )

        # Les pages de validation doivent être utilisées dans GuideApplier
        assert len(result.guide_applier_output.validation_reports) == 3

    def test_result_to_dict(self):
        """Test la sérialisation du résultat."""
        orchestrator = PipelineOrchestrator()
        result = orchestrator.run(pages=["page.png"])

        result_dict = result.to_dict()

        assert "success" in result_dict
        assert "stage_completed" in result_dict
        assert "execution_time_ms" in result_dict

    def test_save_results(self, tmp_path):
        """Test la sauvegarde des résultats."""
        orchestrator = PipelineOrchestrator()
        result = orchestrator.run(pages=["page.png"])

        saved = orchestrator.save_results(result, tmp_path)

        assert "summary" in saved
        assert saved["summary"].exists()

        # Vérifier que le fichier JSON est valide
        import json
        with open(saved["summary"]) as f:
            data = json.load(f)
            assert "success" in data


class TestPipelineIntegration:
    """Tests d'intégration du pipeline complet."""

    def test_end_to_end_success_scenario(self):
        """Test scénario de bout en bout avec succès."""
        config = PipelineConfig(confidence_threshold=0.5)
        orchestrator = PipelineOrchestrator(config)

        # Simuler plusieurs pages
        pages = [f"blueprint_{i}.png" for i in range(5)]

        result = orchestrator.run(pages=pages)

        # Le pipeline devrait se terminer sans erreur
        assert result.error_message is None
        assert result.stage_completed == "consolidator"

        # Vérifier la chaîne de données
        assert result.guide_builder_output.source_images == pages
        assert len(result.guide_applier_output.validation_reports) == len(pages)
        assert result.confidence_report.overall_score > 0

    def test_end_to_end_with_few_pages(self):
        """Test avec peu de pages."""
        orchestrator = PipelineOrchestrator()
        result = orchestrator.run(pages=["single.png"])

        # Devrait toujours fonctionner
        assert result.stage_completed == "consolidator"

    def test_pipeline_deterministic(self):
        """Test que le pipeline est déterministe (avec mocks)."""
        orchestrator = PipelineOrchestrator()

        result1 = orchestrator.run(pages=["a.png", "b.png"])
        result2 = orchestrator.run(pages=["a.png", "b.png"])

        # Les résultats mockés devraient être identiques
        assert result1.success == result2.success
        assert result1.confidence_report.overall_score == result2.confidence_report.overall_score


class TestRuleConfidence:
    """Tests pour RuleConfidence."""

    def test_is_stable_true(self):
        """Test qu'une règle est stable avec bonnes stats."""
        rc = RuleConfidence(
            rule_id="R001",
            confidence=0.9,
            confirmed_count=8,
            contradicted_count=0,
            variation_count=2
        )
        assert rc.is_stable is True

    def test_is_stable_false_with_contradiction(self):
        """Test qu'une règle n'est pas stable avec contradiction."""
        rc = RuleConfidence(
            rule_id="R001",
            confidence=0.8,
            confirmed_count=8,
            contradicted_count=1,
            variation_count=1
        )
        assert rc.is_stable is False

    def test_is_stable_false_low_confirmation_rate(self):
        """Test qu'une règle n'est pas stable avec peu de confirmations."""
        rc = RuleConfidence(
            rule_id="R001",
            confidence=0.5,
            confirmed_count=2,
            contradicted_count=0,
            variation_count=8
        )
        assert rc.is_stable is False


class TestValidationReport:
    """Tests pour ValidationReport."""

    def test_counts(self):
        """Test le comptage des validations."""
        report = ValidationReport(
            page="test.png",
            rule_validations=[
                RuleValidation("R001", ValidationStatus.CONFIRMED, "test.png"),
                RuleValidation("R002", ValidationStatus.CONFIRMED, "test.png"),
                RuleValidation("R003", ValidationStatus.CONTRADICTED, "test.png"),
                RuleValidation("R004", ValidationStatus.VARIATION, "test.png"),
            ]
        )

        assert report.confirmed_count == 2
        assert report.contradicted_count == 1
        assert report.variation_count == 1
