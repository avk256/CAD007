from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass(slots=True)
class CodeValidationResult:
    passed: bool
    issues: list[str] = field(default_factory=list)


class CodeValidator:
    """Static guardrail for generated FreeCAD Python; not a security sandbox."""

    blocked_import_roots = {
        "subprocess", "socket", "requests", "httpx", "urllib", "ftplib",
        "paramiko", "ctypes", "multiprocessing",
    }
    blocked_call_names = {"eval", "exec", "compile", "__import__"}
    blocked_attribute_calls = {
        ("os", "system"), ("os", "popen"), ("shutil", "rmtree"),
    }

    def validate(self, code: str) -> CodeValidationResult:
        issues: list[str] = []
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return CodeValidationResult(False, [f"Python syntax error: {exc}"])

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] in self.blocked_import_roots:
                        issues.append(f"Blocked import: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or '').split('.')[0]
                if root in self.blocked_import_roots:
                    issues.append(f"Blocked import: {node.module}")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in self.blocked_call_names:
                    issues.append(f"Blocked call: {node.func.id}()")
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    pair = (node.func.value.id, node.func.attr)
                    if pair in self.blocked_attribute_calls:
                        issues.append(f"Blocked call: {pair[0]}.{pair[1]}()")

        if "FreeCADGui" in code:
            issues.append("GUI-dependent FreeCADGui usage is not allowed in headless execution.")
        return CodeValidationResult(not issues, sorted(set(issues)))
