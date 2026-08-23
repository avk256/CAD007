from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ClarificationQuestion(BaseModel):
    id: str
    category: str
    question: str
    explanation: Optional[str] = None
    affected_parameters: list[str] = Field(default_factory=list)
    choices: list[str] = Field(default_factory=list)


class ClarificationRecord(BaseModel):
    iteration: int
    questions: list[ClarificationQuestion] = Field(default_factory=list)
    answer: Any


class PlanningFeedback(BaseModel):
    source: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
