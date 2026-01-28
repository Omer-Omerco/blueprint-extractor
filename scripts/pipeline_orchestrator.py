#!/usr/bin/env python3
"""
Pipeline Orchestrator

Exécute les 4 agents en séquence pour analyser des plans.

Usage:
    python scripts/pipeline_orchestrator.py --pages p1.png p2.png --output output/
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.agents import (
    Consolidator,
    GuideApplier,
    GuideBuilder,
    SelfValidator,
)
from scripts.agents.guide_builder import CandidateRule, GuideBuilderOutput
from scripts.agents.guide_applier import GuideApplierOutput
from scripts.agents.self_validator import ConfidenceReport
from scripts.agents.consolidator import ConsolidatorOutput


@dataclass
class PipelineConfig:
    """Configuration du pipeline."""

    confidence_threshold: float = 0.7
    min_validation_pages: int = 2
    output_format: str = "json"  # "json" or "markdown"


@dataclass
class PipelineResult:
    """Résultat complet du pipeline."""

    success: bool
    stage_completed: str
    guide_builder_output: GuideBuilderOutput | None = None
    guide_applier_output: GuideApplierOutput | None = None
    confidence_report: ConfidenceReport | None = None
    consolidator_output: ConsolidatorOutput | None = None
    error_message: str | None = None
    execution_time_ms: float = 0.0

    def to_dict(self) -> dict:
        """Convertit en dictionnaire sérialisable."""
        result = {
            "success": self.success,
            "stage_completed": self.stage_completed,
            "execution_time_ms": self.execution_time_ms,
        }

        if self.error_message:
            result["error"] = self.error_message

        if self.consolidator_output:
            result["final_guide"] = self.consolidator_output.stable_guide
            result["stable_rules_count"] = len(self.consolidator_output.stable_rules)
            if self.consolidator_output.rejection_message:
                result["rejection"] = self.consolidator_output.rejection_message

        if self.confidence_report:
            result["confidence_score"] = self.confidence_report.overall_score
            result["can_generate_final"] = self.confidence_report.can_generate_final

        return result


class PipelineOrchestrator:
    """
    Orchestre l'exécution des 4 agents en séquence.

    Workflow:
    1. GuideBuilder: Analyse les pages initiales → guide provisoire
    2. GuideApplier: Valide le guide sur des pages supplémentaires
    3. SelfValidator: Évalue la confiance du guide
    4. Consolidator: Génère le guide final ou rejette
    """

    def __init__(self, config: PipelineConfig | None = None):
        self.config = config or PipelineConfig()

        # Initialiser les agents
        self.guide_builder = GuideBuilder()
        self.guide_applier = GuideApplier()
        self.self_validator = SelfValidator(
            confidence_threshold=self.config.confidence_threshold
        )
        self.consolidator = Consolidator(
            confidence_threshold=self.config.confidence_threshold
        )

    def run(
        self,
        pages: list[str | Path],
        validation_pages: list[str | Path] | None = None
    ) -> PipelineResult:
        """
        Exécute le pipeline complet.

        Args:
            pages: Pages pour construire le guide initial
            validation_pages: Pages pour valider le guide (optionnel, sinon utilise pages)

        Returns:
            PipelineResult avec tous les outputs
        """
        import time
        start_time = time.time()

        # Utiliser les mêmes pages pour validation si non spécifié
        if validation_pages is None:
            validation_pages = pages

        try:
            # Stage 1: GuideBuilder
            print("[1/4] Running GuideBuilder...")
            guide_output = self.guide_builder.run(pages)
            print(f"      Generated guide with {len(guide_output.candidate_rules)} rules")

            # Stage 2: GuideApplier
            print("[2/4] Running GuideApplier...")
            applier_output = self.guide_applier.run(
                provisional_guide=guide_output.provisional_guide,
                validation_pages=validation_pages,
                candidate_rules=[
                    {"rule_id": r.rule_id, "pattern": r.pattern}
                    for r in guide_output.candidate_rules
                ]
            )
            print(f"      Validated on {len(applier_output.validation_reports)} pages")

            # Stage 3: SelfValidator
            print("[3/4] Running SelfValidator...")
            confidence_report = self.self_validator.run(
                provisional_guide=guide_output.provisional_guide,
                validation_output=applier_output
            )
            print(f"      Confidence score: {confidence_report.overall_score:.2%}")

            # Stage 4: Consolidator
            print("[4/4] Running Consolidator...")
            consolidator_output = self.consolidator.run(
                provisional_guide=guide_output.provisional_guide,
                confidence_report=confidence_report,
                candidate_rules=guide_output.candidate_rules
            )

            if consolidator_output.success:
                print(f"      SUCCESS: Generated stable guide with {len(consolidator_output.stable_rules)} rules")
            else:
                print(f"      REJECTED: {consolidator_output.rejection_message[:50]}...")

            elapsed = (time.time() - start_time) * 1000

            return PipelineResult(
                success=consolidator_output.success,
                stage_completed="consolidator",
                guide_builder_output=guide_output,
                guide_applier_output=applier_output,
                confidence_report=confidence_report,
                consolidator_output=consolidator_output,
                execution_time_ms=elapsed
            )

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return PipelineResult(
                success=False,
                stage_completed="error",
                error_message=str(e),
                execution_time_ms=elapsed
            )

    def save_results(
        self,
        result: PipelineResult,
        output_dir: str | Path
    ) -> dict[str, Path]:
        """
        Sauvegarde les résultats du pipeline.

        Returns:
            Dict mapping output type to file path
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_files = {}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Sauvegarder le résumé
        summary_path = output_dir / f"pipeline_result_{timestamp}.json"
        with open(summary_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        saved_files["summary"] = summary_path

        # Sauvegarder le guide final si disponible
        if result.consolidator_output and result.consolidator_output.stable_guide:
            guide_path = output_dir / f"final_guide_{timestamp}.md"
            with open(guide_path, "w") as f:
                f.write(result.consolidator_output.stable_guide)
            saved_files["guide"] = guide_path

        # Sauvegarder les règles stables
        if result.consolidator_output and result.consolidator_output.stable_rules:
            rules_path = output_dir / f"stable_rules_{timestamp}.json"
            rules_data = [
                {
                    "rule_id": r.rule_id,
                    "pattern": r.pattern,
                    "description": r.description,
                    "confidence": r.confidence,
                    "validation_count": r.validation_count
                }
                for r in result.consolidator_output.stable_rules
            ]
            with open(rules_path, "w") as f:
                json.dump(rules_data, f, indent=2)
            saved_files["rules"] = rules_path

        return saved_files


def main():
    parser = argparse.ArgumentParser(
        description="Blueprint Analysis Pipeline - 4 Agents"
    )
    parser.add_argument(
        "--pages",
        nargs="+",
        required=True,
        help="Input page images for guide building"
    )
    parser.add_argument(
        "--validation-pages",
        nargs="*",
        help="Validation pages (defaults to --pages)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output/",
        help="Output directory for results"
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.7,
        help="Minimum confidence to accept guide (default: 0.7)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    # Configuration
    config = PipelineConfig(
        confidence_threshold=args.confidence_threshold
    )

    # Exécuter le pipeline
    orchestrator = PipelineOrchestrator(config)
    result = orchestrator.run(
        pages=args.pages,
        validation_pages=args.validation_pages
    )

    # Sauvegarder les résultats
    saved = orchestrator.save_results(result, args.output)

    # Afficher le résumé
    print("\n" + "=" * 50)
    if result.success:
        print("✓ Pipeline completed successfully")
        print(f"  Confidence: {result.confidence_report.overall_score:.2%}")
        print(f"  Stable rules: {len(result.consolidator_output.stable_rules)}")
    else:
        print("✗ Pipeline failed")
        if result.consolidator_output and result.consolidator_output.rejection_message:
            print(f"  Reason: {result.consolidator_output.rejection_message}")
        elif result.error_message:
            print(f"  Error: {result.error_message}")

    print(f"\nSaved files:")
    for name, path in saved.items():
        print(f"  - {name}: {path}")

    print(f"\nExecution time: {result.execution_time_ms:.0f}ms")

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
