from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class AgentCADState(TypedDict, total=False):
    request: str
    thread_id: str
    perform_structural_analysis: bool
    task_intent: str
    clarification_round: int
    max_planning_iterations: int
    clarifications: list[dict[str, Any]]

    geometry_spec: dict[str, Any]
    structural_analysis: dict[str, Any] | None
    validation_report: dict[str, Any]
    unified_model: dict[str, Any]
    clarification_questions: list[dict[str, Any]]

    feature_plan: dict[str, Any]
    feature_plan_attempts: int
    feature_plan_validation: dict[str, Any]
    geometry_inspection: dict[str, Any]

    artifacts: dict[str, Any]
    mesh_result: dict[str, Any]
    solver_result: dict[str, Any]
    simulation_summary: dict[str, Any]

    failure: dict[str, Any] | None
    output_dir: str
    status: str

    # Reducers preserve the complete protocol instead of overwriting the
    # previous node's messages on each LangGraph transition.
    events: Annotated[list[str], operator.add]
    diagnostics: Annotated[list[dict[str, Any]], operator.add]
