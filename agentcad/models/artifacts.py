from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ArtifactManifest(BaseModel):
    stl: list[str] = Field(default_factory=list)
    step: list[str] = Field(default_factory=list)
    fcstd: list[str] = Field(default_factory=list)
    python: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    fem: list[str] = Field(default_factory=list)
    other: list[str] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    success: bool = False
    return_code: int = -1
    stdout: str = ""
    stderr: str = ""
    reason: str = ""
    command: list[str] = Field(default_factory=list)
    script_path: Optional[str] = None
    artifacts: ArtifactManifest = Field(default_factory=ArtifactManifest)


class STLInspectionReport(BaseModel):
    passed: bool = False
    stl_path: Optional[str] = None
    triangle_count: int = 0
    dimensions_mm: list[float] = Field(default_factory=list)
    bbox_min_mm: list[float] = Field(default_factory=list)
    bbox_max_mm: list[float] = Field(default_factory=list)
    surface_area_mm2: Optional[float] = None
    degenerate_triangles: int = 0
    checks: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class FEMInspectionReport(BaseModel):
    passed: bool = False
    summary_path: Optional[str] = None
    result_files: list[str] = Field(default_factory=list)
    checks: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
