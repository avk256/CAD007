from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Optional

from agentcad.models.artifacts import ArtifactManifest, ExecutionResult
from agentcad.validators.code_validator import CodeValidator


class FreeCADExecutor:
    """Deterministic execution tool for generated FreeCAD Python."""

    def __init__(
        self,
        freecad_cmd: Optional[str] = None,
        timeout_seconds: int = 300,
        code_validator: CodeValidator | None = None,
    ):
        self._freecad_cmd_explicit = freecad_cmd
        self._freecad_cmd_resolved: Optional[str] = None
        self.timeout_seconds = timeout_seconds
        self.code_validator = code_validator or CodeValidator()

    @staticmethod
    def find_freecad_cmd(explicit: Optional[str] = None) -> str:
        candidates: list[str] = []
        if explicit:
            candidates.append(explicit)
        for name in ("FreeCADCmd", "freecadcmd"):
            found = shutil.which(name)
            if found:
                candidates.append(found)
        for item in candidates:
            resolved = shutil.which(item) or item
            if Path(resolved).exists():
                return str(Path(resolved).resolve())
        raise FileNotFoundError(
            "FreeCADCmd/freecadcmd not found. Set FREECAD_CMD or EngineSettings.freecad_cmd."
        )

    @staticmethod
    def collect_artifacts(output_dir: Path) -> ArtifactManifest:
        result = ArtifactManifest()
        if not output_dir.exists():
            return result
        for path in sorted(p for p in output_dir.rglob("*") if p.is_file()):
            suffix = path.suffix.lower()
            value = str(path.resolve())
            if suffix == ".stl": result.stl.append(value)
            elif suffix in {".step", ".stp"}: result.step.append(value)
            elif suffix == ".fcstd": result.fcstd.append(value)
            elif suffix in {".py", ".fcmacro"}: result.python.append(value)
            elif suffix == ".log": result.logs.append(value)
            elif suffix in {".frd", ".dat", ".inp", ".sta", ".cvg"}: result.fem.append(value)
            elif path.name == "agentcad_fem_summary.json": result.fem.append(value)
            else: result.other.append(value)
        return result

    def execute(self, code: str, output_dir: str | Path, attempt: int) -> ExecutionResult:
        workdir = Path(output_dir).expanduser().resolve()
        workdir.mkdir(parents=True, exist_ok=True)
        script_path = workdir / f"generated_attempt_{attempt}.py"
        script_path.write_text(code + "\n", encoding="utf-8")

        validation = self.code_validator.validate(code)
        if not validation.passed:
            reason = "Static code validation failed: " + "; ".join(validation.issues)
            return ExecutionResult(
                success=False, return_code=125, stderr=reason, reason=reason,
                script_path=str(script_path), artifacts=self.collect_artifacts(workdir),
            )

        if self._freecad_cmd_resolved is None:
            self._freecad_cmd_resolved = self.find_freecad_cmd(self._freecad_cmd_explicit)
        command = [self._freecad_cmd_resolved, str(script_path)]
        try:
            completed = subprocess.run(
                command,
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            return_code = completed.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            return_code = 124
            reason = f"FreeCAD execution exceeded {self.timeout_seconds} seconds."
            self._write_log(workdir, attempt, return_code, reason, stdout, stderr)
            return ExecutionResult(
                success=False, return_code=return_code, stdout=stdout, stderr=stderr,
                reason=reason, command=command, script_path=str(script_path),
                artifacts=self.collect_artifacts(workdir),
            )
        except OSError as exc:
            reason = f"Could not start FreeCADCmd: {exc}"
            return ExecutionResult(
                success=False, return_code=127, stderr=str(exc), reason=reason,
                command=command, script_path=str(script_path),
                artifacts=self.collect_artifacts(workdir),
            )

        combined = f"{stdout}\n{stderr}"
        marker = "AGENTCAD_SUCCESS" in combined
        traceback = "Traceback (most recent call last)" in combined
        success = return_code == 0 and marker and not traceback
        if success:
            reason = "FreeCAD executed successfully."
            final_script = workdir / "generated_freecad_model.py"
            final_script.write_text(code + "\n", encoding="utf-8")
        elif return_code != 0:
            reason = f"FreeCAD returned exit code {return_code}."
        elif traceback:
            reason = "FreeCAD output contains a Python traceback."
        else:
            reason = "FreeCAD finished without AGENTCAD_SUCCESS."

        self._write_log(workdir, attempt, return_code, reason, stdout, stderr)
        return ExecutionResult(
            success=success, return_code=return_code, stdout=stdout, stderr=stderr,
            reason=reason, command=command, script_path=str(script_path),
            artifacts=self.collect_artifacts(workdir),
        )

    @staticmethod
    def _write_log(workdir: Path, attempt: int, return_code: int, reason: str, stdout: str, stderr: str) -> None:
        (workdir / f"freecad_attempt_{attempt}.log").write_text(
            textwrap.dedent(f"""
            Return code: {return_code}
            Reason: {reason}

            STDOUT:
            {stdout}

            STDERR:
            {stderr}
            """).strip(),
            encoding="utf-8",
        )
