#!/usr/bin/env python3
"""
Simple LangChain -> FreeCAD agent.

Workflow:
1. Accept a natural-language description of a CAD part.
2. Ask an LLM (OpenRouter or OpenAI via LangChain) to generate a FreeCAD Python script.
3. Perform a small static safety/syntax check.
4. Execute the generated script with FreeCADCmd/freecadcmd.
5. If execution fails, send the diagnostics back to the LLM and retry.
6. Report success/failure and keep every generated attempt in the output directory.

FreeCAD itself is expected to be installed on the host OS. This program does
not import FreeCAD into the Conda environment; it launches FreeCAD's own
headless Python interpreter as a subprocess.
"""

from __future__ import annotations

import argparse
import ast
import os
import py_compile
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Structured LLM output
# ---------------------------------------------------------------------------

class GeneratedFreeCADScript(BaseModel):
    """FreeCAD program produced by the language model."""

    summary: str = Field(
        description="Short description of the generated geometry and modeling approach."
    )
    script_code: str = Field(
        description="Complete executable Python script for FreeCADCmd, without Markdown fences."
    )


# ---------------------------------------------------------------------------
# FreeCAD execution result
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    success: bool
    returncode: int
    stdout: str
    stderr: str
    command: list[str]
    reason: str


# ---------------------------------------------------------------------------
# Basic safety checks for generated code
# ---------------------------------------------------------------------------

BLOCKED_IMPORT_ROOTS = {
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "urllib",
    "ftplib",
    "paramiko",
    "ctypes",
    "multiprocessing",
}

BLOCKED_CALL_NAMES = {
    "eval",
    "exec",
    "compile",
    "__import__",
}

BLOCKED_ATTRIBUTE_CALLS = {
    ("os", "system"),
    ("os", "popen"),
    ("os", "spawnl"),
    ("os", "spawnlp"),
    ("os", "spawnv"),
    ("os", "spawnvp"),
    ("shutil", "rmtree"),
}


def clean_code(text: str) -> str:
    """Remove accidental Markdown code fences."""
    code = text.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code = "\n".join(lines).strip()
    return code


def validate_generated_code(code: str) -> list[str]:
    """
    Lightweight guardrail.

    This is NOT a true sandbox. It prevents several obvious ways for generated
    code to invoke network/process APIs before handing the script to FreeCAD.
    """
    issues: list[str] = []

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"Python syntax error: {exc}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in BLOCKED_IMPORT_ROOTS:
                    issues.append(f"Blocked import: {alias.name}")

        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in BLOCKED_IMPORT_ROOTS:
                issues.append(f"Blocked import: {node.module}")

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALL_NAMES:
                issues.append(f"Blocked call: {node.func.id}()")

            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                pair = (node.func.value.id, node.func.attr)
                if pair in BLOCKED_ATTRIBUTE_CALLS:
                    issues.append(f"Blocked call: {pair[0]}.{pair[1]}()")

    return sorted(set(issues))


# ---------------------------------------------------------------------------
# LLM setup
# ---------------------------------------------------------------------------

def build_model(provider: str, model_name: str, temperature: float):
    provider = provider.lower().strip()

    if provider == "openrouter":
        if not os.getenv("OPENROUTER_API_KEY"):
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. "
                "Export it in the shell or place it in a .env file."
            )
        from langchain_openrouter import ChatOpenRouter

        return ChatOpenRouter(
            model=model_name,
            temperature=temperature,
            app_title="AgentCAD FreeCAD LangChain Agent",
        )

    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set. "
                "Export it in the shell or place it in a .env file."
            )
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
        )

    raise ValueError("provider must be either 'openrouter' or 'openai'")


SYSTEM_PROMPT = r"""
You are AgentCAD, a careful FreeCAD Python code generator.

Your job is to convert a user's natural-language description of a mechanical
part into a COMPLETE script that can be executed headlessly by FreeCADCmd.

Rules:
1. Generate plain Python for FreeCAD, not Markdown.
2. Prefer robust FreeCAD core modules such as:
   - import FreeCAD as App
   - import Part
   Use Mesh only when actually needed.
3. Do not use FreeCADGui, GUI commands, dialogs, or anything requiring a display.
4. Do not run shell commands, subprocesses, network calls, installers, or package managers.
5. Keep all dimensions in millimetres unless the user explicitly states otherwise.
6. Use deterministic geometry construction and descriptive object names.
7. Create/recompute a FreeCAD document and save it as an .FCStd file.
8. When appropriate, also export printable/manufacturing geometry as STL and/or STEP.
9. All generated files must be written inside the output directory supplied in the request.
10. Use pathlib.Path for filesystem path construction.
11. At the end, print exactly:
       AGENTCAD_SUCCESS
   only after the document has been recomputed and successfully saved/exported.
12. If the request is under-specified, choose conservative, simple engineering defaults
    and document those defaults as comments in the generated script.
13. Do not silently create extremely complex geometry. Prefer a simple valid model.
14. Code must run in headless FreeCAD and must not depend on external workbenches/add-ons
    unless the user explicitly requests them.
"""


