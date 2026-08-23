from __future__ import annotations

from agentcad.models.common import IssueKind, IssueSeverity, QuantityParameter
from agentcad.models.validation import ValidationIssue
from .units import convert_to_canonical


class ValidatorBase:
    module_name = "validator"

    def issue(
        self,
        code: str,
        message: str,
        *,
        kind: IssueKind = IssueKind.INVALID,
        severity: IssueSeverity = IssueSeverity.ERROR,
        affected: list[str] | None = None,
        explanation: str | None = None,
        question: str | None = None,
        requires_user: bool = False,
    ) -> ValidationIssue:
        return ValidationIssue(
            code=code,
            message=message,
            severity=severity,
            kind=kind,
            module=self.module_name,
            affected_parameters=affected or [],
            explanation=explanation,
            suggested_question=question,
            requires_user=requires_user,
        )

    def validate_quantity(
        self,
        q: QuantityParameter,
        *,
        path: str,
        dimension: str,
        positive: bool = True,
        nonzero: bool = False,
        required: bool = True,
    ) -> tuple[list[ValidationIssue], float | None]:
        issues: list[ValidationIssue] = []
        if q.value is None:
            if required:
                issues.append(
                    self.issue(
                        f"{path}.missing",
                        f"Не задано параметр {q.name}.",
                        kind=IssueKind.MISSING,
                        affected=[path],
                        question=f"Уточніть значення параметра {q.name} та його одиницю вимірювання.",
                        requires_user=True,
                    )
                )
            return issues, None
        if q.unit is None:
            issues.append(
                self.issue(
                    f"{path}.unit_missing",
                    f"Для параметра {q.name} не задано одиницю вимірювання.",
                    kind=IssueKind.MISSING,
                    affected=[path],
                    question=f"У яких одиницях задано {q.name} = {q.value}?",
                    requires_user=True,
                )
            )
            return issues, None
        try:
            canonical = convert_to_canonical(q.value, q.unit, dimension)
        except ValueError as exc:
            issues.append(
                self.issue(
                    f"{path}.unit_invalid",
                    str(exc),
                    affected=[path],
                    question=f"Уточніть одиницю вимірювання для {q.name}.",
                    requires_user=True,
                )
            )
            return issues, None
        if positive and canonical <= 0:
            issues.append(
                self.issue(
                    f"{path}.nonpositive",
                    f"Параметр {q.name} повинен бути додатним.",
                    affected=[path],
                    question=f"Уточніть додатне значення {q.name}.",
                    requires_user=True,
                )
            )
        elif nonzero and canonical == 0:
            issues.append(
                self.issue(
                    f"{path}.zero",
                    f"Параметр {q.name} не повинен дорівнювати нулю.",
                    affected=[path],
                    question=f"Уточніть ненульове значення {q.name}.",
                    requires_user=True,
                )
            )
        return issues, canonical
