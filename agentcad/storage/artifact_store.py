from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class ArtifactStore:
    """Creates reproducible per-run workspaces and writes typed JSON artifacts."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create_run(self, request: str) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", request.strip()).strip("-").lower()[:36] or "run"
        run_dir = self.root / f"{stamp}_{slug}_{uuid.uuid4().hex[:8]}"
        for sub in ("specification", "geometry", "mesh", "solver", "results", "validation", "logs"):
            (run_dir / sub).mkdir(parents=True, exist_ok=True)
        return run_dir

    @staticmethod
    def write_json(path: str | Path, value: Any) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, BaseModel):
            payload = value.model_dump(mode="json")
        else:
            payload = value
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    @staticmethod
    def write_text(path: str | Path, text: str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target
