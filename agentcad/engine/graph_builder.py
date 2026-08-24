from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

from agentcad.models.common import TaskIntent, ValidationStatus
from agentcad.models.feature_plan import GeometryFeaturePlan
from agentcad.models.geometry import GeometrySpec
from agentcad.models.simulation import StructuralAnalysisSpec
from agentcad.models.unified_specification import UnifiedEngineeringModel
from agentcad.models.validation import ValidationReport

from .state import AgentCADState


class GraphBuilder:
    """Build the verifier-guided AgentCAD v3 orchestration graph.

    LLM nodes only create typed specifications/plans. Deterministic nodes
    validate and execute those plans. Every stage emits a protocol event and
    important intermediate data is persisted before the next stage runs.
    """

    def __init__(self, engine):
        self.engine = engine

    def build(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:  # pragma: no cover - dependency check
            raise RuntimeError(
                "LangGraph is required for AgentCAD graph orchestration. "
                "Install project dependencies first."
            ) from exc

        graph = StateGraph(AgentCADState)
        graph.add_node("plan_geometry", self._plan_geometry)
        graph.add_node("plan_analysis", self._plan_analysis)
        graph.add_node("validate_engineering_model", self._validate_engineering_model)
        graph.add_node("prepare_clarification", self._prepare_clarification)
        graph.add_node("finalize_planning_failure", self._finalize_planning_failure)
        graph.add_node("plan_features", self._plan_features)
        graph.add_node("validate_feature_plan", self._validate_feature_plan)
        graph.add_node("build_geometry", self._build_geometry)
        graph.add_node("run_fem", self._run_fem)

        graph.add_edge(START, "plan_geometry")
        graph.add_conditional_edges(
            "plan_geometry",
            self._after_planning_node,
            {"continue": "plan_analysis", "fail": END},
        )
        graph.add_conditional_edges(
            "plan_analysis",
            self._after_planning_node,
            {"continue": "validate_engineering_model", "fail": END},
        )
        graph.add_conditional_edges(
            "validate_engineering_model",
            self._after_engineering_validation,
            {
                "clarify": "prepare_clarification",
                "continue": "plan_features",
                "fail": "finalize_planning_failure",
            },
        )
        graph.add_edge("prepare_clarification", END)
        graph.add_edge("finalize_planning_failure", END)

        graph.add_conditional_edges(
            "plan_features",
            self._after_feature_planning,
            {"retry": "plan_features", "fail": END, "continue": "validate_feature_plan"},
        )
        graph.add_conditional_edges(
            "validate_feature_plan",
            self._after_feature_validation,
            {"retry": "plan_features", "fail": END, "continue": "build_geometry"},
        )
        graph.add_conditional_edges(
            "build_geometry",
            self._after_geometry,
            {"retry": "plan_features", "fail": END, "fem": "run_fem", "done": END},
        )
        graph.add_edge("run_fem", END)
        return graph.compile()

    # ------------------------------------------------------------------
    # Diagnostic helpers
    # ------------------------------------------------------------------

    def _failure_payload(self, exc: Exception, *, stage: str, attempt: int | None = None) -> dict[str, Any]:
        payload = self.engine.failure_classifier.classify(exc, stage=stage)
        if attempt is not None:
            payload["attempt"] = attempt
        # Pydantic ValidationError exposes structured field-level errors.
        errors_method = getattr(exc, "errors", None)
        if callable(errors_method):
            try:
                payload["validation_errors"] = errors_method()
            except Exception:
                pass
        return payload

    def _persist_exception(
        self,
        state: AgentCADState,
        *,
        stage: str,
        attempt: int,
        exc: Exception,
        payload: dict[str, Any],
    ) -> None:
        run_dir = Path(state["output_dir"])
        stem = f"{stage}_attempt_{attempt:02d}"
        self.engine.store.write_json(run_dir / "logs" / f"{stem}_error.json", payload)
        self.engine.store.write_text(
            run_dir / "logs" / f"{stem}_traceback.txt",
            traceback.format_exc(),
        )

    @staticmethod
    def _after_planning_node(state: AgentCADState) -> str:
        return "fail" if state.get("failure") else "continue"

    # ------------------------------------------------------------------
    # Engineering planning
    # ------------------------------------------------------------------

    def _plan_geometry(self, state: AgentCADState) -> dict[str, Any]:
        previous = state.get("geometry_spec")
        diagnostics: list[dict[str, Any]] = []
        retry_budget = max(1, min(3, int(state.get("max_planning_iterations", 3))))
        feedback = state.get("failure")

        for attempt in range(1, retry_budget + 1):
            try:
                geometry = self.engine.geometry_planner.plan(
                    state["request"],
                    state.get("clarifications", []),
                    previous_spec=previous,
                    failure_feedback=feedback,
                )
            except Exception as exc:
                payload = self._failure_payload(exc, stage="geometry_planner", attempt=attempt)
                payload["message"] = (
                    "GeometryPlanner did not produce a valid GeometrySpec. "
                    + payload.get("message", "")
                )
                self._persist_exception(
                    state,
                    stage="geometry_planner",
                    attempt=attempt,
                    exc=exc,
                    payload=payload,
                )
                diagnostics.append(payload)
                feedback = payload
                continue

            run_dir = Path(state["output_dir"])
            round_no = int(state.get("clarification_round", 0))
            self.engine.store.write_json(run_dir / "specification" / "geometry_spec.json", geometry)
            self.engine.store.write_json(
                run_dir / "specification" / f"geometry_spec_round_{round_no:02d}.json",
                geometry,
            )
            return {
                "geometry_spec": geometry.model_dump(mode="json"),
                "failure": None,
                "status": "planning",
                "events": [f"GeometryPlanner: valid GeometrySpec produced on attempt {attempt}."],
                "diagnostics": diagnostics,
            }

        failure = diagnostics[-1] if diagnostics else {
            "category": "planning_output_failure",
            "stage": "geometry_planner",
            "message": "GeometryPlanner failed without a diagnostic payload.",
        }
        return {
            "failure": failure,
            "status": "planning_failed",
            "events": [f"GeometryPlanner: failed after {retry_budget} structured-output attempt(s)."],
            "diagnostics": diagnostics,
        }

    def _plan_analysis(self, state: AgentCADState) -> dict[str, Any]:
        if not state.get("perform_structural_analysis", False):
            analysis = self.engine.structural_planner.disabled()
            run_dir = Path(state["output_dir"])
            self.engine.store.write_json(run_dir / "specification" / "structural_analysis.json", analysis)
            return {
                "structural_analysis": analysis.model_dump(mode="json"),
                "failure": None,
                "events": ["StructuralAnalysisPlanner: structural analysis disabled for this task."],
            }

        diagnostics: list[dict[str, Any]] = []
        retry_budget = max(1, min(3, int(state.get("max_planning_iterations", 3))))
        feedback = state.get("failure")

        for attempt in range(1, retry_budget + 1):
            try:
                analysis = self.engine.structural_planner.plan(
                    state["request"],
                    state["geometry_spec"],
                    state.get("clarifications", []),
                    previous_spec=state.get("structural_analysis"),
                    failure_feedback=feedback,
                )
            except Exception as exc:
                payload = self._failure_payload(exc, stage="structural_planner", attempt=attempt)
                payload["message"] = (
                    "StructuralAnalysisPlanner did not produce a valid StructuralAnalysisSpec. "
                    + payload.get("message", "")
                )
                self._persist_exception(
                    state,
                    stage="structural_planner",
                    attempt=attempt,
                    exc=exc,
                    payload=payload,
                )
                diagnostics.append(payload)
                feedback = payload
                continue

            run_dir = Path(state["output_dir"])
            round_no = int(state.get("clarification_round", 0))
            self.engine.store.write_json(run_dir / "specification" / "structural_analysis.json", analysis)
            self.engine.store.write_json(
                run_dir / "specification" / f"structural_analysis_round_{round_no:02d}.json",
                analysis,
            )
            return {
                "structural_analysis": analysis.model_dump(mode="json"),
                "failure": None,
                "events": [f"StructuralAnalysisPlanner: valid analysis specification produced on attempt {attempt}."],
                "diagnostics": diagnostics,
            }

        failure = diagnostics[-1] if diagnostics else {
            "category": "planning_output_failure",
            "stage": "structural_planner",
            "message": "StructuralAnalysisPlanner failed without a diagnostic payload.",
        }
        return {
            "failure": failure,
            "status": "planning_failed",
            "events": [f"StructuralAnalysisPlanner: failed after {retry_budget} structured-output attempt(s)."],
            "diagnostics": diagnostics,
        }

    # ------------------------------------------------------------------
    # Engineering validation + user clarification boundary
    # ------------------------------------------------------------------

    def _validate_engineering_model(self, state: AgentCADState) -> dict[str, Any]:
        geometry = GeometrySpec.model_validate(state["geometry_spec"])
        analysis = StructuralAnalysisSpec.model_validate(state["structural_analysis"])
        intent = (
            TaskIntent.GEOMETRY_AND_STRUCTURAL_ANALYSIS
            if state.get("perform_structural_analysis")
            else TaskIntent.GEOMETRY_ONLY
        )
        report = self.engine.unified_validator.validate(geometry, analysis, intent)
        model = UnifiedEngineeringModel(
            original_request=state["request"],
            task_intent=intent,
            geometry=geometry,
            structural_analysis=analysis if state.get("perform_structural_analysis") else None,
            clarifications=state.get("clarifications", []),
            validation_report=report,
        )
        run_dir = Path(state["output_dir"])
        round_no = int(state.get("clarification_round", 0))
        self.engine.store.write_json(run_dir / "specification" / "engineering_model.json", model)
        self.engine.store.write_json(run_dir / "validation" / "engineering_validation.json", report)
        self.engine.store.write_json(
            run_dir / "specification" / f"engineering_model_round_{round_no:02d}.json",
            model,
        )
        self.engine.store.write_json(
            run_dir / "validation" / f"engineering_validation_round_{round_no:02d}.json",
            report,
        )
        return {
            "task_intent": intent.value,
            "validation_report": report.model_dump(mode="json"),
            "unified_model": model.model_dump(mode="json"),
            "failure": None,
            "events": [f"UnifiedConsistencyValidator: {report.status.value}."],
        }

    @staticmethod
    def _after_engineering_validation(state: AgentCADState) -> str:
        report = ValidationReport.model_validate(state["validation_report"])
        if report.status in {ValidationStatus.VALID, ValidationStatus.VALID_WITH_WARNINGS}:
            return "continue"
        if int(state.get("clarification_round", 0)) >= int(state.get("max_planning_iterations", 4)):
            return "fail"
        return "clarify"

    def _prepare_clarification(self, state: AgentCADState) -> dict[str, Any]:
        report = ValidationReport.model_validate(state["validation_report"])
        questions = self.engine.clarification_manager.questions(report)
        run_dir = Path(state["output_dir"])
        round_no = int(state.get("clarification_round", 0))
        self.engine.store.write_json(run_dir / "validation" / "clarification_questions.json", questions)
        self.engine.store.write_json(
            run_dir / "validation" / f"clarification_questions_round_{round_no:02d}.json",
            questions,
        )
        return {
            "clarification_questions": questions,
            "status": "needs_input",
            "events": [f"ClarificationManager: prepared {len(questions)} question(s) for the user."],
        }

    def _finalize_planning_failure(self, state: AgentCADState) -> dict[str, Any]:
        failure = {
            "category": "planning_validation_failure",
            "stage": "engineering_validation",
            "message": (
                "The engineering specification is still invalid after the maximum "
                "number of clarification rounds."
            ),
            "details": state.get("validation_report", {}),
        }
        run_dir = Path(state["output_dir"])
        self.engine.store.write_json(run_dir / "logs" / "failure.json", failure)
        return {
            "failure": failure,
            "status": "failed",
            "clarification_questions": [],
            "events": ["Planning loop: maximum clarification rounds reached."],
            "diagnostics": [failure],
        }

    # ------------------------------------------------------------------
    # CAD-IR planning and deterministic geometry
    # ------------------------------------------------------------------

    def _plan_features(self, state: AgentCADState) -> dict[str, Any]:
        attempt = int(state.get("feature_plan_attempts", 0)) + 1
        try:
            plan = self.engine.feature_plan_planner.plan(
                state["unified_model"],
                previous_plan=state.get("feature_plan"),
                failure_feedback=state.get("failure"),
            )
        except Exception as exc:
            failure = self._failure_payload(exc, stage="feature_plan_planner", attempt=attempt)
            failure["category"] = "feature_plan_failure"
            failure["message"] = (
                "FeaturePlanPlanner did not produce a valid GeometryFeaturePlan. "
                + failure.get("message", "")
            )
            self._persist_exception(
                state,
                stage="feature_plan_planner",
                attempt=attempt,
                exc=exc,
                payload=failure,
            )
            return {
                "feature_plan_attempts": attempt,
                "failure": failure,
                "status": "feature_plan_invalid",
                "events": [f"FeaturePlanPlanner: structured-output attempt {attempt} failed."],
                "diagnostics": [failure],
            }

        run_dir = Path(state["output_dir"])
        self.engine.store.write_json(run_dir / "specification" / "feature_plan.json", plan)
        self.engine.store.write_json(
            run_dir / "specification" / f"feature_plan_attempt_{attempt:02d}.json",
            plan,
        )
        return {
            "feature_plan": plan.model_dump(mode="json"),
            "feature_plan_attempts": attempt,
            "failure": None,
            "status": "feature_plan_planned",
            "events": [f"FeaturePlanPlanner: GeometryFeaturePlan produced on attempt {attempt}."],
        }

    def _after_feature_planning(self, state: AgentCADState) -> str:
        if not state.get("failure"):
            return "continue"
        if int(state.get("feature_plan_attempts", 0)) < self.engine.settings.max_feature_plan_attempts:
            return "retry"
        return "fail"

    def _validate_feature_plan(self, state: AgentCADState) -> dict[str, Any]:
        plan = GeometryFeaturePlan.model_validate(state["feature_plan"])
        expected_regions = {
            r["name"] for r in state.get("geometry_spec", {}).get("semantic_regions", [])
        }
        report = self.engine.feature_plan_validator.validate(
            plan,
            expected_regions=expected_regions,
        )
        run_dir = Path(state["output_dir"])
        attempt = int(state.get("feature_plan_attempts", 0))
        self.engine.store.write_json(run_dir / "validation" / "feature_plan_validation.json", report)
        self.engine.store.write_json(
            run_dir / "validation" / f"feature_plan_validation_attempt_{attempt:02d}.json",
            report,
        )
        if report.is_valid:
            return {
                "feature_plan_validation": report.model_dump(mode="json"),
                "failure": None,
                "events": ["FeaturePlanValidator: CAD-IR passed deterministic validation."],
            }
        failure = {
            "category": "feature_plan_failure",
            "stage": "feature_plan_validation",
            "attempt": attempt,
            "message": "Feature plan failed deterministic validation.",
            "details": report.model_dump(mode="json"),
        }
        self.engine.store.write_json(
            run_dir / "logs" / f"feature_plan_validation_attempt_{attempt:02d}_error.json",
            failure,
        )
        return {
            "feature_plan_validation": report.model_dump(mode="json"),
            "failure": failure,
            "status": "feature_plan_invalid",
            "events": ["FeaturePlanValidator: CAD-IR validation failed; replanning requested."],
            "diagnostics": [failure],
        }

    def _after_feature_validation(self, state: AgentCADState) -> str:
        if not state.get("failure"):
            return "continue"
        if int(state.get("feature_plan_attempts", 0)) < self.engine.settings.max_feature_plan_attempts:
            return "retry"
        return "fail"

    def _build_geometry(self, state: AgentCADState) -> dict[str, Any]:
        try:
            result = self.engine.execute_geometry(
                GeometryFeaturePlan.model_validate(state["feature_plan"]),
                Path(state["output_dir"]),
            )
            result["events"] = ["CadQueryGeometryCompiler: B-Rep built, verified and exported."]
            return result
        except Exception as exc:
            failure = self._failure_payload(
                exc,
                stage="geometry",
                attempt=int(state.get("feature_plan_attempts", 0)),
            )
            self._persist_exception(
                state,
                stage="geometry",
                attempt=max(1, int(state.get("feature_plan_attempts", 0))),
                exc=exc,
                payload=failure,
            )
            return {
                "failure": failure,
                "status": "geometry_failed",
                "events": [f"CadQuery geometry execution failed: {failure.get('message', '')}"],
                "diagnostics": [failure],
            }

    def _after_geometry(self, state: AgentCADState) -> str:
        failure = state.get("failure")
        if failure:
            if (
                failure.get("category") == "feature_plan_failure"
                and int(state.get("feature_plan_attempts", 0))
                < self.engine.settings.max_feature_plan_attempts
            ):
                return "retry"
            return "fail"
        return "fem" if state.get("perform_structural_analysis") else "done"

    # ------------------------------------------------------------------
    # FEM
    # ------------------------------------------------------------------

    def _run_fem(self, state: AgentCADState) -> dict[str, Any]:
        try:
            result = self.engine.execute_fem(state)
            result["events"] = [
                "Gmsh/CalculiX pipeline completed successfully."
                if not result.get("failure")
                else "Gmsh/CalculiX pipeline completed with a solver failure."
            ]
            return result
        except Exception as exc:
            failure = self._failure_payload(exc, stage="fem", attempt=1)
            self._persist_exception(
                state,
                stage="fem",
                attempt=1,
                exc=exc,
                payload=failure,
            )
            return {
                "failure": failure,
                "status": "fem_failed",
                "events": [f"FEM pipeline failed: {failure.get('message', '')}"],
                "diagnostics": [failure],
            }
