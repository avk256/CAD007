from __future__ import annotations

from enum import Enum

from agentcad.models.artifacts import ExecutionResult, FEMInspectionReport, STLInspectionReport


class FailureClass(str, Enum):
    CODE_IMPLEMENTATION = "code_implementation"
    GEOMETRY_IMPLEMENTATION = "geometry_implementation"
    MODEL_SPECIFICATION = "model_specification"
    UNKNOWN = "unknown"


class FailureClassifier:
    """Deterministic routing heuristic; can later be augmented by an LLM classifier."""

    _MODEL_MARKERS = (
        "singular", "zero pivot", "rigid body", "unconstrained", "boundary condition",
    )

    def classify(
        self,
        execution: ExecutionResult | None = None,
        stl: STLInspectionReport | None = None,
        fem: FEMInspectionReport | None = None,
    ) -> FailureClass:
        if execution is not None and not execution.success:
            return FailureClass.CODE_IMPLEMENTATION
        if stl is not None and not stl.passed:
            return FailureClass.GEOMETRY_IMPLEMENTATION
        if fem is not None and not fem.passed:
            text = " ".join(fem.errors + fem.warnings).lower()
            if any(marker in text for marker in self._MODEL_MARKERS):
                return FailureClass.MODEL_SPECIFICATION
            return FailureClass.CODE_IMPLEMENTATION
        return FailureClass.UNKNOWN
