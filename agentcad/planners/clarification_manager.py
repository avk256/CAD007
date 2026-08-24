from __future__ import annotations

from agentcad.models.planning import ClarificationQuestion
from agentcad.models.validation import ValidationReport

from .parameter_explainer import ParameterExplainer


class ClarificationManager:
    def __init__(self, explainer: ParameterExplainer | None = None):
        self.explainer = explainer or ParameterExplainer()

    def questions(self, report: ValidationReport) -> list[dict]:
        questions: list[dict] = []
        for i, issue in enumerate(report.issues):
            if issue.severity.value != "error":
                continue
            question = issue.suggested_question or f"Please clarify: {issue.message}"
            item = ClarificationQuestion(
                id=f"q{i+1}_{issue.code}",
                question=question,
                path=issue.path,
                explanation=self.explainer.explain(issue.path),
            )
            questions.append(item.model_dump(mode="json"))
        return questions
