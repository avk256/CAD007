from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentCADResult(BaseModel):
    """Public result returned to Streamlit/CLI.

    v3 keeps the compact high-level fields used by the initial prototype, but
    also exposes the complete orchestration state and diagnostic event stream.
    This is intentional: a failed engineering run must remain inspectable.
    """

    status: str
    message: str = ""
    thread_id: str | None = None
    output_dir: str | None = None
    original_request: str | None = None
    perform_structural_analysis: bool = False
    clarification_round: int = 0
    clarifications: list[dict[str, Any]] = Field(default_factory=list)

    unified_model: dict[str, Any] | None = None
    validation_report: dict[str, Any] | None = None
    feature_plan: dict[str, Any] | None = None
    feature_plan_validation: dict[str, Any] | None = None
    geometry_inspection: dict[str, Any] | None = None
    simulation_summary: dict[str, Any] | None = None

    artifacts: dict[str, Any] = Field(default_factory=dict)
    clarification_questions: list[dict[str, Any]] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
    failure: dict[str, Any] | None = None
