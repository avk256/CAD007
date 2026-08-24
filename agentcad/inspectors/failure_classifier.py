from __future__ import annotations

from typing import Any


class FailureClassifier:
    """Classify failures so the UI and repair loop expose the right layer."""

    def classify(self, error: Exception | str, stage: str | None = None) -> dict[str, Any]:
        message = str(error)
        text = message.lower()
        stage_text = (stage or "").lower()

        if (
            "validation error" in text
            or "model_type" in text
            or "structured output" in text
            or "pydantic" in text
            or "planner" in stage_text
        ):
            category = "planning_output_failure"
        elif any(k in text for k in ("feature", "cadquery", "boolean", "fillet", "chamfer", "selector", "geometry")):
            category = "feature_plan_failure"
        elif any(k in text for k in ("gmsh", "mesh", "tetra")):
            category = "mesh_failure"
        elif any(k in text for k in ("singular", "zero pivot", "rigid body", "constraint", "boundary condition")):
            category = "model_definition_failure"
        elif any(k in text for k in ("calculix", "ccx", "solver", "convergence")):
            category = "solver_failure"
        else:
            category = "infrastructure_failure"

        return {
            "category": category,
            "stage": stage,
            "message": message,
            "exception_type": type(error).__name__ if isinstance(error, Exception) else None,
        }
