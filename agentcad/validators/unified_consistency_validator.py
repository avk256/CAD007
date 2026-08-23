from __future__ import annotations

from agentcad.models.common import IssueKind, IssueSeverity, TaskIntent, ValidationStatus
from agentcad.models.geometry import GeometrySpec
from agentcad.models.simulation import StructuralAnalysisSpec
from agentcad.models.validation import ValidationIssue, ValidationReport
from .geometry_validator import GeometryValidator
from .material_validator import MaterialValidator
from .boundary_condition_validator import BoundaryConditionValidator
from .load_validator import LoadValidator
from .mesh_validator import MeshValidator
from .fem_validator import FEMValidator


class UnifiedConsistencyValidator:
    """Deterministic validation of geometry + FEM formulation as one contract."""

    def __init__(self):
        self.geometry = GeometryValidator()
        self.material = MaterialValidator()
        self.boundary_conditions = BoundaryConditionValidator()
        self.loads = LoadValidator()
        self.mesh = MeshValidator()
        self.fem = FEMValidator()

    def validate(
        self,
        geometry: GeometrySpec,
        structural: StructuralAnalysisSpec,
        task_intent: TaskIntent,
    ) -> ValidationReport:
        issues: list[ValidationIssue] = []
        issues.extend(self.geometry.validate(geometry))

        if task_intent == TaskIntent.GEOMETRY_AND_STRUCTURAL_ANALYSIS:
            if not structural.enabled:
                issues.append(ValidationIssue(
                    code="structural.disabled",
                    message="Запитано розрахунок НДС, але StructuralAnalysisSpec вимкнений.",
                    severity=IssueSeverity.ERROR,
                    kind=IssueKind.CONFLICT,
                    module="unified",
                    affected_parameters=["structural_analysis"],
                    suggested_question="Підтвердіть, що потрібно виконувати лінійний статичний розрахунок НДС.",
                    requires_user=True,
                ))
            else:
                semantic_regions = {r.name for r in geometry.semantic_regions}
                for item in structural.unresolved_issues:
                    issues.append(ValidationIssue(
                        code=f"structural.planner.{item.code}",
                        message=item.message,
                        severity=IssueSeverity.ERROR,
                        kind=item.kind,
                        module="structural_planner",
                        affected_parameters=item.affected_parameters,
                        explanation=item.explanation,
                        suggested_question=item.suggested_question,
                        requires_user=item.kind in {IssueKind.MISSING, IssueKind.CONFLICT, IssueKind.INVALID},
                    ))
                issues.extend(self.material.validate(structural.material))
                issues.extend(self.boundary_conditions.validate(structural.boundary_conditions, semantic_regions))
                issues.extend(self.loads.validate(structural.loads, semantic_regions))
                issues.extend(self.mesh.validate(structural.mesh, semantic_regions))
                issues.extend(self.fem.validate(structural))

        status = self._status(issues)
        return ValidationReport(status=status, issues=issues)

    @staticmethod
    def _status(issues: list[ValidationIssue]) -> ValidationStatus:
        if any(i.kind == IssueKind.UNSUPPORTED for i in issues):
            return ValidationStatus.UNSUPPORTED
        if any(i.kind == IssueKind.CONFLICT and i.severity == IssueSeverity.ERROR for i in issues):
            return ValidationStatus.CONFLICT
        if any(i.requires_user for i in issues):
            return ValidationStatus.NEEDS_CLARIFICATION
        if any(i.severity == IssueSeverity.ERROR for i in issues):
            return ValidationStatus.NEEDS_CLARIFICATION
        if any(i.severity == IssueSeverity.WARNING for i in issues):
            return ValidationStatus.VALID_WITH_WARNINGS
        return ValidationStatus.VALID
