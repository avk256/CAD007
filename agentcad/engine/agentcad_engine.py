from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agentcad.config.settings import EngineSettings
from agentcad.executors.freecad_executor import FreeCADExecutor
from agentcad.generators.code_generator import CodeGenerator
from agentcad.inspectors.failure_classifier import FailureClassifier
from agentcad.inspectors.fem_result_inspector import FEMResultInspector
from agentcad.inspectors.stl_inspector import STLInspector
from agentcad.llm.model_factory import ModelFactory
from agentcad.models.common import TaskIntent
from agentcad.planners.clarification_manager import ClarificationManager
from agentcad.planners.geometry_planner import GeometryPlanner
from agentcad.planners.parameter_explainer import ParameterExplainer
from agentcad.planners.structural_analysis_planner import StructuralAnalysisPlanner
from agentcad.validators.unified_consistency_validator import UnifiedConsistencyValidator
from .graph_builder import GraphBuilder
from .result import EngineRunResult, EngineRunStatus


class AgentCADEngine:
    """Single public orchestration API used by Streamlit/CLI/other frontends."""

    def __init__(
        self,
        settings: Optional[EngineSettings] = None,
        *,
        model=None,
        checkpointer=None,
    ):
        load_dotenv()
        self.settings = settings or EngineSettings.from_env()
        self.settings.output_root = self.settings.output_root.expanduser().resolve()
        self.settings.output_root.mkdir(parents=True, exist_ok=True)

        self.model = model or ModelFactory.create(self.settings)
        self.geometry_planner = GeometryPlanner(self.model)
        self.structural_planner = StructuralAnalysisPlanner(self.model)
        self.validator = UnifiedConsistencyValidator()
        self.explainer = ParameterExplainer()
        self.clarification_manager = ClarificationManager(self.explainer)
        self.code_generator = CodeGenerator(self.model)
        self.executor = FreeCADExecutor(
            freecad_cmd=self.settings.freecad_cmd,
            timeout_seconds=self.settings.freecad_timeout_seconds,
        )
        self.stl_inspector = STLInspector(
            relative_tolerance=self.settings.bbox_relative_tolerance,
            absolute_tolerance_mm=self.settings.bbox_absolute_tolerance_mm,
        )
        self.fem_inspector = FEMResultInspector()
        self.failure_classifier = FailureClassifier()
        self.checkpointer = checkpointer or InMemorySaver()

        self.graph = GraphBuilder(
            geometry_planner=self.geometry_planner,
            structural_planner=self.structural_planner,
            validator=self.validator,
            clarification_manager=self.clarification_manager,
            code_generator=self.code_generator,
            executor=self.executor,
            stl_inspector=self.stl_inspector,
            fem_inspector=self.fem_inspector,
            failure_classifier=self.failure_classifier,
        ).build(self.checkpointer)

    @staticmethod
    def _config(thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}

    def start(
        self,
        description: str,
        *,
        perform_structural_analysis: bool = False,
        thread_id: Optional[str] = None,
        output_dir: Optional[str | Path] = None,
    ) -> EngineRunResult:
        description = description.strip()
        if not description:
            raise ValueError("description must not be empty")

        thread_id = thread_id or str(uuid.uuid4())
        if output_dir is None:
            output_dir = self.settings.output_root / f"run_{thread_id}"
        output_dir = Path(output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        intent = (
            TaskIntent.GEOMETRY_AND_STRUCTURAL_ANALYSIS
            if perform_structural_analysis else TaskIntent.GEOMETRY_ONLY
        )
        initial_state = {
            "original_request": description,
            "perform_structural_analysis": perform_structural_analysis,
            "task_intent": intent.value,
            "output_dir": str(output_dir),
            "max_planning_iterations": self.settings.max_planning_iterations,
            "max_code_attempts": self.settings.max_code_attempts,
            "clarifications": [],
            "planning_iteration": 0,
            "code_attempt": 0,
            "final_success": False,
            "events": [],
        }
        result = self.graph.invoke(
            initial_state,
            config=self._config(thread_id),
            version="v2",
        )
        return self._run_result(thread_id, result)

    def resume(self, thread_id: str, answer: Any) -> EngineRunResult:
        result = self.graph.invoke(
            Command(resume=answer),
            config=self._config(thread_id),
            version="v2",
        )
        return self._run_result(thread_id, result)

    def get_state(self, thread_id: str) -> dict[str, Any]:
        snapshot = self.graph.get_state(self._config(thread_id))
        return dict(snapshot.values or {})

    def get_result(self, thread_id: str) -> dict[str, Any]:
        return self.get_state(thread_id)

    def get_artifacts(self, thread_id: str) -> dict[str, Any]:
        state = self.get_state(thread_id)
        execution = state.get("execution_result", {})
        return execution.get("artifacts", {}) if isinstance(execution, dict) else {}

    def stream_updates(self, inputs: dict[str, Any], thread_id: str):
        """Low-level optional API for alternative UIs that want LangGraph updates."""
        yield from self.graph.stream(
            inputs,
            config=self._config(thread_id),
            stream_mode="updates",
            version="v2",
        )

    def _run_result(self, thread_id: str, graph_output) -> EngineRunResult:
        state = dict(graph_output.value or {})
        if graph_output.interrupts:
            payload = graph_output.interrupts[0].value
            questions = []
            if isinstance(payload, dict):
                questions = payload.get("questions", []) or []
            return EngineRunResult(
                thread_id=thread_id,
                status=EngineRunStatus.NEEDS_INPUT,
                state=state,
                questions=questions,
                interrupt_payload=payload,
                message="AgentCAD requires clarification before continuing.",
            )
        if state.get("final_success"):
            return EngineRunResult(
                thread_id=thread_id,
                status=EngineRunStatus.COMPLETED,
                state=state,
                message=state.get("final_reason", "Completed."),
            )
        return EngineRunResult(
            thread_id=thread_id,
            status=EngineRunStatus.FAILED,
            state=state,
            message=state.get("final_reason", "AgentCAD failed."),
        )
