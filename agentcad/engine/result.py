from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EngineRunStatus(str, Enum):
    NEEDS_INPUT = "needs_input"
    COMPLETED = "completed"
    FAILED = "failed"


class EngineRunResult(BaseModel):
    thread_id: str
    status: EngineRunStatus
    state: dict[str, Any] = Field(default_factory=dict)
    questions: list[dict[str, Any]] = Field(default_factory=list)
    interrupt_payload: Optional[Any] = None
    message: str = ""
