from __future__ import annotations

from agentcad.models.common import IssueKind, IssueSeverity
from agentcad.models.geometry import GeometrySpec
from agentcad.models.validation import ValidationIssue
from .base import ValidatorBase


class GeometryValidator(ValidatorBase):
    module_name = "geometry"

    def validate(self, spec: GeometrySpec) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        for item in spec.unresolved_issues:
            issues.append(
                self.issue(
                    f"planner.{item.code}",
                    item.message,
                    kind=item.kind,
                    affected=item.affected_parameters,
                    explanation=item.explanation,
                    question=item.suggested_question,
                    requires_user=item.kind in {IssueKind.MISSING, IssueKind.CONFLICT, IssueKind.INVALID},
                )
            )

        if not spec.features:
            issues.append(
                self.issue(
                    "geometry.no_features",
                    "GeometryPlanner не визначив жодної геометричної ознаки.",
                    kind=IssueKind.MISSING,
                    affected=["geometry.features"],
                    question="Уточніть основну форму та розміри деталі.",
                    requires_user=True,
                )
            )

        names = [r.name for r in spec.semantic_regions]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            issues.append(
                self.issue(
                    "geometry.duplicate_regions",
                    f"Повторюються семантичні області: {', '.join(duplicates)}.",
                    kind=IssueKind.CONFLICT,
                    affected=["geometry.semantic_regions"],
                    question="Уточніть або перейменуйте неоднозначні геометричні області.",
                    requires_user=False,
                )
            )

        if spec.overall_dimensions_mm:
            dims = spec.overall_dimensions_mm
            if min(dims.x, dims.y, dims.z) <= 0:
                issues.append(
                    self.issue(
                        "geometry.invalid_bbox",
                        "Габаритні розміри повинні бути додатними.",
                        affected=["geometry.overall_dimensions_mm"],
                        requires_user=True,
                    )
                )
        return issues
