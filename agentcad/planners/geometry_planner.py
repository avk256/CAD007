from __future__ import annotations

import json
from typing import Any, Optional

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from agentcad.llm.prompt_loader import load_prompt
from agentcad.models.geometry import GeometrySpec


class GeometryPlanner:
    def __init__(self, model):
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=load_prompt("geometry_planner.txt")),
            ("human", "ORIGINAL REQUEST:\n{request}\n\nCLARIFICATION HISTORY:\n{clarifications}\n\nPREVIOUS GEOMETRY SPEC:\n{previous_spec}\n\nFAILURE FEEDBACK:\n{failure_feedback}"),
        ])
        self._chain = prompt | model.with_structured_output(GeometrySpec)

    def plan(self, request: str, clarifications: list[dict[str, Any]], previous_spec: Optional[dict[str, Any]] = None, failure_feedback: Optional[dict[str, Any]] = None) -> GeometrySpec:
        return self._chain.invoke({
            "request": request,
            "clarifications": json.dumps(clarifications, ensure_ascii=False, indent=2),
            "previous_spec": json.dumps(previous_spec or {}, ensure_ascii=False, indent=2),
            "failure_feedback": json.dumps(failure_feedback or {}, ensure_ascii=False, indent=2),
        })
