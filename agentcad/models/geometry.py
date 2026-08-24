from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .common import Dimensions3D, PlannerIssue


class RegionKind(str, Enum):
    SOLID = "solid"
    FACE = "face"
    EDGE = "edge"
    VERTEX = "vertex"
    SURFACE_SET = "surface_set"
    EDGE_SET = "edge_set"


class GeometryFeature(BaseModel):
    id: str
    feature_type: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    semantic_regions: list[str] = Field(default_factory=list)


class SemanticRegion(BaseModel):
    name: str = Field(description="Stable semantic name, never a transient Face1-style id.")
    kind: RegionKind
    description: str


class GeometrySpec(BaseModel):
    summary: str
    units: str = "mm"
    coordinate_system: str = "Right-handed Cartesian XYZ."
    overall_dimensions_mm: Optional[Dimensions3D] = None
    features: list[GeometryFeature] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)
    semantic_regions: list[SemanticRegion] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unresolved_issues: list[PlannerIssue] = Field(default_factory=list)
