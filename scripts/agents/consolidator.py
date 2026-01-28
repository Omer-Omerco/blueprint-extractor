"""
Agent 4: Consolidator

Consolide le guide final si la confiance est suffisante.
"""

from dataclasses import dataclass, field
from typing import Protocol

from .guide_builder import CandidateRule
from .self_validator import ConfidenceReport


@dataclass
class StableRule:
    """Une règle validée et stable."""

    rule_id: str
    pattern: str
    description: str
    confidence: float
    validation_count: int = 0


@dataclass
class ConsolidatorOutput:
    """Output de l'agent Consolidator."""

    success: bool
    stable_guide: str | None = None
    stable_rules: list[StableRule] = field(default_factory=list)
    rejection_message: str | None = None
    rejected_rules: list[str] = field(default_factory=list)


class Consolidator:
    """
    Agent qui consolide le guide final.

    Workflow:
    1. Vérifie que la confiance est suffisante (>= 0.7)
    2. Filtre les règles stables
    3. Génère le guide final
    4. Ou retourne un message de rejet avec explications
    """

    CONFIDENCE_THRESHOLD = 0.7

    def __init__(self, confidence_threshold: float | None = None):
        self.threshold = confidence_threshold or self.CONFIDENCE_THRESHOLD

    def run(
        self,
        provisional_guide: str,
        confidence_report: ConfidenceReport,
        candidate_rules: list[CandidateRule] | None = None
    ) -> ConsolidatorOutput:
        """
        Consolide le guide ou le rejette.

        Args:
            provisional_guide: Le guide provisoire
            confidence_report: Le rapport de confiance de l'agent 3
            candidate_rules: Les règles candidates optionnelles

        Returns:
            ConsolidatorOutput avec le guide stable ou un message de rejet
        """
        # Vérifier si on peut consolider
        if not confidence_report.can_generate_final:
            return self._generate_rejection(confidence_report)

        if confidence_report.overall_score < self.threshold:
            return self._generate_rejection(confidence_report)

        # Filtrer et consolider les règles stables
        stable_rules = self._filter_stable_rules(
            confidence_report,
            candidate_rules
        )

        # Générer le guide final
        stable_guide = self._generate_final_guide(
            provisional_guide,
            stable_rules,
            confidence_report
        )

        # Identifier les règles rejetées
        all_rule_ids = {rc.rule_id for rc in confidence_report.rule_confidences}
        stable_rule_ids = {sr.rule_id for sr in stable_rules}
        rejected_rules = list(all_rule_ids - stable_rule_ids)

        return ConsolidatorOutput(
            success=True,
            stable_guide=stable_guide,
            stable_rules=stable_rules,
            rejected_rules=rejected_rules
        )

    def _generate_rejection(
        self,
        confidence_report: ConfidenceReport
    ) -> ConsolidatorOutput:
        """Génère un message de rejet."""
        reasons = []

        if confidence_report.overall_score < self.threshold:
            reasons.append(
                f"Confidence score ({confidence_report.overall_score:.2f}) "
                f"below threshold ({self.threshold})"
            )

        if confidence_report.issues:
            reasons.extend(confidence_report.issues)

        unstable = confidence_report.unstable_rules
        if unstable:
            reasons.append(f"Unstable rules: {', '.join(unstable)}")

        rejection_message = "Guide cannot be finalized:\n" + "\n".join(
            f"  - {reason}" for reason in reasons
        )

        if confidence_report.recommendations:
            rejection_message += "\n\nRecommendations:\n" + "\n".join(
                f"  - {rec}" for rec in confidence_report.recommendations
            )

        return ConsolidatorOutput(
            success=False,
            rejection_message=rejection_message,
            rejected_rules=confidence_report.unstable_rules
        )

    def _filter_stable_rules(
        self,
        confidence_report: ConfidenceReport,
        candidate_rules: list[CandidateRule] | None
    ) -> list[StableRule]:
        """Filtre et retourne uniquement les règles stables."""
        stable_rules = []

        # Mapper les règles candidates par ID
        candidate_map = {}
        if candidate_rules:
            for cr in candidate_rules:
                candidate_map[cr.rule_id] = cr

        for rc in confidence_report.rule_confidences:
            if not rc.is_stable:
                continue

            # Récupérer les infos de la règle candidate si disponible
            candidate = candidate_map.get(rc.rule_id)

            stable_rules.append(StableRule(
                rule_id=rc.rule_id,
                pattern=candidate.pattern if candidate else rc.rule_id,
                description=candidate.description if candidate else f"Rule {rc.rule_id}",
                confidence=rc.confidence,
                validation_count=rc.confirmed_count + rc.variation_count
            ))

        return stable_rules

    def _generate_final_guide(
        self,
        provisional_guide: str,
        stable_rules: list[StableRule],
        confidence_report: ConfidenceReport
    ) -> str:
        """Génère le guide final consolidé."""
        rules_section = "\n".join(
            f"### {rule.rule_id}: {rule.pattern}\n"
            f"- Description: {rule.description}\n"
            f"- Confidence: {rule.confidence:.2%}\n"
            f"- Validations: {rule.validation_count}"
            for rule in stable_rules
        )

        return f"""# Final Blueprint Analysis Guide

## Status: VALIDATED
Overall Confidence: {confidence_report.overall_score:.2%}
Stable Rules: {len(stable_rules)}

## Validated Rules

{rules_section}

## Usage Notes
This guide has been validated across multiple blueprint pages and can be used
for automated analysis. Rules with confidence above 70% are considered stable.

---
Generated by Blueprint Extractor Pipeline
"""
