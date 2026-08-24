from __future__ import annotations

from pydantic import BaseModel, Field

from .common import IssueKind, IssueSeverity, ValidationStatus


class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: IssueSeverity = IssueSeverity.ERROR
    kind: IssueKind = IssueKind.INVALID
    path: str = ""
    suggested_question: str | None = None


class ValidationReport(BaseModel):
    status: ValidationStatus
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.status in {ValidationStatus.VALID, ValidationStatus.VALID_WITH_WARNINGS}
