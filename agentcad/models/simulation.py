from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .boundary_conditions import BoundaryConditionSpec
from .common import PlannerIssue
from .loads import LoadSpec
from .material import MaterialSpec
from .mesh import MeshSpec


class AnalysisType(str, Enum):
    LINEAR_STATIC = "linear_static"


class SolverType(str, Enum):
    CALCULIX = "calculix"


class StructuralAnalysisSpec(BaseModel):
    enabled: bool = False
    analysis_type: AnalysisType = AnalysisType.LINEAR_STATIC
    material: MaterialSpec = Field(default_factory=MaterialSpec)
    boundary_conditions: list[BoundaryConditionSpec] = Field(default_factory=list)
    loads: list[LoadSpec] = Field(default_factory=list)
    mesh: MeshSpec = Field(default_factory=MeshSpec)
    solver: SolverType = SolverType.CALCULIX
    assumptions: list[str] = Field(default_factory=list)
    unresolved_issues: list[PlannerIssue] = Field(default_factory=list)
