from __future__ import annotations

from agentcad.models.common import IssueKind, IssueSeverity
from agentcad.models.material import MaterialSpec
from agentcad.models.validation import ValidationIssue
from .base import ValidatorBase
from .units import convert_to_canonical


class MaterialValidator(ValidatorBase):
    module_name = "material"

    def validate(self, material: MaterialSpec) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for item in material.unresolved_issues:
            issues.append(
                self.issue(
                    f"planner.{item.code}", item.message, kind=item.kind,
                    affected=item.affected_parameters, explanation=item.explanation,
                    question=item.suggested_question,
                    requires_user=item.kind in {IssueKind.MISSING, IssueKind.CONFLICT, IssueKind.INVALID},
                )
            )

        sub, rho = self.validate_quantity(
            material.density, path="material.density", dimension="density", required=True
        )
        issues.extend(sub)
        sub, young = self.validate_quantity(
            material.young_modulus, path="material.young_modulus", dimension="stress", required=True
        )
        issues.extend(sub)

        p = material.poisson_ratio
        if p.value is None:
            issues.append(
                self.issue(
                    "material.poisson_ratio.missing",
                    "Не задано коефіцієнт Пуассона.",
                    kind=IssueKind.MISSING,
                    affected=["material.poisson_ratio"],
                    question="Уточніть коефіцієнт Пуассона ν для матеріалу.",
                    requires_user=True,
                )
            )
        elif not (-1.0 < p.value < 0.5):
            issues.append(
                self.issue(
                    "material.poisson_ratio.range",
                    "Для лінійного ізотропного матеріалу має виконуватись -1 < ν < 0.5.",
                    affected=["material.poisson_ratio"],
                    question="Уточніть коректне значення коефіцієнта Пуассона ν.",
                    requires_user=True,
                )
            )
        elif p.value > 0.49:
            issues.append(
                self.issue(
                    "material.poisson_ratio.near_incompressible",
                    "ν близький до 0.5; майже нестисливий матеріал може потребувати спеціальної дискретизації.",
                    severity=IssueSeverity.WARNING,
                    kind=IssueKind.WARNING,
                    affected=["material.poisson_ratio"],
                )
            )

        if young is not None and (young < 0.1 or young > 10_000_000):
            issues.append(
                self.issue(
                    "material.young_modulus.suspicious",
                    "Модуль Юнга має нетиповий порядок величини; перевірте значення та одиниці.",
                    severity=IssueSeverity.WARNING,
                    kind=IssueKind.WARNING,
                    affected=["material.young_modulus"],
                    question="Підтвердіть значення і одиницю модуля Юнга.",
                    requires_user=True,
                )
            )
        if rho is not None and rho > 100_000:
            issues.append(
                self.issue(
                    "material.density.suspicious",
                    "Густина має нетипово велике значення; перевірте одиниці.",
                    severity=IssueSeverity.WARNING,
                    kind=IssueKind.WARNING,
                    affected=["material.density"],
                    question="Підтвердіть значення та одиницю густини.",
                    requires_user=True,
                )
            )
        return issues
