"""
Agent 1: GuideBuilder

Construit un guide provisoire à partir d'une liste d'images de plans.
Pour l'instant, le LLM call est mocké avec des placeholders.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class CandidateRule:
    """Une règle candidate extraite des images."""

    rule_id: str
    pattern: str
    description: str
    source_pages: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class GuideBuilderOutput:
    """Output de l'agent GuideBuilder."""

    provisional_guide: str
    candidate_rules: list[CandidateRule]
    source_images: list[str]


class LLMClient(Protocol):
    """Protocol pour le client LLM."""

    def analyze_images(self, image_paths: list[str], prompt: str) -> str:
        """Analyse des images avec un prompt."""
        ...


class MockLLMClient:
    """Client LLM mocké pour le développement."""

    def analyze_images(self, image_paths: list[str], prompt: str) -> str:
        """Retourne une réponse mockée."""
        return f"[MOCK] Analyzed {len(image_paths)} images"


class GuideBuilder:
    """
    Agent qui construit un guide provisoire à partir d'images de plans.

    Workflow:
    1. Analyse les images fournies
    2. Extrait les patterns visuels récurrents
    3. Génère des règles candidates
    4. Compile un guide provisoire
    """

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client or MockLLMClient()

    def run(self, image_paths: list[str | Path]) -> GuideBuilderOutput:
        """
        Exécute l'agent sur une liste d'images.

        Args:
            image_paths: Liste des chemins vers les images de plans

        Returns:
            GuideBuilderOutput avec le guide provisoire et les règles candidates
        """
        # Normaliser les paths
        paths = [str(p) for p in image_paths]

        # Valider que les paths existent (optionnel en mode mock)
        existing_paths = []
        for p in paths:
            if Path(p).exists():
                existing_paths.append(p)
            else:
                existing_paths.append(p)  # On garde même si n'existe pas en mock

        # Mock LLM call - sera remplacé par un vrai appel
        analysis_result = self.llm_client.analyze_images(
            existing_paths,
            prompt=self._build_analysis_prompt()
        )

        # Générer les règles candidates (mocké)
        candidate_rules = self._extract_candidate_rules(paths)

        # Compiler le guide provisoire (mocké)
        provisional_guide = self._compile_provisional_guide(
            analysis_result,
            candidate_rules
        )

        return GuideBuilderOutput(
            provisional_guide=provisional_guide,
            candidate_rules=candidate_rules,
            source_images=paths
        )

    def _build_analysis_prompt(self) -> str:
        """Construit le prompt pour l'analyse LLM."""
        return """Analyze these blueprint images and extract:
1. Visual patterns (symbols, annotations, legends)
2. Room labeling conventions
3. Measurement notation styles
4. Color coding systems
5. Any recurring elements

Output a structured analysis of the visual language used."""

    def _extract_candidate_rules(self, image_paths: list[str]) -> list[CandidateRule]:
        """
        Extrait les règles candidates des images.

        Actuellement mocké - retourne des règles placeholder.
        """
        # Mock rules basées sur des patterns courants dans les plans
        mock_rules = [
            CandidateRule(
                rule_id="R001",
                pattern="room_label_format",
                description="Room labels follow format: TYPE + NUMBER (e.g., 'Chambre 1')",
                source_pages=image_paths[:1] if image_paths else [],
                confidence=0.8
            ),
            CandidateRule(
                rule_id="R002",
                pattern="dimension_notation",
                description="Dimensions in meters with 2 decimal places",
                source_pages=image_paths[:2] if len(image_paths) >= 2 else image_paths,
                confidence=0.9
            ),
            CandidateRule(
                rule_id="R003",
                pattern="scale_indicator",
                description="Scale shown as 1:100 or 1:50 ratio",
                source_pages=image_paths,
                confidence=0.7
            ),
        ]
        return mock_rules

    def _compile_provisional_guide(
        self,
        analysis_result: str,
        candidate_rules: list[CandidateRule]
    ) -> str:
        """
        Compile le guide provisoire à partir de l'analyse et des règles.

        Actuellement mocké - retourne un guide placeholder.
        """
        rules_text = "\n".join(
            f"- {r.rule_id}: {r.description} (confidence: {r.confidence})"
            for r in candidate_rules
        )

        return f"""# Provisional Blueprint Analysis Guide

## Analysis Summary
{analysis_result}

## Candidate Rules
{rules_text}

## Visual Patterns
- Room labels: Standardized naming convention detected
- Dimensions: Metric system with decimal notation
- Scale: Consistent scale indicators present

## Notes
This is a provisional guide pending validation on additional pages.
"""
