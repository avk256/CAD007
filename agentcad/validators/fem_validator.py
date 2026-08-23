from __future__ import annotations

from agentcad.models.boundary_conditions import BoundaryConditionType
from agentcad.models.common import IssueKind, IssueSeverity
from agentcad.models.simulation import StructuralAnalysisSpec
from agentcad.models.validation import ValidationIssue
from .base import ValidatorBase


class FEMValidator(ValidatorBase):
    module_name = "fem"

    def validate(self, spec: StructuralAnalysisSpec) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not spec.loads:
            prescribed = any(
                bc.bc_type == BoundaryConditionType.PRESCRIBED_DISPLACEMENT
                for bc in spec.boundary_conditions
            )
            if not prescribed:
                issues.append(self.issue(
                    "fem.no_load",
                    "Не задано навантаження або ненульове задане переміщення.",
                    kind=IssueKind.MISSING,
                    affected=["loads"],
                    question="Яке навантаження діє на конструкцію?",
                    requires_user=True,
                ))

        # Conservative warning: the exact rank of the constraint system can only be
        # established after mapping conditions to the FE model.
        if spec.boundary_conditions and all(
            bc.bc_type != BoundaryConditionType.FIXED for bc in spec.boundary_conditions
        ):
            issues.append(self.issue(
                "fem.rigid_body_risk",
                "Закріплення не містять повністю фіксованої області; необхідно перевірити усунення рухів твердого тіла.",
                severity=IssueSeverity.WARNING,
                kind=IssueKind.WARNING,
                affected=["boundary_conditions"],
            ))
        return issues
