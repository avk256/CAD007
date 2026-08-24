from __future__ import annotations

import traceback
import uuid
from pathlib import Path
from typing import Any

from agentcad.config.settings import EngineSettings
from agentcad.geometry import CadQueryGeometryCompiler, GeometryExporter, GeometryInspector
from agentcad.inspectors import FailureClassifier
from agentcad.llm.model_factory import create_chat_model
from agentcad.meshing.gmsh_adapter import GmshMeshAdapter
from agentcad.models.feature_plan import GeometryFeaturePlan
from agentcad.models.simulation import StructuralAnalysisSpec
from agentcad.planners.clarification_manager import ClarificationManager
from agentcad.solvers.calculix import CalculiXExecutor, CalculiXModelBuilder, CalculiXResultParser
from agentcad.storage import ArtifactStore
from agentcad.validators.feature_plan_validator import FeaturePlanValidator
from agentcad.validators.unified_consistency_validator import UnifiedConsistencyValidator

from .graph_builder import GraphBuilder
from .result import AgentCADResult


class AgentCADEngine:
    """Public orchestration facade for AgentCAD v3.

    The engine deliberately keeps the application-facing workflow similar to
    AgentCAD v2: start a run, inspect its complete state, and resume the same
    run after user clarification. v3 rebuilds the typed engineering model from
    the original request + accumulated clarification history, while preserving
    the same run directory and diagnostic protocol.
    """

    def __init__(self, settings: EngineSettings | None = None, model=None):
        self.settings = settings or EngineSettings.from_env()
        self.store = ArtifactStore(self.settings.output_root)

        self._model = model
        self.geometry_planner = None
        self.structural_planner = None
        self.feature_plan_planner = None
        self.clarification_manager = ClarificationManager()

        self.unified_validator = UnifiedConsistencyValidator()
        self.feature_plan_validator = FeaturePlanValidator()
        self.compiler = CadQueryGeometryCompiler()
        self.geometry_inspector = GeometryInspector()
        self.geometry_exporter = GeometryExporter()
        self.mesh_adapter = GmshMeshAdapter()
        self.calculix_builder = CalculiXModelBuilder()
        self.calculix_executor = CalculiXExecutor(
            executable=self.settings.calculix_executable,
            timeout_seconds=self.settings.solver_timeout_seconds,
        )
        self.result_parser = CalculiXResultParser()
        self.failure_classifier = FailureClassifier()
        self._graph = None

        # Streamlit uses a cached AgentCADEngine. Keeping lightweight run
        # contexts here gives v3 the same start/resume interaction pattern as
        # v2 without coupling the CAD/CAE core to a particular UI.
        self._run_contexts: dict[str, dict[str, Any]] = {}
        self._last_results: dict[str, AgentCADResult] = {}

    def _ensure_planners(self) -> None:
        if self.geometry_planner is not None:
            return
        from agentcad.planners.feature_plan_planner import FeaturePlanPlanner
        from agentcad.planners.geometry_planner import GeometryPlanner
        from agentcad.planners.structural_analysis_planner import StructuralAnalysisPlanner

        if self._model is None:
            self._model = create_chat_model(self.settings)
        self.geometry_planner = GeometryPlanner(self._model)
        self.structural_planner = StructuralAnalysisPlanner(self._model)
        self.feature_plan_planner = FeaturePlanPlanner(self._model)

    @property
    def graph(self):
        self._ensure_planners()
        if self._graph is None:
            self._graph = GraphBuilder(self).build()
        return self._graph

    # ------------------------------------------------------------------
    # Public workflow API
    # ------------------------------------------------------------------

    def start(
        self,
        description: str,
        perform_structural_analysis: bool = False,
        clarifications: list[dict[str, Any]] | None = None,
        *,
        output_dir: str | Path | None = None,
        thread_id: str | None = None,
        clarification_round: int = 0,
    ) -> AgentCADResult:
        description = description.strip()
        if not description:
            raise ValueError("description must not be empty")

        thread_id = thread_id or str(uuid.uuid4())
        if output_dir is None:
            run_dir = self.store.create_run(description)
        else:
            run_dir = Path(output_dir).expanduser().resolve()
            for sub in ("specification", "geometry", "mesh", "solver", "results", "validation", "logs"):
                (run_dir / sub).mkdir(parents=True, exist_ok=True)

        clarifications = list(clarifications or [])
        self.store.write_text(run_dir / "request.txt", description)
        self.store.write_json(run_dir / "validation" / "clarification_history.json", clarifications)
        self.store.write_json(
            run_dir / "validation" / f"clarification_history_round_{clarification_round:02d}.json",
            clarifications,
        )

        initial = {
            "request": description,
            "thread_id": thread_id,
            "perform_structural_analysis": perform_structural_analysis,
            "clarification_round": int(clarification_round),
            "max_planning_iterations": int(self.settings.max_planning_iterations),
            "clarifications": clarifications,
            "output_dir": str(run_dir),
            "artifacts": {},
            "status": "planning",
            "failure": None,
            "feature_plan_attempts": 0,
            "events": [
                f"Run started: clarification round {clarification_round}; "
                f"structural analysis={'enabled' if perform_structural_analysis else 'disabled'}."
            ],
            "diagnostics": [],
        }

        try:
            state = dict(self.graph.invoke(initial))
        except Exception as exc:
            failure = self.failure_classifier.classify(exc, stage="orchestration")
            errors_method = getattr(exc, "errors", None)
            if callable(errors_method):
                try:
                    failure["validation_errors"] = errors_method()
                except Exception:
                    pass
            self.store.write_json(run_dir / "logs" / "failure.json", failure)
            self.store.write_text(run_dir / "logs" / "orchestration_traceback.txt", traceback.format_exc())
            state = dict(initial)
            state.update(
                {
                    "status": "failed",
                    "failure": failure,
                    "events": initial["events"] + [f"Orchestration failed: {failure.get('message', '')}"],
                    "diagnostics": [failure],
                }
            )

        result = self._to_result(state, thread_id=thread_id)
        self._persist_result(result)
        self._remember_run(result)
        return result

    def resume(self, thread_id: str, answers: dict[str, Any]) -> AgentCADResult:
        """Continue the same engineering task after a clarification round.

        v3 re-runs the typed planning/validation pipeline using the original
        request plus accumulated clarification history. The run directory and
        thread id are preserved, so all JSON snapshots and diagnostics remain
        together and can be compared round by round.
        """
        context = self._run_contexts.get(thread_id)
        if context is None:
            raise KeyError(
                "Unknown AgentCAD thread_id. The in-memory engine context may have "
                "been lost after an application restart. Start the task again."
            )

        current_result = self._last_results.get(thread_id)
        questions = current_result.clarification_questions if current_result else []
        question_by_id = {str(q.get("id")): q for q in questions}
        history = list(context.get("clarifications", []))
        next_round = int(context.get("clarification_round", 0)) + 1

        for question_id, answer in answers.items():
            value = str(answer).strip()
            if not value:
                continue
            q = question_by_id.get(str(question_id), {})
            history.append(
                {
                    "round": next_round,
                    "question_id": str(question_id),
                    "question": q.get("question", ""),
                    "path": q.get("path"),
                    "answer": value,
                }
            )

        if history == context.get("clarifications", []):
            raise ValueError("At least one non-empty clarification answer is required.")

        return self.start(
            context["description"],
            perform_structural_analysis=bool(context["perform_structural_analysis"]),
            clarifications=history,
            output_dir=context["output_dir"],
            thread_id=thread_id,
            clarification_round=next_round,
        )

    def get_state(self, thread_id: str) -> dict[str, Any]:
        result = self._last_results.get(thread_id)
        if result is None:
            raise KeyError(f"Unknown AgentCAD thread_id: {thread_id}")
        return dict(result.state)

    def get_result(self, thread_id: str) -> AgentCADResult:
        result = self._last_results.get(thread_id)
        if result is None:
            raise KeyError(f"Unknown AgentCAD thread_id: {thread_id}")
        return result

    def get_artifacts(self, thread_id: str) -> dict[str, Any]:
        return dict(self.get_result(thread_id).artifacts)

    # ------------------------------------------------------------------
    # Deterministic entry points
    # ------------------------------------------------------------------

    def execute_feature_plan(
        self,
        plan: GeometryFeaturePlan,
        output_dir: str | Path,
    ) -> AgentCADResult:
        """Deterministic entry point useful for tests and non-LLM integrations."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        report = self.feature_plan_validator.validate(plan)
        self.store.write_json(out / "validation" / "feature_plan_validation.json", report)
        if not report.is_valid:
            failure = {
                "category": "feature_plan_failure",
                "details": report.model_dump(mode="json"),
            }
            return AgentCADResult(
                status="feature_plan_invalid",
                output_dir=str(out),
                failure=failure,
                feature_plan_validation=report.model_dump(mode="json"),
                diagnostics=[failure],
            )
        data = self.execute_geometry(plan, out)
        return AgentCADResult(
            status=data["status"],
            output_dir=str(out),
            feature_plan=plan.model_dump(mode="json"),
            feature_plan_validation=report.model_dump(mode="json"),
            geometry_inspection=data.get("geometry_inspection"),
            artifacts=data.get("artifacts", {}),
            failure=data.get("failure"),
        )

    def execute_geometry(self, plan: GeometryFeaturePlan, run_dir: Path) -> dict[str, Any]:
        build = self.compiler.compile(plan)
        inspection = self.geometry_inspector.inspect(build)
        self.store.write_json(run_dir / "validation" / "geometry_inspection.json", inspection)
        if not inspection.valid or inspection.solids < 1:
            raise RuntimeError("Built B-Rep failed geometry inspection or contains no solid.")
        expected_regions = {r.name for r in plan.semantic_regions}
        missing_regions = sorted(expected_regions - set(inspection.semantic_regions))
        if missing_regions:
            raise RuntimeError(
                "Semantic geometry verification failed for regions: "
                + ", ".join(missing_regions)
            )

        manifest = self.geometry_exporter.export(
            build,
            run_dir / "geometry",
            basename="model",
        )
        self.store.write_json(run_dir / "manifest_geometry.json", manifest)
        return {
            "geometry_inspection": inspection.model_dump(mode="json"),
            "artifacts": manifest.model_dump(mode="json"),
            "status": "geometry_complete",
            "failure": None,
        }

    def execute_fem(self, state: dict[str, Any]) -> dict[str, Any]:
        run_dir = Path(state["output_dir"])
        plan = GeometryFeaturePlan.model_validate(state["feature_plan"])
        analysis = StructuralAnalysisSpec.model_validate(state["structural_analysis"])
        geometry_artifacts = state.get("artifacts", {})
        files = geometry_artifacts.get("files", {})
        step_path = files.get("step")
        if not step_path:
            raise RuntimeError("STEP artifact is required for the Gmsh backend.")

        mesh_result = self.mesh_adapter.mesh(
            step_path,
            plan,
            analysis.mesh,
            run_dir / "mesh",
        )
        self.store.write_json(run_dir / "manifest_mesh.json", mesh_result)
        inp = self.calculix_builder.build(
            mesh_result["base_inp"],
            mesh_result["metadata"],
            analysis,
            run_dir / "solver",
            job_name="agentcad_model",
        )
        execution = self.calculix_executor.run(inp)
        summary = self.result_parser.parse(execution)
        self.store.write_json(run_dir / "results" / "simulation_summary.json", summary)
        self.store.write_json(run_dir / "manifest_solver.json", execution)

        artifacts = dict(geometry_artifacts)
        artifact_files = dict(artifacts.get("files", {}))
        artifact_files.update(
            {
                "mesh_msh": mesh_result["msh"],
                "mesh_metadata": mesh_result["metadata"],
                "calculix_inp": str(inp),
                "calculix_frd": execution.get("frd", ""),
                "calculix_dat": execution.get("dat", ""),
            }
        )
        artifacts["files"] = artifact_files
        return {
            "mesh_result": mesh_result,
            "solver_result": execution,
            "simulation_summary": summary.model_dump(mode="json"),
            "artifacts": artifacts,
            "status": "complete" if summary.success else "solver_failed",
            "failure": None
            if summary.success
            else {
                "category": "solver_failure",
                "message": "; ".join(summary.notes)
                or "CalculiX did not produce a successful result.",
            },
        }

    # ------------------------------------------------------------------
    # Result persistence / inspection
    # ------------------------------------------------------------------

    def _remember_run(self, result: AgentCADResult) -> None:
        if not result.thread_id:
            return
        self._last_results[result.thread_id] = result
        self._run_contexts[result.thread_id] = {
            "description": result.original_request or "",
            "perform_structural_analysis": result.perform_structural_analysis,
            "output_dir": result.output_dir,
            "clarifications": list(result.clarifications),
            "clarification_round": int(result.clarification_round),
        }

    def _persist_result(self, result: AgentCADResult) -> None:
        if not result.output_dir:
            return
        run_dir = Path(result.output_dir)
        round_no = int(result.clarification_round)
        self.store.write_json(run_dir / "logs" / "final_state.json", result.state)
        self.store.write_json(
            run_dir / "logs" / f"final_state_round_{round_no:02d}.json",
            result.state,
        )
        self.store.write_json(run_dir / "run_result.json", result)
        self.store.write_json(
            run_dir / "logs" / f"run_result_round_{round_no:02d}.json",
            result,
        )
        self.store.write_json(run_dir / "logs" / "events.json", result.events)
        if result.failure:
            self.store.write_json(run_dir / "logs" / "failure.json", result.failure)

    @staticmethod
    def _to_result(state: dict[str, Any], *, thread_id: str) -> AgentCADResult:
        status = state.get("status", "complete")
        questions = state.get("clarification_questions", []) or []
        failure = state.get("failure")

        if questions or status == "needs_input":
            message = "AgentCAD requires additional engineering information before continuing."
            status = "needs_input"
        elif failure:
            message = failure.get("message", "AgentCAD completed with an error.")
        elif status in {"complete", "geometry_complete"}:
            message = "AgentCAD completed successfully."
        else:
            message = f"AgentCAD finished with status: {status}."

        return AgentCADResult(
            status=status,
            message=message,
            thread_id=thread_id,
            output_dir=state.get("output_dir"),
            original_request=state.get("request"),
            perform_structural_analysis=bool(state.get("perform_structural_analysis", False)),
            clarification_round=int(state.get("clarification_round", 0)),
            clarifications=state.get("clarifications", []) or [],
            unified_model=state.get("unified_model"),
            validation_report=state.get("validation_report"),
            feature_plan=state.get("feature_plan"),
            feature_plan_validation=state.get("feature_plan_validation"),
            geometry_inspection=state.get("geometry_inspection"),
            simulation_summary=state.get("simulation_summary"),
            artifacts=state.get("artifacts", {}) or {},
            clarification_questions=questions,
            events=state.get("events", []) or [],
            diagnostics=state.get("diagnostics", []) or [],
            state=state,
            failure=failure,
        )