def build_generation_chain(model):
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            (
                "human",
                """
MODE: {mode}

USER DESCRIPTION:
{description}

OUTPUT DIRECTORY:
{output_dir}

PREVIOUS SCRIPT (empty on first attempt):
{previous_script}

FREECAD EXECUTION DIAGNOSTICS (empty on first attempt):
{diagnostics}

Generate the complete corrected FreeCAD script.
""",
            ),
        ]
    )

    structured_model = model.with_structured_output(GeneratedFreeCADScript)
    return prompt | structured_model


# ---------------------------------------------------------------------------
# FreeCAD discovery/execution
# ---------------------------------------------------------------------------

def find_freecad_cmd(explicit: Optional[str] = None) -> str:
    candidates: list[str] = []

    if explicit:
        candidates.append(explicit)

    env_cmd = os.getenv("FREECAD_CMD")
    if env_cmd:
        candidates.append(env_cmd)

    for name in ("FreeCADCmd", "freecadcmd"):
        located = shutil.which(name)
        if located:
            candidates.append(located)

    for candidate in candidates:
        path = shutil.which(candidate) or candidate
        if Path(path).exists():
            return str(Path(path).resolve())

    raise FileNotFoundError(
        "FreeCAD command-line executable was not found. "
        "Install FreeCAD and/or set FREECAD_CMD=/full/path/to/FreeCADCmd."
    )


