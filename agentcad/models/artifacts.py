from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ArtifactManifest(BaseModel):
    output_dir: str
    files: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add(self, name: str, path: str | Path) -> None:
        self.files[name] = str(Path(path))
