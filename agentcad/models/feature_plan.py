from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .geometry import RegionKind


class FeatureOperation(str, Enum):
    BOX = "box"
    CYLINDER = "cylinder"
    CONE = "cone"
    SPHERE = "sphere"
    EXTRUDE = "extrude"
    REVOLVE = "revolve"
    HOLE = "hole"
    CUT = "cut"
    FUSE = "fuse"
    INTERSECT = "intersect"
    FILLET = "fillet"
    CHAMFER = "chamfer"
    TRANSLATE = "translate"
    ROTATE = "rotate"
    MIRROR = "mirror"
    LINEAR_PATTERN = "linear_pattern"
    CIRCULAR_PATTERN = "circular_pattern"


class RegionSelectorType(str, Enum):
    CADQUERY = "cadquery"
    EXTREME = "extreme"
    SURFACE_TYPE = "surface_type"
    SOURCE_FEATURE = "source_feature"


class RegionSelector(BaseModel):
    """Deterministic rule used to resolve a semantic region on the final B-Rep."""

    selector_type: RegionSelectorType = RegionSelectorType.CADQUERY
    expression: Optional[str] = Field(
        default=None,
        description="CadQuery selector such as >Z, <X, %Cylinder, |Z, or a compound selector.",
    )
    axis: Optional[str] = Field(default=None, description="X, Y or Z for extreme selectors.")
    side: Optional[str] = Field(default=None, description="min or max for extreme selectors.")
    surface_type: Optional[str] = Field(default=None, description="PLANE, CYLINDER, CONE, SPHERE, TORUS.")
    expected_count: Optional[int] = Field(default=None, ge=1)
    tolerance: float = Field(default=1e-6, gt=0)


class SemanticRegionRule(BaseModel):
    name: str
    kind: RegionKind
    description: str = ""
    selector: RegionSelector
    source_feature: Optional[str] = None


class FeatureStep(BaseModel):
    id: str
    operation: FeatureOperation
    description: str = ""
    target: Optional[str] = Field(default=None, description="Primary upstream feature id.")
    inputs: list[str] = Field(default_factory=list, description="Input feature ids for booleans/compound operations.")
    parameters: dict[str, Any] = Field(default_factory=dict)


class GeometryFeaturePlan(BaseModel):
    version: str = "3.0"
    units: str = "mm"
    root_feature: str
    steps: list[FeatureStep]
    semantic_regions: list[SemanticRegionRule] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    def step_map(self) -> dict[str, FeatureStep]:
        return {step.id: step for step in self.steps}
