"""
Agent 2: GuideApplier

Applique le guide provisoire sur des pages de validation et génère des rapports.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol


class ValidationStatus(Enum):
    """Status de validation d'une règle."""

    CONFIRMED = "confirmed"
    CONTRADICTED = "contradicted"
    VARIATION = "variation"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class RuleValidation:
    """Résultat de validation d'une règle sur une page."""

    rule_id: str
    status: ValidationStatus
    page: str
    evidence: str = ""
    notes: str = ""


@dataclass
class ValidationReport:
    """Rapport de validation pour une page."""

    page: str
    rule_validations: list[RuleValidation] = field(default_factory=list)
    overall_notes: str = ""

    @property
    def confirmed_count(self) -> int:
        return sum(1 for v in self.rule_validations if v.status == ValidationStatus.CONFIRMED)

    @property
    def contradicted_count(self) -> int:
        return sum(1 for v in self.rule_validations if v.status == ValidationStatus.CONTRADICTED)

    @property
    def variation_count(self) -> int:
        return sum(1 for v in self.rule_validations if v.status == ValidationStatus.VARIATION)


@dataclass
class GuideApplierOutput:
    """Output de l'agent GuideApplier."""

    validation_reports: list[ValidationReport]
    summary: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        if not self.summary:
            self.summary = self._compute_summary()

    def _compute_summary(self) -> dict[str, int]:
        total_confirmed = sum(r.confirmed_count for r in self.validation_reports)
        total_contradicted = sum(r.contradicted_count for r in self.validation_reports)
        total_variations = sum(r.variation_count for r in self.validation_reports)
        return {
            "confirmed": total_confirmed,
            "contradicted": total_contradicted,
            "variations": total_variations,
            "pages_validated": len(self.validation_reports),
        }


class LLMClient(Protocol):
    """Protocol pour le client LLM."""

    def validate_guide(self, image_path: str, guide: str) -> str:
        """Valide le guide sur une image."""
        ...


class MockLLMClient:
    """Client LLM mocké pour le développement."""

    def validate_guide(self, image_path: str, guide: str) -> str:
        """Retourne une validation mockée."""
        return f"[MOCK] Validated guide on {image_path}"


class GuideApplier:
    """
    Agent qui applique le guide provisoire sur des pages de validation.

    Workflow:
    1. Pour chaque page de validation
    2. Applique chaque règle du guide
    3. Détermine le status: CONFIRMED/CONTRADICTED/VARIATION
    4. Génère un rapport de validation
    """

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client or MockLLMClient()

    def run(
        self,
        provisional_guide: str,
        validation_pages: list[str | Path],
        candidate_rules: list[dict] | None = None
    ) -> GuideApplierOutput:
        """
        Exécute l'agent sur les pages de validation.

        Args:
            provisional_guide: Le guide provisoire à valider
            validation_pages: Liste des chemins vers les pages de validation
            candidate_rules: Liste optionnelle des règles à valider

        Returns:
            GuideApplierOutput avec les rapports de validation
        """
        # Normaliser les paths
        pages = [str(p) for p in validation_pages]

        # Extraire les IDs de règles du guide ou utiliser ceux fournis
        rule_ids = self._extract_rule_ids(provisional_guide, candidate_rules)

        # Valider chaque page
        validation_reports = []
        for page in pages:
            report = self._validate_page(page, provisional_guide, rule_ids)
            validation_reports.append(report)

        return GuideApplierOutput(validation_reports=validation_reports)

    def _extract_rule_ids(
        self,
        guide: str,
        candidate_rules: list[dict] | None
    ) -> list[str]:
        """Extrait les IDs de règles."""
        if candidate_rules:
            return [r.get("rule_id", r.get("id", f"R{i:03d}"))
                    for i, r in enumerate(candidate_rules)]

        # Parse le guide pour trouver les règles (simplifié)
        import re
        matches = re.findall(r"R\d{3}", guide)
        return list(set(matches)) if matches else ["R001", "R002", "R003"]

    def _validate_page(
        self,
        page: str,
        guide: str,
        rule_ids: list[str]
    ) -> ValidationReport:
        """
        Valide une page contre le guide.

        Actuellement mocké - génère des validations simulées.
        """
        # Mock LLM call
        _ = self.llm_client.validate_guide(page, guide)

        # Générer des validations mockées
        validations = []
        for i, rule_id in enumerate(rule_ids):
            # Simuler différents status pour le mock
            if i % 3 == 0:
                status = ValidationStatus.CONFIRMED
                evidence = "Pattern matches expected format"
            elif i % 3 == 1:
                status = ValidationStatus.VARIATION
                evidence = "Minor variation in notation detected"
            else:
                status = ValidationStatus.CONFIRMED
                evidence = "Consistent with guide specifications"

            validations.append(RuleValidation(
                rule_id=rule_id,
                status=status,
                page=page,
                evidence=evidence
            ))

        return ValidationReport(
            page=page,
            rule_validations=validations,
            overall_notes=f"Validation complete for {Path(page).name}"
        )
