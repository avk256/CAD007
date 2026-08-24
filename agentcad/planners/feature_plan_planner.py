from __future__ import annotations

import json
from typing import Any, Optional

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from agentcad.llm.prompt_loader import load_prompt
from agentcad.models.feature_plan import GeometryFeaturePlan


class FeaturePlanPlanner:
    """LLM creates typed CAD IR, never executable Python."""

    def __init__(self, model):
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=load_prompt("feature_plan_planner.txt")),
            ("human", "VALIDATED ENGINEERING MODEL:\n{model}\n\nPREVIOUS FEATURE PLAN:\n{previous_plan}\n\nDETERMINISTIC FAILURE FEEDBACK:\n{failure_feedback}"),
        ])
        self._chain = prompt | model.with_structured_output(GeometryFeaturePlan)

    def plan(self, engineering_model: dict[str, Any], previous_plan: Optional[dict[str, Any]] = None, failure_feedback: Optional[dict[str, Any]] = None) -> GeometryFeaturePlan:
        return self._chain.invoke({
            "model": json.dumps(engineering_model, ensure_ascii=False, indent=2),
            "previous_plan": json.dumps(previous_plan or {}, ensure_ascii=False, indent=2),
            "failure_feedback": json.dumps(failure_feedback or {}, ensure_ascii=False, indent=2),
        })
