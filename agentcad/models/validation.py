from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .common import IssueKind, IssueSeverity, ValidationStatus


class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: IssueSeverity = IssueSeverity.ERROR
    kind: IssueKind = IssueKind.INVALID
    module: str
    affected_parameters: list[str] = Field(default_factory=list)
    explanation: Optional[str] = None
    suggested_question: Optional[str] = None
    requires_user: bool = False


class ValidationReport(BaseModel):
    status: ValidationStatus
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.WARNING]
