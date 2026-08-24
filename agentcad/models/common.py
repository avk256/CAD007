from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskIntent(str, Enum):
    GEOMETRY_ONLY = "geometry_only"
    GEOMETRY_AND_STRUCTURAL_ANALYSIS = "geometry_and_structural_analysis"


class ParameterSource(str, Enum):
    USER_EXPLICIT = "user_explicit"
    INFERRED = "inferred"
    DEFAULT = "default"
    UNDEFINED = "undefined"


class ValidationStatus(str, Enum):
    VALID = "valid"
    VALID_WITH_WARNINGS = "valid_with_warnings"
    NEEDS_CLARIFICATION = "needs_clarification"
    CONFLICT = "conflict"
    UNSUPPORTED = "unsupported"


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class IssueKind(str, Enum):
    MISSING = "missing"
    INVALID = "invalid"
    CONFLICT = "conflict"
    UNSUPPORTED = "unsupported"
    WARNING = "warning"


class QuantityParameter(BaseModel):
    """Numeric engineering parameter with explicit provenance and units."""

    name: str
    value: Optional[float] = None
    unit: Optional[str] = None
    source: ParameterSource = ParameterSource.UNDEFINED
    required: bool = True
    explanation: Optional[str] = None
    notes: Optional[str] = None


class Vector3(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class Dimensions3D(BaseModel):
    x: float = Field(gt=0)
    y: float = Field(gt=0)
    z: float = Field(gt=0)


class PlannerIssue(BaseModel):
    code: str
    message: str
    kind: IssueKind = IssueKind.INVALID
    affected_parameters: list[str] = Field(default_factory=list)
    suggested_question: Optional[str] = None
    explanation: Optional[str] = None