def run_freecad_script(
    freecad_cmd: str,
    script_path: Path,
    working_dir: Path,
    timeout_seconds: int,
) -> ExecutionResult:
    command = [freecad_cmd, str(script_path)]

    try:
        completed = subprocess.run(
            command,
            cwd=str(working_dir),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return ExecutionResult(
            success=False,
            returncode=124,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            command=command,
            reason=f"FreeCAD execution exceeded {timeout_seconds} seconds.",
        )
    except OSError as exc:
        return ExecutionResult(
            success=False,
            returncode=127,
            stdout="",
            stderr=str(exc),
            command=command,
            reason="Could not start FreeCADCmd.",
        )

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    combined = f"{stdout}\n{stderr}"

    marker_found = "AGENTCAD_SUCCESS" in combined
    traceback_found = "Traceback (most recent call last)" in combined

    success = completed.returncode == 0 and marker_found and not traceback_found

    if success:
        reason = "FreeCAD finished successfully and emitted AGENTCAD_SUCCESS."
    elif completed.returncode != 0:
        reason = f"FreeCAD returned non-zero exit code {completed.returncode}."
    elif traceback_found:
        reason = "A Python traceback was detected in FreeCAD output."
    else:
        reason = "FreeCAD finished without the required AGENTCAD_SUCCESS marker."

    return ExecutionResult(
        success=success,
        returncode=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        command=command,
        reason=reason,
    )


def diagnostics_text(result: ExecutionResult, limit: int = 14000) -> str:
    text = textwrap.dedent(
        f"""
        Return code: {result.returncode}
        Reason: {result.reason}

        STDOUT:
        {result.stdout}

        STDERR:
        {result.stderr}
        """
    ).strip()

    if len(text) > limit:
        text = text[-limit:]
        text = "[diagnostics truncated to last characters]\n" + text
    return text


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def run_agent(
    description: str,
    provider: str,
    model_name: str,
    output_dir: Path,
    max_attempts: int,
    temperature: float,
    freecad_cmd_arg: Optional[str],
    timeout_seconds: int,
    unsafe: bool,
) -> int:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    freecad_cmd = find_freecad_cmd(freecad_cmd_arg)
    model = build_model(provider, model_name, temperature)
    chain = build_generation_chain(model)

    print(f"[AgentCAD] Provider: {provider}")
    print(f"[AgentCAD] Model: {model_name}")
    print(f"[AgentCAD] FreeCAD CLI: {freecad_cmd}")
    print(f"[AgentCAD] Output directory: {output_dir}")
    print(f"[AgentCAD] Maximum attempts: {max_attempts}")

    previous_script = ""
    diagnostics = ""
    last_result: Optional[ExecutionResult] = None

    for attempt in range(1, max_attempts + 1):
        mode = "INITIAL GENERATION" if attempt == 1 else "REPAIR AFTER FAILED EXECUTION"
        print(f"\n[AgentCAD] Attempt {attempt}/{max_attempts}: {mode.lower()}...")

        generated = chain.invoke(
            {
                "mode": mode,
                "description": description,
                "output_dir": str(output_dir),
                "previous_script": previous_script,
                "diagnostics": diagnostics,
            }
        )

        code = clean_code(generated.script_code)

        attempt_path = output_dir / f"generated_attempt_{attempt}.py"
        attempt_path.write_text(code + "\n", encoding="utf-8")

        print(f"[AgentCAD] LLM summary: {generated.summary}")
        print(f"[AgentCAD] Generated script: {attempt_path}")

        if not unsafe:
            safety_issues = validate_generated_code(code)
            if safety_issues:
                diagnostics = (
                    "The generated script was NOT executed because it failed the "
                    "local static safety check:\n- "
                    + "\n- ".join(safety_issues)
                )
                previous_script = code
                print("[AgentCAD] Safety validation failed:")
                for issue in safety_issues:
                    print(f"  - {issue}")
                continue

        try:
            py_compile.compile(str(attempt_path), doraise=True)
        except py_compile.PyCompileError as exc:
            diagnostics = f"The generated script has a Python syntax/compile error:\n{exc}"
            previous_script = code
            print("[AgentCAD] Python compile check failed.")
            print(diagnostics)
            continue

        print("[AgentCAD] Running FreeCAD headlessly...")
        result = run_freecad_script(
            freecad_cmd=freecad_cmd,
            script_path=attempt_path,
            working_dir=output_dir,
            timeout_seconds=timeout_seconds,
        )
        last_result = result

        log_path = output_dir / f"freecad_attempt_{attempt}.log"
        log_path.write_text(
            diagnostics_text(result, limit=1_000_000),
            encoding="utf-8",
        )

        if result.success:
            final_path = output_dir / "generated_freecad_model.py"
            final_path.write_text(code + "\n", encoding="utf-8")

            print("\n[AgentCAD] SUCCESS")
            print(f"[AgentCAD] Final script: {final_path}")
            print(f"[AgentCAD] FreeCAD log: {log_path}")
            print("[AgentCAD] Generated files:")
            for path in sorted(output_dir.iterdir()):
                if path.is_file():
                    print(f"  - {path.name}")
            return 0

        print(f"[AgentCAD] FreeCAD failed: {result.reason}")
        print(f"[AgentCAD] Log: {log_path}")

        diagnostics = diagnostics_text(result)
        previous_script = code

    print("\n[AgentCAD] FAILED")
    print(f"[AgentCAD] Could not produce a successful FreeCAD model in {max_attempts} attempts.")

    if last_result:
        print(f"[AgentCAD] Last FreeCAD reason: {last_result.reason}")

    print(f"[AgentCAD] Inspect attempts and logs in: {output_dir}")
    return 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and execute FreeCAD scripts from natural language using LangChain."
    )
    parser.add_argument(
        "--description",
        "-d",
        help="Natural-language description of the part. If omitted, interactive input is used.",
    )
    parser.add_argument(
        "--provider",
        choices=("openrouter", "openai"),
        default=os.getenv("LLM_PROVIDER", "openrouter"),
        help="LLM provider. Default: env LLM_PROVIDER or openrouter.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("LLM_MODEL", ""),
        help="Model identifier. Can also be set via LLM_MODEL.",
    )
    parser.add_argument(
        "--output-dir",
        default="./agentcad_output",
        help="Directory for generated scripts, logs and CAD files.",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum generation/repair attempts. Default: 3.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="LLM temperature. Default: 0.0.",
    )
    parser.add_argument(
        "--freecad-cmd",
        default=None,
        help="Explicit path to FreeCADCmd/freecadcmd. Otherwise auto-detected.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="FreeCAD execution timeout in seconds. Default: 180.",
    )
    parser.add_argument(
        "--unsafe",
        action="store_true",
        help="Disable the lightweight static safety check for generated code.",
    )
    return parser.parse_args()


def default_model(provider: str) -> str:
    # Deliberately conservative, easy-to-change defaults.
    if provider == "openrouter":
        return "openai/gpt-5.5"
    return "gpt-5.5"


def main() -> int:
    load_dotenv()
    args = parse_args()

    description = (args.description or "").strip()
    if not description:
        print("Опишіть деталь, її форму та розміри.")
        description = input("> ").strip()

    if not description:
        print("[AgentCAD] Empty description.", file=sys.stderr)
        return 2

    model_name = args.model.strip() or default_model(args.provider)

    if args.max_attempts < 1:
        print("[AgentCAD] --max-attempts must be >= 1.", file=sys.stderr)
        return 2

    return run_agent(
        description=description,
        provider=args.provider,
        model_name=model_name,
        output_dir=Path(args.output_dir),
        max_attempts=args.max_attempts,
        temperature=args.temperature,
        freecad_cmd_arg=args.freecad_cmd,
        timeout_seconds=args.timeout,
        unsafe=args.unsafe,
    )


if __name__ == "__main__":
    raise SystemExit(main())
