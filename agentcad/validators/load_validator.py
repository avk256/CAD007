from __future__ import annotations

import math

from agentcad.models.common import IssueKind
from agentcad.models.loads import LoadSpec, LoadType
from agentcad.models.validation import ValidationIssue
from .base import ValidatorBase


_DIMENSIONS = {
    LoadType.FORCE: "force",
    LoadType.PRESSURE: "stress",
    LoadType.MOMENT: "moment",
    LoadType.GRAVITY: "acceleration",
}


class LoadValidator(ValidatorBase):
    module_name = "loads"

    def validate(self, loads: list[LoadSpec], semantic_regions: set[str]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for load in loads:
            sub, _ = self.validate_quantity(
                load.magnitude,
                path=f"loads.{load.id}.magnitude",
                dimension=_DIMENSIONS[load.load_type],
                positive=False,
                nonzero=True,
                required=True,
            )
            issues.extend(sub)

            if load.load_type != LoadType.GRAVITY:
                if not load.target_region:
                    issues.append(
                        self.issue(
                            f"loads.{load.id}.target_missing",
                            "Для навантаження не задано геометричну область.",
                            kind=IssueKind.MISSING,
                            affected=["loads", "geometry.semantic_region"],
                            question=f"До якої геометричної області прикласти навантаження {load.id}?",
                            requires_user=True,
                        )
                    )
                elif load.target_region not in semantic_regions:
                    issues.append(
                        self.issue(
                            f"loads.{load.id}.target_invalid",
                            f"Область {load.target_region!r} відсутня у GeometrySpec.",
                            kind=IssueKind.CONFLICT,
                            affected=["loads", "geometry.semantic_region"],
                            question=f"Уточніть область прикладання навантаження {load.id}.",
                            requires_user=True,
                        )
                    )

            if load.load_type in {LoadType.FORCE, LoadType.MOMENT, LoadType.GRAVITY}:
                d = load.direction
                if d is None or math.isclose(d.x*d.x + d.y*d.y + d.z*d.z, 0.0, abs_tol=1e-14):
                    issues.append(
                        self.issue(
                            f"loads.{load.id}.direction",
                            f"Для {load.load_type.value} не задано ненульовий напрямок.",
                            kind=IssueKind.MISSING,
                            affected=["loads.direction"],
                            question=f"У якому напрямку діє навантаження {load.id}?",
                            requires_user=True,
                        )
                    )
        return issues
