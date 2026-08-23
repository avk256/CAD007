from __future__ import annotations

import json
from typing import Any, Optional

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from agentcad.llm.prompt_loader import load_prompt
from agentcad.models.simulation import StructuralAnalysisSpec


class StructuralAnalysisPlanner:
    """LLM-backed planner for a supported linear-static FEM formulation."""

    def __init__(self, model):
        # External prompt files are literal messages. This prevents JSON or
        # Python braces in prompt text from being interpreted as template vars.
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=load_prompt("structural_analysis_planner.txt")),
                (
                    "human",
                    """ORIGINAL REQUEST:
{request}

GEOMETRY SPEC:
{geometry_spec}

CLARIFICATION HISTORY:
{clarifications}

PREVIOUS STRUCTURAL SPEC:
{previous_spec}

FAILURE FEEDBACK:
{failure_feedback}
""",
                ),
            ]
        )
        self._chain = prompt | model.with_structured_output(StructuralAnalysisSpec)

    def plan(
        self,
        request: str,
        geometry_spec: dict[str, Any],
        clarifications: list[dict[str, Any]],
        enabled: bool,
        previous_spec: Optional[dict[str, Any]] = None,
        failure_feedback: Optional[dict[str, Any]] = None,
    ) -> StructuralAnalysisSpec:
        if not enabled:
            return StructuralAnalysisSpec(enabled=False)

        result = self._chain.invoke(
            {
                "request": request,
                "geometry_spec": json.dumps(geometry_spec, ensure_ascii=False, indent=2),
                "clarifications": json.dumps(clarifications, ensure_ascii=False, indent=2),
                "previous_spec": json.dumps(previous_spec or {}, ensure_ascii=False, indent=2),
                "failure_feedback": json.dumps(failure_feedback or {}, ensure_ascii=False, indent=2),
            }
        )
        result.enabled = True
        return result
