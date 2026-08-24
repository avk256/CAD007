from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EngineSettings:
    llm_provider: str = "openrouter"
    llm_model: str = "openai/gpt-5.5"
    llm_temperature: float = 0.0
    output_root: Path = Path("./agentcad_outputs")
    max_planning_iterations: int = 4
    max_feature_plan_attempts: int = 3
    gmsh_executable: str = "gmsh"
    calculix_executable: str = "ccx"
    solver_timeout_seconds: int = 600

    @classmethod
    def from_env(cls) -> "EngineSettings":
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "openrouter"),
            llm_model=os.getenv("LLM_MODEL", "openai/gpt-5.5"),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0")),
            output_root=Path(os.getenv("AGENTCAD_OUTPUT_ROOT", "./agentcad_outputs")),
            max_planning_iterations=int(os.getenv("AGENTCAD_MAX_PLANNING_ITERATIONS", "4")),
            max_feature_plan_attempts=int(os.getenv("AGENTCAD_MAX_FEATURE_PLAN_ATTEMPTS", "3")),
            gmsh_executable=os.getenv("GMSH_EXECUTABLE", "gmsh"),
            calculix_executable=os.getenv("CALCULIX_EXECUTABLE", "ccx"),
            solver_timeout_seconds=int(os.getenv("AGENTCAD_SOLVER_TIMEOUT", "600")),
        )
