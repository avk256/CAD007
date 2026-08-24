from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GeometryInspectionReport(BaseModel):
    valid: bool
    shape_type: str
    solids: int
    faces: int
    edges: int
    volume_mm3: float
    area_mm2: float
    bbox_mm: dict[str, float]
    center_mm: dict[str, float]
    semantic_regions: dict[str, dict[str, Any]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class SimulationResultSummary(BaseModel):
    success: bool = False
    solver: str = "CalculiX"
    analysis_type: str = "linear_static"
    max_displacement: float | None = None
    max_von_mises: float | None = None
    notes: list[str] = Field(default_factory=list)
