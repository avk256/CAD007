from __future__ import annotations

from pathlib import Path

import cadquery as cq

from agentcad.geometry.compiler import GeometryBuildResult
from agentcad.models.artifacts import ArtifactManifest


class GeometryExporter:
    def export(self, build: GeometryBuildResult, output_dir: str | Path, basename: str = "model") -> ArtifactManifest:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        manifest = ArtifactManifest(output_dir=str(out))

        step = out / f"{basename}.step"
        stl = out / f"{basename}.stl"
        cq.exporters.export(build.root, str(step))
        cq.exporters.export(build.root, str(stl))
        manifest.add("step", step)
        manifest.add("stl", stl)

        # glTF export in CadQuery is assembly-oriented. Wrapping a part in a one-item
        # assembly gives the web UI a lightweight GLB artifact without changing B-Rep truth.
        try:
            glb = out / f"{basename}.glb"
            assy = cq.Assembly(name=basename)
            assy.add(build.root, name="part")
            assy.export(str(glb))
            if glb.exists() and glb.stat().st_size > 0:
                manifest.add("glb", glb)
        except Exception as exc:
            manifest.metadata["glb_warning"] = str(exc)

        return manifest
