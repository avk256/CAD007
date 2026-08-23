from __future__ import annotations

from pathlib import Path

import numpy as np
from stl import mesh as stl_mesh

from agentcad.models.artifacts import STLInspectionReport
from agentcad.models.unified_specification import UnifiedModelSpecification


class STLInspector:
    """Deterministic STL mesh and expected-bounding-box inspection."""

    def __init__(self, relative_tolerance: float = 0.01, absolute_tolerance_mm: float = 0.15):
        self.relative_tolerance = relative_tolerance
        self.absolute_tolerance_mm = absolute_tolerance_mm

    def inspect(self, stl_path: str | Path, specification: UnifiedModelSpecification) -> STLInspectionReport:
        path = Path(stl_path)
        report = STLInspectionReport(stl_path=str(path.resolve()))
        if not path.is_file():
            report.errors.append("STL file does not exist.")
            return report

        try:
            model = stl_mesh.Mesh.from_file(str(path))
            vectors = np.asarray(model.vectors, dtype=float)
        except Exception as exc:
            report.errors.append(f"Cannot load STL: {exc}")
            return report

        if vectors.ndim != 3 or vectors.shape[0] == 0:
            report.errors.append("STL contains no triangles.")
            return report

        vertices = vectors.reshape(-1, 3)
        finite = bool(np.isfinite(vertices).all())
        report.triangle_count = int(vectors.shape[0])
        if not finite:
            report.errors.append("STL contains NaN or infinite coordinates.")

        xyz_min = vertices.min(axis=0)
        xyz_max = vertices.max(axis=0)
        dimensions = xyz_max - xyz_min
        report.bbox_min_mm = xyz_min.tolist()
        report.bbox_max_mm = xyz_max.tolist()
        report.dimensions_mm = dimensions.tolist()

        edge_a = vectors[:, 1] - vectors[:, 0]
        edge_b = vectors[:, 2] - vectors[:, 0]
        triangle_areas = 0.5 * np.linalg.norm(np.cross(edge_a, edge_b), axis=1)
        report.surface_area_mm2 = float(triangle_areas.sum())
        report.degenerate_triangles = int(np.count_nonzero(triangle_areas <= 1e-12))

        positive_dims = bool((dimensions > 1e-9).all())
        positive_area = bool(report.surface_area_mm2 and report.surface_area_mm2 > 0)
        report.checks.extend([
            {"name": "finite_coordinates", "passed": finite},
            {"name": "positive_dimensions", "passed": positive_dims},
            {"name": "positive_surface_area", "passed": positive_area},
        ])
        if report.degenerate_triangles:
            report.warnings.append(f"Degenerate triangles: {report.degenerate_triangles}.")

        expected = specification.geometry.overall_dimensions_mm
        bbox_ok = True
        if expected:
            expected_arr = np.array([expected.x, expected.y, expected.z], dtype=float)
            tolerance = np.maximum(
                self.absolute_tolerance_mm,
                self.relative_tolerance * expected_arr,
            )
            delta = np.abs(dimensions - expected_arr)
            bbox_ok = bool(np.all(delta <= tolerance))
            report.checks.append({
                "name": "expected_bbox",
                "passed": bbox_ok,
                "expected_mm": expected_arr.tolist(),
                "absolute_error_mm": delta.tolist(),
                "tolerance_mm": tolerance.tolist(),
            })
            if not bbox_ok:
                report.errors.append(
                    "STL bounding-box dimensions do not match UnifiedModelSpecification."
                )

        report.passed = finite and positive_dims and positive_area and bbox_ok
        return report
