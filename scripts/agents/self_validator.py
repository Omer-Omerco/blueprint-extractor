"""
Agent 3: SelfValidator

Évalue la confiance du guide provisoire basé sur les rapports de validation.
"""

from dataclasses import dataclass, field
from typing import Protocol

from .guide_applier import GuideApplierOutput, ValidationStatus


@dataclass
class RuleConfidence:
    """Score de confiance pour une règle spécifique."""

    rule_id: str
    confidence: float
    confirmed_count: int = 0
    contradicted_count: int = 0
    variation_count: int = 0

    @property
    def is_stable(self) -> bool:
        """Une règle est stable si elle a >70% de confirmations et 0 contradictions."""
        total = self.confirmed_count + self.contradicted_count + self.variation_count
        if total == 0:
            return False
        return (self.confirmed_count / total >= 0.7) and (self.contradicted_count == 0)


@dataclass
class ConfidenceReport:
    """Rapport de confiance global."""

    overall_score: float
    can_generate_final: bool
    rule_confidences: list[RuleConfidence] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def stable_rules_count(self) -> int:
        return sum(1 for r in self.rule_confidences if r.is_stable)

    @property
    def unstable_rules(self) -> list[str]:
        return [r.rule_id for r in self.rule_confidences if not r.is_stable]


class SelfValidator:
    """
    Agent qui évalue la confiance du guide provisoire.

    Workflow:
    1. Analyse les rapports de validation
    2. Calcule un score de confiance par règle
    3. Calcule un score global
    4. Détermine si le guide peut être finalisé
    """

    CONFIDENCE_THRESHOLD = 0.7

    def __init__(self, confidence_threshold: float | None = None):
        self.threshold = confidence_threshold or self.CONFIDENCE_THRESHOLD

    def run(
        self,
        provisional_guide: str,
        validation_output: GuideApplierOutput
    ) -> ConfidenceReport:
        """
        Évalue la confiance du guide.

        Args:
            provisional_guide: Le guide provisoire
            validation_output: Les résultats de validation de l'agent 2

        Returns:
            ConfidenceReport avec le score et les recommandations
        """
        # Calculer la confiance par règle
        rule_confidences = self._compute_rule_confidences(validation_output)

        # Calculer le score global
        overall_score = self._compute_overall_score(rule_confidences)

        # Identifier les problèmes
        issues = self._identify_issues(validation_output, rule_confidences)

        # Générer les recommandations
        recommendations = self._generate_recommendations(rule_confidences, issues)

        # Déterminer si on peut générer le guide final
        can_generate = self._can_generate_final(overall_score, rule_confidences)

        return ConfidenceReport(
            overall_score=overall_score,
            can_generate_final=can_generate,
            rule_confidences=rule_confidences,
            issues=issues,
            recommendations=recommendations
        )

    def _compute_rule_confidences(
        self,
        validation_output: GuideApplierOutput
    ) -> list[RuleConfidence]:
        """Calcule la confiance pour chaque règle."""
        # Agréger les validations par règle
        rule_stats: dict[str, dict[str, int]] = {}

        for report in validation_output.validation_reports:
            for validation in report.rule_validations:
                if validation.rule_id not in rule_stats:
                    rule_stats[validation.rule_id] = {
                        "confirmed": 0,
                        "contradicted": 0,
                        "variation": 0
                    }

                if validation.status == ValidationStatus.CONFIRMED:
                    rule_stats[validation.rule_id]["confirmed"] += 1
                elif validation.status == ValidationStatus.CONTRADICTED:
                    rule_stats[validation.rule_id]["contradicted"] += 1
                elif validation.status == ValidationStatus.VARIATION:
                    rule_stats[validation.rule_id]["variation"] += 1

        # Calculer la confiance pour chaque règle
        rule_confidences = []
        for rule_id, stats in rule_stats.items():
            total = stats["confirmed"] + stats["contradicted"] + stats["variation"]
            if total > 0:
                # Formule: confirmés contribuent positivement, contradictions pénalisent
                confidence = (
                    stats["confirmed"] - stats["contradicted"] * 2 + stats["variation"] * 0.5
                ) / total
                confidence = max(0.0, min(1.0, confidence))  # Clamp entre 0 et 1
            else:
                confidence = 0.0

            rule_confidences.append(RuleConfidence(
                rule_id=rule_id,
                confidence=confidence,
                confirmed_count=stats["confirmed"],
                contradicted_count=stats["contradicted"],
                variation_count=stats["variation"]
            ))

        return rule_confidences

    def _compute_overall_score(self, rule_confidences: list[RuleConfidence]) -> float:
        """Calcule le score de confiance global."""
        if not rule_confidences:
            return 0.0

        # Moyenne pondérée des confiances
        total_weight = 0
        weighted_sum = 0.0

        for rc in rule_confidences:
            # Poids basé sur le nombre d'observations
            weight = rc.confirmed_count + rc.contradicted_count + rc.variation_count
            weighted_sum += rc.confidence * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight

    def _identify_issues(
        self,
        validation_output: GuideApplierOutput,
        rule_confidences: list[RuleConfidence]
    ) -> list[str]:
        """Identifie les problèmes dans la validation."""
        issues = []

        # Vérifier les contradictions
        contradicted_rules = [
            rc for rc in rule_confidences if rc.contradicted_count > 0
        ]
        if contradicted_rules:
            for rc in contradicted_rules:
                issues.append(
                    f"Rule {rc.rule_id} has {rc.contradicted_count} contradiction(s)"
                )

        # Vérifier les règles à faible confiance
        low_confidence_rules = [
            rc for rc in rule_confidences if rc.confidence < 0.5
        ]
        if low_confidence_rules:
            for rc in low_confidence_rules:
                issues.append(
                    f"Rule {rc.rule_id} has low confidence ({rc.confidence:.2f})"
                )

        # Vérifier le nombre de pages validées
        if validation_output.summary.get("pages_validated", 0) < 2:
            issues.append("Insufficient validation pages (minimum 2 recommended)")

        return issues

    def _generate_recommendations(
        self,
        rule_confidences: list[RuleConfidence],
        issues: list[str]
    ) -> list[str]:
        """Génère des recommandations pour améliorer la confiance."""
        recommendations = []

        if not issues:
            recommendations.append("Guide appears stable and ready for finalization")
            return recommendations

        # Recommandations basées sur les problèmes
        unstable_rules = [rc for rc in rule_confidences if not rc.is_stable]
        if unstable_rules:
            recommendations.append(
                f"Review {len(unstable_rules)} unstable rule(s): "
                f"{', '.join(r.rule_id for r in unstable_rules)}"
            )

        contradicted = [rc for rc in rule_confidences if rc.contradicted_count > 0]
        if contradicted:
            recommendations.append(
                "Investigate contradicted rules and update guide accordingly"
            )

        low_confidence = [rc for rc in rule_confidences if rc.confidence < 0.5]
        if low_confidence:
            recommendations.append(
                "Consider adding more validation pages to improve confidence"
            )

        return recommendations

    def _can_generate_final(
        self,
        overall_score: float,
        rule_confidences: list[RuleConfidence]
    ) -> bool:
        """Détermine si le guide peut être finalisé."""
        # Score global doit être au-dessus du seuil
        if overall_score < self.threshold:
            return False

        # Aucune règle ne doit avoir de contradictions
        if any(rc.contradicted_count > 0 for rc in rule_confidences):
            return False

        # Au moins une règle doit être stable
        if not any(rc.is_stable for rc in rule_confidences):
            return False

        return True
