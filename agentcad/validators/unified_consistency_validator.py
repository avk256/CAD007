from __future__ import annotations

from agentcad.models.common import IssueKind, IssueSeverity, TaskIntent, ValidationStatus
from agentcad.models.geometry import GeometrySpec
from agentcad.models.mesh import ElementFamily, ModelDimension, ModelIdealization
from agentcad.models.simulation import StructuralAnalysisSpec
from agentcad.models.validation import ValidationIssue, ValidationReport


class UnifiedConsistencyValidator:
    """Deterministic engineering validation before any CAD execution."""

    def validate(self, geometry: GeometrySpec, structural: StructuralAnalysisSpec | None, task_intent: TaskIntent) -> ValidationReport:
        issues: list[ValidationIssue] = []
        issues.extend(self._geometry_issues(geometry))
        if task_intent == TaskIntent.GEOMETRY_AND_STRUCTURAL_ANALYSIS:
            if structural is None or not structural.enabled:
                issues.append(self._error("missing_structural_analysis", "Structural analysis was requested but no enabled analysis specification was produced.", "structural_analysis"))
            else:
                issues.extend(self._structural_issues(geometry, structural))

        errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
        warnings = [i for i in issues if i.severity == IssueSeverity.WARNING]
        if errors:
            if any(i.kind == IssueKind.UNSUPPORTED for i in errors):
                status = ValidationStatus.UNSUPPORTED
            elif any(i.kind == IssueKind.CONFLICT for i in errors):
                status = ValidationStatus.CONFLICT
            else:
                status = ValidationStatus.NEEDS_CLARIFICATION
        elif warnings:
            status = ValidationStatus.VALID_WITH_WARNINGS
        else:
            status = ValidationStatus.VALID
        return ValidationReport(status=status, issues=issues)

    def _geometry_issues(self, geometry: GeometrySpec) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not geometry.features:
            issues.append(self._error("geometry_has_no_features", "Geometry specification contains no buildable features.", "geometry.features"))
        names = [r.name for r in geometry.semantic_regions]
        if len(names) != len(set(names)):
            issues.append(self._error("duplicate_semantic_region", "Semantic region names must be unique.", "geometry.semantic_regions"))
        for pi in geometry.unresolved_issues:
            issues.append(ValidationIssue(
                code=pi.code,
                message=pi.message,
                severity=IssueSeverity.ERROR,
                kind=pi.kind,
                path="geometry",
                suggested_question=pi.suggested_question,
            ))
        return issues

    def _structural_issues(self, geometry: GeometrySpec, s: StructuralAnalysisSpec) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        regions = {r.name for r in geometry.semantic_regions}
        mat = s.material
        for path, q in [
            ("structural_analysis.material.density", mat.density),
            ("structural_analysis.material.young_modulus", mat.young_modulus),
            ("structural_analysis.material.poisson_ratio", mat.poisson_ratio),
        ]:
            if q.value is None:
                issues.append(self._error("missing_material_parameter", f"Required material parameter '{q.name}' is missing.", path, f"What value should be used for {q.name}?"))
        if mat.poisson_ratio.value is not None and not (-1.0 < mat.poisson_ratio.value < 0.5):
            issues.append(self._error("invalid_poisson_ratio", "Poisson ratio for stable isotropic linear elasticity must satisfy -1 < nu < 0.5.", "structural_analysis.material.poisson_ratio"))
        if mat.young_modulus.value is not None and mat.young_modulus.value <= 0:
            issues.append(self._error("invalid_young_modulus", "Young's modulus must be positive.", "structural_analysis.material.young_modulus"))

        if not s.boundary_conditions:
            issues.append(self._error("missing_boundary_conditions", "At least one boundary condition is required to remove rigid-body motion.", "structural_analysis.boundary_conditions"))
        if not s.loads and not any(bc.bc_type.value == "prescribed_displacement" for bc in s.boundary_conditions):
            issues.append(self._error("missing_load", "At least one load or prescribed displacement is required.", "structural_analysis.loads"))

        for i, bc in enumerate(s.boundary_conditions):
            if bc.target_region not in regions:
                issues.append(self._error("unknown_bc_region", f"Boundary condition '{bc.id}' references unknown semantic region '{bc.target_region}'.", f"structural_analysis.boundary_conditions[{i}].target_region"))
        for i, load in enumerate(s.loads):
            if load.target_region and load.target_region not in regions:
                issues.append(self._error("unknown_load_region", f"Load '{load.id}' references unknown semantic region '{load.target_region}'.", f"structural_analysis.loads[{i}].target_region"))

        mesh = s.mesh
        if mesh.idealization != ModelIdealization.SOLID_3D:
            issues.append(self._unsupported("unsupported_idealization", "AgentCAD v3.0 direct Gmsh/CalculiX backend currently supports solid_3d only.", "structural_analysis.mesh.idealization"))
        if mesh.dimension != ModelDimension.D3:
            issues.append(self._error("mesh_dimension_mismatch", "solid_3d requires a 3D mesh.", "structural_analysis.mesh.dimension"))
        if mesh.element_family != ElementFamily.TETRAHEDRON:
            issues.append(self._unsupported("unsupported_element_family", "AgentCAD v3.0 direct backend currently supports tetrahedral solid elements.", "structural_analysis.mesh.element_family"))
        if mesh.global_size_mode.value == "explicit" and mesh.global_element_size.value is None:
            issues.append(self._error("missing_mesh_size", "Explicit mesh-size mode requires global_element_size.", "structural_analysis.mesh.global_element_size"))

        for pi in s.unresolved_issues + mat.unresolved_issues:
            issues.append(ValidationIssue(code=pi.code, message=pi.message, severity=IssueSeverity.ERROR, kind=pi.kind, path="structural_analysis", suggested_question=pi.suggested_question))
        return issues

    @staticmethod
    def _error(code: str, message: str, path: str, question: str | None = None) -> ValidationIssue:
        return ValidationIssue(code=code, message=message, severity=IssueSeverity.ERROR, kind=IssueKind.INVALID, path=path, suggested_question=question)

    @staticmethod
    def _unsupported(code: str, message: str, path: str) -> ValidationIssue:
        return ValidationIssue(code=code, message=message, severity=IssueSeverity.ERROR, kind=IssueKind.UNSUPPORTED, path=path)
