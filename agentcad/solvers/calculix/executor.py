from __future__ import annotations

import subprocess
from pathlib import Path


class CalculiXExecutor:
    def __init__(self, executable: str = "ccx", timeout_seconds: int = 600):
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    def run(self, inp_path: str | Path) -> dict:
        inp = Path(inp_path).resolve()
        proc = subprocess.run(
            [self.executable, "-i", inp.stem],
            cwd=str(inp.parent),
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        stdout = inp.parent / f"{inp.stem}_ccx_stdout.txt"
        stderr = inp.parent / f"{inp.stem}_ccx_stderr.txt"
        stdout.write_text(proc.stdout or "", encoding="utf-8")
        stderr.write_text(proc.stderr or "", encoding="utf-8")
        return {
            "returncode": proc.returncode,
            "stdout": str(stdout),
            "stderr": str(stderr),
            "frd": str(inp.parent / f"{inp.stem}.frd"),
            "dat": str(inp.parent / f"{inp.stem}.dat"),
            "sta": str(inp.parent / f"{inp.stem}.sta"),
        }
