from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .common import PlannerIssue, QuantityParameter


class MaterialModel(str, Enum):
    LINEAR_ISOTROPIC = "linear_isotropic"


class MaterialSpec(BaseModel):
    name: str = "unspecified material"
    model: MaterialModel = MaterialModel.LINEAR_ISOTROPIC
    density: QuantityParameter = Field(
        default_factory=lambda: QuantityParameter(name="density", required=True)
    )
    young_modulus: QuantityParameter = Field(
        default_factory=lambda: QuantityParameter(name="young_modulus", required=True)
    )
    poisson_ratio: QuantityParameter = Field(
        default_factory=lambda: QuantityParameter(name="poisson_ratio", unit="1", required=True)
    )
    unresolved_issues: list[PlannerIssue] = Field(default_factory=list)
