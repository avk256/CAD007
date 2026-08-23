from __future__ import annotations

from agentcad.models.boundary_conditions import BoundaryConditionSpec, BoundaryConditionType
from agentcad.models.common import IssueKind
from agentcad.models.validation import ValidationIssue
from .base import ValidatorBase


class BoundaryConditionValidator(ValidatorBase):
    module_name = "boundary_conditions"

    def validate(
        self,
        conditions: list[BoundaryConditionSpec],
        semantic_regions: set[str],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not conditions:
            issues.append(
                self.issue(
                    "bc.missing",
                    "Для статичного розрахунку не задано жодної умови закріплення.",
                    kind=IssueKind.MISSING,
                    affected=["boundary_conditions"],
                    question="Які області конструкції потрібно закріпити і які переміщення обмежити?",
                    requires_user=True,
                )
            )
            return issues

        for bc in conditions:
            if bc.target_region not in semantic_regions:
                issues.append(
                    self.issue(
                        f"bc.{bc.id}.target",
                        f"Область закріплення {bc.target_region!r} відсутня у GeometrySpec.",
                        kind=IssueKind.CONFLICT,
                        affected=["boundary_conditions", "geometry.semantic_region"],
                        question=(
                            f"Уточніть, яка геометрична область відповідає закріпленню {bc.id}; "
                            f"зараз вказано {bc.target_region!r}."
                        ),
                        requires_user=True,
                    )
                )
            if bc.bc_type == BoundaryConditionType.PRESCRIBED_DISPLACEMENT and not bc.constrained_dofs:
                issues.append(
                    self.issue(
                        f"bc.{bc.id}.dofs",
                        "Для заданого переміщення не вказані ступені свободи.",
                        kind=IssueKind.MISSING,
                        affected=["boundary_conditions"],
                        question=f"Які компоненти переміщення потрібно задати для умови {bc.id}?",
                        requires_user=True,
                    )
                )
        return issues
