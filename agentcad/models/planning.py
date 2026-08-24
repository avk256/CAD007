from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ClarificationQuestion(BaseModel):
    id: str
    question: str
    path: str = ""
    explanation: str | None = None


class ClarificationRecord(BaseModel):
    question_id: str
    answer: Any
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
