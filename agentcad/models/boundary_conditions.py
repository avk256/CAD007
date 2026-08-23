from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .common import QuantityParameter


class BoundaryConditionType(str, Enum):
    FIXED = "fixed"
    PRESCRIBED_DISPLACEMENT = "prescribed_displacement"


class DegreeOfFreedom(str, Enum):
    UX = "Ux"
    UY = "Uy"
    UZ = "Uz"
    RX = "Rx"
    RY = "Ry"
    RZ = "Rz"


class BoundaryConditionSpec(BaseModel):
    id: str
    bc_type: BoundaryConditionType
    target_region: str
    constrained_dofs: list[DegreeOfFreedom] = Field(default_factory=list)
    values: dict[str, QuantityParameter] = Field(default_factory=dict)
    coordinate_system: str = "global"
    description: str = ""
