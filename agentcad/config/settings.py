from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class EngineSettings:
    llm_provider: str = "openrouter"
    llm_model: str = ""
    llm_temperature: float = 0.0
    freecad_cmd: Optional[str] = None
    freecad_timeout_seconds: int = 300
    max_planning_iterations: int = 5
    max_code_attempts: int = 3
    output_root: Path = Path("./agentcad_runs")
    bbox_relative_tolerance: float = 0.01
    bbox_absolute_tolerance_mm: float = 0.15

    @classmethod
    def from_env(cls) -> "EngineSettings":
        provider = os.getenv("LLM_PROVIDER", "openrouter").strip().lower()
        model = os.getenv("LLM_MODEL", "").strip()
        if not model:
            model = "openai/gpt-5.5" if provider == "openrouter" else "gpt-5.5"
        return cls(
            llm_provider=provider,
            llm_model=model,
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
            freecad_cmd=os.getenv("FREECAD_CMD") or None,
            freecad_timeout_seconds=int(os.getenv("FREECAD_TIMEOUT", "300")),
            max_planning_iterations=int(os.getenv("MAX_PLANNING_ITERATIONS", "5")),
            max_code_attempts=int(os.getenv("MAX_CODE_ATTEMPTS", "3")),
            output_root=Path(os.getenv("AGENTCAD_OUTPUT_ROOT", "./agentcad_runs")),
        )
