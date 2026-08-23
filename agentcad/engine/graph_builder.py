from __future__ import annotations

import json
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agentcad.engine.state import AgentCADState
from agentcad.generators.code_generator import CodeGenerator
from agentcad.inspectors.failure_classifier import FailureClass, FailureClassifier
from agentcad.inspectors.fem_result_inspector import FEMResultInspector
from agentcad.inspectors.stl_inspector import STLInspector
from agentcad.models.artifacts import ExecutionResult, FEMInspectionReport, STLInspectionReport
from agentcad.models.common import TaskIntent, ValidationStatus
from agentcad.models.geometry import GeometrySpec
from agentcad.models.planning import ClarificationRecord
from agentcad.models.simulation import StructuralAnalysisSpec
from agentcad.models.unified_specification import UnifiedModelSpecification
from agentcad.models.validation import ValidationReport
from agentcad.planners.clarification_manager import ClarificationManager
from agentcad.planners.geometry_planner import GeometryPlanner
from agentcad.planners.structural_analysis_planner import StructuralAnalysisPlanner
from agentcad.validators.unified_consistency_validator import UnifiedConsistencyValidator
from agentcad.executors.freecad_executor import FreeCADExecutor


class GraphBuilder:
    """Connects independent AgentCAD modules into one LangGraph workflow."""

    def __init__(
        self,
        *,
        geometry_planner: GeometryPlanner,
        structural_planner: StructuralAnalysisPlanner,
        validator: UnifiedConsistencyValidator,
        clarification_manager: ClarificationManager,
        code_generator: CodeGenerator,
        executor: FreeCADExecutor,
        stl_inspector: STLInspector,
        fem_inspector: FEMResultInspector,
        failure_classifier: FailureClassifier,
    ):
        self.geometry_planner = geometry_planner
        self.structural_planner = structural_planner
        self.validator = validator
        self.clarification_manager = clarification_manager
        self.code_generator = code_generator
        self.executor = executor
        self.stl_inspector = stl_inspector
        self.fem_inspector = fem_inspector
        self.failure_classifier = failure_classifier

    def build(self, checkpointer):
        graph = StateGraph(AgentCADState)
        graph.add_node("geometry_planner", self._geometry_planner)
        graph.add_node("structural_planner", self._structural_planner)
        graph.add_node("unified_validator", self._unified_validator)
        graph.add_node("prepare_clarification", self._prepare_clarification)
        graph.add_node("ask_user", self._ask_user)
        graph.add_node("freeze_specification", self._freeze_specification)
        graph.add_node("code_generator", self._code_generator)
        graph.add_node("freecad_executor", self._freecad_executor)
        graph.add_node("stl_inspector", self._stl_inspector)
        graph.add_node("fem_inspector", self._fem_inspector)
        graph.add_node("failure_classifier", self._failure_classifier)
        graph.add_node("finalize_success", self._finalize_success)
        graph.add_node("finalize_failure", self._finalize_failure)

        graph.add_edge(START, "geometry_planner")
        graph.add_edge("geometry_planner", "structural_planner")
        graph.add_edge("structural_planner", "unified_validator")
        graph.add_conditional_edges("unified_validator", self._route_after_validation)
        graph.add_conditional_edges("prepare_clarification", self._route_after_prepare_clarification)
        graph.add_edge("ask_user", "geometry_planner")
        graph.add_edge("freeze_specification", "code_generator")
        graph.add_edge("code_generator", "freecad_executor")
        graph.add_conditional_edges("freecad_executor", self._route_after_executor)
        graph.add_conditional_edges("stl_inspector", self._route_after_stl)
        graph.add_conditional_edges("fem_inspector", self._route_after_fem)
        graph.add_conditional_edges("failure_classifier", self._route_after_failure_classification)
        graph.add_edge("finalize_success", END)
        graph.add_edge("finalize_failure", END)
        return graph.compile(checkpointer=checkpointer)

    # ----------------------------- planning loop -----------------------------

    def _geometry_planner(self, state: AgentCADState) -> dict:
        spec = self.geometry_planner.plan(
            request=state["original_request"],
            clarifications=state.get("clarifications", []),
            previous_spec=state.get("geometry_spec"),
            failure_feedback=state.get("failure_feedback"),
        )
        return {
            "geometry_spec": spec.model_dump(mode="json"),
            "events": [f"GeometryPlanner: {spec.summary}"],
        }

    def _structural_planner(self, state: AgentCADState) -> dict:
        enabled = bool(state["perform_structural_analysis"])
        spec = self.structural_planner.plan(
            request=state["original_request"],
            geometry_spec=state["geometry_spec"],
            clarifications=state.get("clarifications", []),
            enabled=enabled,
            previous_spec=state.get("structural_spec"),
            failure_feedback=state.get("failure_feedback"),
        )
        return {
            "structural_spec": spec.model_dump(mode="json"),
            "events": [
                "StructuralAnalysisPlanner: FEM formulation updated."
                if enabled else
                "StructuralAnalysisPlanner: structural analysis disabled for this task."
            ],
        }

    def _unified_validator(self, state: AgentCADState) -> dict:
        geometry = GeometrySpec.model_validate(state["geometry_spec"])
        structural = StructuralAnalysisSpec.model_validate(state["structural_spec"])
        intent = TaskIntent(state["task_intent"])
        report = self.validator.validate(geometry, structural, intent)
        return {
            "validation_report": report.model_dump(mode="json"),
            "planning_iteration": int(state.get("planning_iteration", 0)) + 1,
            "events": [f"UnifiedConsistencyValidator: {report.status.value}."],
        }

    def _route_after_validation(
        self, state: AgentCADState
    ) -> Literal["freeze_specification", "prepare_clarification", "finalize_failure"]:
        report = ValidationReport.model_validate(state["validation_report"])
        if report.status in {ValidationStatus.VALID, ValidationStatus.VALID_WITH_WARNINGS}:
            return "freeze_specification"
        if int(state.get("planning_iteration", 0)) >= int(state["max_planning_iterations"]):
            return "finalize_failure"
        return "prepare_clarification"

    def _prepare_clarification(self, state: AgentCADState) -> dict:
        report = ValidationReport.model_validate(state["validation_report"])
        questions = self.clarification_manager.build_questions(report)
        feedback = {
            "source": "UnifiedConsistencyValidator",
            "message": f"Planning validation status: {report.status.value}",
            "details": report.model_dump(mode="json"),
        }
        return {
            "pending_questions": [q.model_dump(mode="json") for q in questions],
            "failure_feedback": feedback,
            "events": [
                f"ClarificationManager: prepared {len(questions)} user question(s)."
                if questions else
                "ClarificationManager: no user input required; planners will self-repair the formal specification."
            ],
        }

    def _route_after_prepare_clarification(
        self, state: AgentCADState
    ) -> Literal["ask_user", "geometry_planner", "finalize_failure"]:
        if state.get("pending_questions"):
            return "ask_user"
        if int(state.get("planning_iteration", 0)) >= int(state["max_planning_iterations"]):
            return "finalize_failure"
        return "geometry_planner"

    def _ask_user(self, state: AgentCADState) -> dict:
        # This is deliberately the first side-effecting operation in the node.
        # LangGraph re-runs the node from the beginning when Command(resume=...) is used.
        answer = interrupt({
            "type": "agentcad_clarification",
            "planning_iteration": state.get("planning_iteration", 0),
            "questions": state.get("pending_questions", []),
        })
        questions = state.get("pending_questions", [])
        record = ClarificationRecord(
            iteration=int(state.get("planning_iteration", 0)),
            questions=questions,
            answer=answer,
        )
        return {
            "clarifications": [record.model_dump(mode="json")],
            "pending_questions": [],
            "failure_feedback": {},
            "events": ["Human-in-the-loop: clarification received; restarting both planners."],
        }

    def _freeze_specification(self, state: AgentCADState) -> dict:
        geometry = GeometrySpec.model_validate(state["geometry_spec"])
        structural = StructuralAnalysisSpec.model_validate(state["structural_spec"])
        report = ValidationReport.model_validate(state["validation_report"])
        intent = TaskIntent(state["task_intent"])
        clarifications = [ClarificationRecord.model_validate(x) for x in state.get("clarifications", [])]
        assumptions = list(geometry.assumptions)
        if structural.enabled:
            assumptions.extend(structural.assumptions)
        spec = UnifiedModelSpecification(
            original_request=state["original_request"],
            task_intent=intent,
            geometry=geometry,
            structural_analysis=structural if structural.enabled else None,
            clarifications=clarifications,
            assumptions=assumptions,
            validation_report=report,
        )
        return {
            "unified_specification": spec.model_dump(mode="json"),
            "failure_feedback": {},
            "events": ["UnifiedModelSpecification: validated planning contract frozen."],
        }

    # --------------------------- implementation loop -------------------------

    @staticmethod
    def _diagnostics(state: AgentCADState) -> str:
        parts: list[str] = []
        if state.get("execution_result"):
            parts.append("EXECUTION:\n" + json.dumps(state["execution_result"], ensure_ascii=False, indent=2)[-15000:])
        if state.get("stl_inspection") and not state["stl_inspection"].get("passed"):
            parts.append("STL INSPECTION:\n" + json.dumps(state["stl_inspection"], ensure_ascii=False, indent=2))
        if state.get("fem_inspection") and not state["fem_inspection"].get("passed"):
            parts.append("FEM INSPECTION:\n" + json.dumps(state["fem_inspection"], ensure_ascii=False, indent=2))
        return "\n\n".join(parts)

    def _code_generator(self, state: AgentCADState) -> dict:
        attempt = int(state.get("code_attempt", 0)) + 1
        spec = UnifiedModelSpecification.model_validate(state["unified_specification"])
        result = self.code_generator.generate(
            specification=spec,
            output_dir=state["output_dir"],
            attempt=attempt,
            previous_code=state.get("generated_code", ""),
            diagnostics=self._diagnostics(state),
        )
        return {
            "code_attempt": attempt,
            "generated_code": result.script_code,
            "code_summary": result.summary,
            "execution_result": {},
            "stl_inspection": {},
            "fem_inspection": {},
            "final_success": False,
            "events": [f"CodeGenerator: generated implementation attempt {attempt}."],
        }

    def _freecad_executor(self, state: AgentCADState) -> dict:
        result = self.executor.execute(
            code=state["generated_code"],
            output_dir=state["output_dir"],
            attempt=int(state["code_attempt"]),
        )
        return {
            "execution_result": result.model_dump(mode="json"),
            "events": [f"FreeCADExecutor: {result.reason}"],
        }

    def _route_after_executor(
        self, state: AgentCADState
    ) -> Literal["stl_inspector", "code_generator", "finalize_failure"]:
        result = ExecutionResult.model_validate(state["execution_result"])
        if result.success:
            return "stl_inspector"
        if int(state["code_attempt"]) < int(state["max_code_attempts"]):
            return "code_generator"
        return "finalize_failure"

    def _stl_inspector(self, state: AgentCADState) -> dict:
        execution = ExecutionResult.model_validate(state["execution_result"])
        spec = UnifiedModelSpecification.model_validate(state["unified_specification"])
        stls = execution.artifacts.stl
        if not stls:
            report = STLInspectionReport(errors=["FreeCAD execution produced no STL file."])
        else:
            newest = max(stls, key=lambda p: __import__('pathlib').Path(p).stat().st_mtime_ns)
            report = self.stl_inspector.inspect(newest, spec)
        return {
            "stl_inspection": report.model_dump(mode="json"),
            "events": [
                "STLInspector: geometry passed inspection."
                if report.passed else
                "STLInspector: geometry failed inspection."
            ],
        }

    def _route_after_stl(
        self, state: AgentCADState
    ) -> Literal["fem_inspector", "finalize_success", "code_generator", "finalize_failure"]:
        report = STLInspectionReport.model_validate(state["stl_inspection"])
        if report.passed:
            return "fem_inspector" if state["perform_structural_analysis"] else "finalize_success"
        if int(state["code_attempt"]) < int(state["max_code_attempts"]):
            return "code_generator"
        return "finalize_failure"

    def _fem_inspector(self, state: AgentCADState) -> dict:
        report = self.fem_inspector.inspect(state["output_dir"])
        return {
            "fem_inspection": report.model_dump(mode="json"),
            "events": [
                "FEMResultInspector: solver results passed basic checks."
                if report.passed else
                "FEMResultInspector: solver results failed basic checks."
            ],
        }

    def _route_after_fem(
        self, state: AgentCADState
    ) -> Literal["finalize_success", "failure_classifier"]:
        report = FEMInspectionReport.model_validate(state["fem_inspection"])
        return "finalize_success" if report.passed else "failure_classifier"

    def _failure_classifier(self, state: AgentCADState) -> dict:
        execution = ExecutionResult.model_validate(state["execution_result"]) if state.get("execution_result") else None
        stl = STLInspectionReport.model_validate(state["stl_inspection"]) if state.get("stl_inspection") else None
        fem = FEMInspectionReport.model_validate(state["fem_inspection"]) if state.get("fem_inspection") else None
        failure = self.failure_classifier.classify(execution, stl, fem)
        feedback = {
            "source": "FailureClassifier",
            "message": f"Failure classified as {failure.value}.",
            "details": {
                "execution": state.get("execution_result", {}),
                "stl": state.get("stl_inspection", {}),
                "fem": state.get("fem_inspection", {}),
            },
        }
        update = {
            "failure_class": failure.value,
            "failure_feedback": feedback,
            "events": [f"FailureClassifier: {failure.value}."],
        }
        if failure == FailureClass.MODEL_SPECIFICATION:
            # The validated specification needs revision; grant a fresh code retry budget
            # after the planning loop resolves the model issue.
            update.update({"code_attempt": 0, "generated_code": ""})
        return update

    def _route_after_failure_classification(
        self, state: AgentCADState
    ) -> Literal["geometry_planner", "code_generator", "finalize_failure"]:
        failure = FailureClass(state.get("failure_class", FailureClass.UNKNOWN.value))
        if failure == FailureClass.MODEL_SPECIFICATION:
            if int(state.get("planning_iteration", 0)) < int(state["max_planning_iterations"]):
                return "geometry_planner"
            return "finalize_failure"
        if int(state.get("code_attempt", 0)) < int(state["max_code_attempts"]):
            return "code_generator"
        return "finalize_failure"

    # ------------------------------ terminal --------------------------------

    def _finalize_success(self, state: AgentCADState) -> dict:
        return {
            "final_success": True,
            "final_reason": "AgentCAD completed generation and all required inspections.",
            "events": ["AgentCAD: completed successfully."],
        }

    def _finalize_failure(self, state: AgentCADState) -> dict:
        reason = "AgentCAD stopped before producing a validated result."
        if state.get("validation_report"):
            report = ValidationReport.model_validate(state["validation_report"])
            if report.status not in {ValidationStatus.VALID, ValidationStatus.VALID_WITH_WARNINGS}:
                reason = f"Planning did not become valid: {report.status.value}."
        if state.get("execution_result"):
            execution = ExecutionResult.model_validate(state["execution_result"])
            if not execution.success:
                reason = execution.reason
        if state.get("fem_inspection"):
            fem = FEMInspectionReport.model_validate(state["fem_inspection"])
            if not fem.passed and fem.errors:
                reason = "FEM result inspection failed: " + "; ".join(fem.errors[:3])
        return {
            "final_success": False,
            "final_reason": reason,
            "events": [f"AgentCAD: failed — {reason}"],
        }
