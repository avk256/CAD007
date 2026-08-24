from __future__ import annotations

from pathlib import Path

from agentcad.models.results import SimulationResultSummary


_FAILURE_MARKERS = ("singular", "zero pivot", "rigid body", "no convergence", "fatal error", "error")


class CalculiXResultParser:
    """Conservative result parser; numerical field extraction can be extended independently."""

    def parse(self, execution: dict) -> SimulationResultSummary:
        texts: list[str] = []
        for key in ("stdout", "stderr", "dat", "sta"):
            p = Path(execution.get(key, ""))
            if p.exists():
                texts.append(p.read_text(encoding="utf-8", errors="ignore"))
        combined = "\n".join(texts).lower()
        markers = [m for m in _FAILURE_MARKERS if m in combined]
        frd = Path(execution.get("frd", ""))
        success = execution.get("returncode") == 0 and frd.exists() and frd.stat().st_size > 0 and not markers
        notes = []
        if markers:
            notes.append("Solver markers: " + ", ".join(markers))
        if not frd.exists() or (frd.exists() and frd.stat().st_size == 0):
            notes.append("Non-empty FRD result file was not produced.")
        return SimulationResultSummary(success=success, notes=notes)
