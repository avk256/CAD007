from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from .common import TaskIntent
from .geometry import GeometrySpec
from .planning import ClarificationRecord
from .simulation import StructuralAnalysisSpec
from .validation import ValidationReport


class UnifiedModelSpecification(BaseModel):
    version: str = "2.0"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    original_request: str
    task_intent: TaskIntent
    geometry: GeometrySpec
    structural_analysis: Optional[StructuralAnalysisSpec] = None
    clarifications: list[ClarificationRecord] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    validation_report: ValidationReport
