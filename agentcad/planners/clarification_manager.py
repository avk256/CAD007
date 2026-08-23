from __future__ import annotations

import uuid

from agentcad.models.planning import ClarificationQuestion
from agentcad.models.validation import ValidationReport
from .parameter_explainer import ParameterExplainer


class ClarificationManager:
    """Converts formal validation issues into a compact user-question batch."""

    def __init__(self, explainer: ParameterExplainer | None = None):
        self.explainer = explainer or ParameterExplainer()

    def build_questions(self, report: ValidationReport) -> list[ClarificationQuestion]:
        questions: list[ClarificationQuestion] = []
        seen: set[str] = set()

        for issue in report.issues:
            if not issue.requires_user:
                continue
            signature = issue.suggested_question or issue.message
            if signature in seen:
                continue
            seen.add(signature)
            explanation = issue.explanation or self.explainer.explain(issue.affected_parameters)
            questions.append(
                ClarificationQuestion(
                    id=str(uuid.uuid4()),
                    category=issue.kind.value,
                    question=issue.suggested_question or issue.message,
                    explanation=explanation,
                    affected_parameters=issue.affected_parameters,
                )
            )

        return questions
