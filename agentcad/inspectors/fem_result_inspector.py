from __future__ import annotations

import json
from pathlib import Path

from agentcad.models.artifacts import FEMInspectionReport


class FEMResultInspector:
    """Deterministic, intentionally conservative inspection of solver artifacts."""

    _ERROR_MARKERS = (
        "singular", "zero pivot", "rigid body", "nan", "fatal error",
        "calculation stopped", "no convergence",
    )

    def inspect(self, output_dir: str | Path) -> FEMInspectionReport:
        root = Path(output_dir).resolve()
        report = FEMInspectionReport()
        summary_path = root / "agentcad_fem_summary.json"

        if summary_path.is_file():
            report.summary_path = str(summary_path)
            try:
                report.summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception as exc:
                report.errors.append(f"Cannot parse agentcad_fem_summary.json: {exc}")
            else:
                if not bool(report.summary.get("success")):
                    report.errors.append("Generated FEM summary reports success=false.")

        candidates = sorted(
            p for p in root.rglob("*")
            if p.is_file() and p.suffix.lower() in {".frd", ".dat", ".inp", ".sta", ".cvg"}
        )
        report.result_files = [str(p) for p in candidates]
        frd_files = [p for p in candidates if p.suffix.lower() == ".frd" and p.stat().st_size > 0]
        report.checks.append({"name": "nonempty_frd_result", "passed": bool(frd_files)})

        diagnostic_text = ""
        for path in candidates:
            if path.suffix.lower() in {".dat", ".sta", ".cvg"}:
                try:
                    diagnostic_text += "\n" + path.read_text(encoding="utf-8", errors="ignore")[-100_000:]
                except OSError:
                    pass
        lowered = diagnostic_text.lower()
        found = sorted({marker for marker in self._ERROR_MARKERS if marker in lowered})
        if found:
            report.errors.append("Solver diagnostics contain: " + ", ".join(found))
        report.checks.append({"name": "no_known_solver_error_markers", "passed": not found})

        summary_success = bool(report.summary.get("success")) if report.summary else None
        if summary_success is None:
            report.warnings.append(
                "agentcad_fem_summary.json is missing; result acceptance is based on solver artifacts only."
            )
        report.passed = bool(frd_files) and not report.errors and summary_success is not False
        return report
