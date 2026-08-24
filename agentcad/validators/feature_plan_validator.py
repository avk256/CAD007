from __future__ import annotations

from agentcad.models.common import IssueKind, IssueSeverity, ValidationStatus
from agentcad.models.feature_plan import FeatureOperation, GeometryFeaturePlan
from agentcad.models.validation import ValidationIssue, ValidationReport


_REQUIRED: dict[FeatureOperation, tuple[str, ...]] = {
    FeatureOperation.BOX: ("x", "y", "z"),
    FeatureOperation.CYLINDER: ("height",),
    FeatureOperation.CONE: ("radius1", "radius2", "height"),
    FeatureOperation.SPHERE: ("radius",),
    FeatureOperation.EXTRUDE: ("profile", "distance"),
    FeatureOperation.REVOLVE: ("profile",),
    FeatureOperation.HOLE: ("diameter",),
    FeatureOperation.FILLET: ("radius",),
    FeatureOperation.CHAMFER: ("length",),
    FeatureOperation.TRANSLATE: ("vector",),
    FeatureOperation.ROTATE: ("axis_start", "axis_end", "angle_deg"),
    FeatureOperation.MIRROR: ("plane",),
    FeatureOperation.LINEAR_PATTERN: ("count", "spacing", "direction"),
    FeatureOperation.CIRCULAR_PATTERN: ("count", "axis_start", "axis_end"),
}


class FeaturePlanValidator:
    """Validates the CAD IR without importing or executing CadQuery."""

    def validate(self, plan: GeometryFeaturePlan, expected_regions: set[str] | None = None) -> ValidationReport:
        issues: list[ValidationIssue] = []
        seen: set[str] = set()
        ids = [s.id for s in plan.steps]

        for idx, step in enumerate(plan.steps):
            if step.id in seen:
                issues.append(self._error("duplicate_feature_id", f"Feature id '{step.id}' is duplicated.", f"steps[{idx}].id"))
            seen.add(step.id)

            for name in _REQUIRED.get(step.operation, ()):
                if name not in step.parameters:
                    issues.append(self._error("missing_feature_parameter", f"Operation '{step.operation.value}' requires parameter '{name}'.", f"steps[{idx}].parameters.{name}"))

            dependencies = list(step.inputs)
            if step.target:
                dependencies.append(step.target)
            for dep in dependencies:
                if dep not in seen:
                    issues.append(self._error("invalid_feature_dependency", f"Feature '{step.id}' references '{dep}' before it is defined.", f"steps[{idx}]"))

            if step.operation in {FeatureOperation.CUT, FeatureOperation.FUSE, FeatureOperation.INTERSECT} and len(step.inputs) < 2:
                issues.append(self._error("boolean_requires_inputs", f"Boolean operation '{step.operation.value}' requires at least two inputs.", f"steps[{idx}].inputs"))

            if step.operation in {FeatureOperation.HOLE, FeatureOperation.FILLET, FeatureOperation.CHAMFER, FeatureOperation.TRANSLATE, FeatureOperation.ROTATE, FeatureOperation.MIRROR, FeatureOperation.LINEAR_PATTERN, FeatureOperation.CIRCULAR_PATTERN} and not step.target:
                issues.append(self._error("operation_requires_target", f"Operation '{step.operation.value}' requires target.", f"steps[{idx}].target"))

        if not plan.steps:
            issues.append(self._error("empty_feature_plan", "Feature plan contains no steps.", "steps"))
        elif plan.root_feature not in ids:
            issues.append(self._error("missing_root_feature", f"Root feature '{plan.root_feature}' does not exist.", "root_feature"))

        region_names: set[str] = set()
        for idx, region in enumerate(plan.semantic_regions):
            if region.name in region_names:
                issues.append(self._error("duplicate_region", f"Semantic region '{region.name}' is duplicated.", f"semantic_regions[{idx}].name"))
            region_names.add(region.name)
            if region.source_feature and region.source_feature not in ids:
                issues.append(self._error("unknown_region_source", f"Region '{region.name}' references unknown source feature '{region.source_feature}'.", f"semantic_regions[{idx}].source_feature"))

        if expected_regions is not None:
            missing = sorted(expected_regions - region_names)
            extra = sorted(region_names - expected_regions)
            if missing:
                issues.append(self._error("missing_semantic_regions", f"Feature plan does not define engineering semantic regions: {', '.join(missing)}.", "semantic_regions"))
            if extra:
                issues.append(ValidationIssue(
                    code="extra_semantic_regions",
                    message=f"Feature plan adds semantic regions not declared by the engineering model: {', '.join(extra)}.",
                    severity=IssueSeverity.WARNING,
                    kind=IssueKind.WARNING,
                    path="semantic_regions",
                ))

        errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
        if errors:
            return ValidationReport(status=ValidationStatus.NEEDS_CLARIFICATION, issues=issues)
        if issues:
            return ValidationReport(status=ValidationStatus.VALID_WITH_WARNINGS, issues=issues)
        return ValidationReport(status=ValidationStatus.VALID, issues=[])

    @staticmethod
    def _error(code: str, message: str, path: str) -> ValidationIssue:
        return ValidationIssue(code=code, message=message, severity=IssueSeverity.ERROR, kind=IssueKind.INVALID, path=path)
