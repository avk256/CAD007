from __future__ import annotations

import operator
from typing import Annotated, Any, NotRequired, TypedDict


class AgentCADState(TypedDict):
    # User input and configuration
    original_request: str
    perform_structural_analysis: bool
    task_intent: str
    output_dir: str
    max_planning_iterations: int
    max_code_attempts: int

    # Unified planning loop
    geometry_spec: NotRequired[dict[str, Any]]
    structural_spec: NotRequired[dict[str, Any]]
    validation_report: NotRequired[dict[str, Any]]
    pending_questions: NotRequired[list[dict[str, Any]]]
    clarifications: Annotated[list[dict[str, Any]], operator.add]
    planning_iteration: int
    failure_feedback: NotRequired[dict[str, Any]]

    # Frozen planning contract
    unified_specification: NotRequired[dict[str, Any]]

    # Code generation / execution
    code_attempt: int
    generated_code: NotRequired[str]
    code_summary: NotRequired[str]
    execution_result: NotRequired[dict[str, Any]]

    # Inspection
    stl_inspection: NotRequired[dict[str, Any]]
    fem_inspection: NotRequired[dict[str, Any]]
    failure_class: NotRequired[str]

    # Final state
    final_success: bool
    final_reason: NotRequired[str]
    events: Annotated[list[str], operator.add]
