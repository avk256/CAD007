from __future__ import annotations

from agentcad.geometry.compiler import GeometryBuildResult
from agentcad.geometry.region_resolver import SemanticRegionResolver
from agentcad.models.results import GeometryInspectionReport


class GeometryInspector:
    def __init__(self, resolver: SemanticRegionResolver | None = None):
        self.resolver = resolver or SemanticRegionResolver()

    def inspect(self, build: GeometryBuildResult) -> GeometryInspectionReport:
        shape = build.root.val()
        bbox = shape.BoundingBox()
        center = shape.Center()
        warnings = list(build.warnings)
        semantic: dict[str, dict] = {}
        try:
            resolved = self.resolver.resolve_all(build)
            for name, region in resolved.items():
                entry = {
                    "kind": region.kind.value,
                    "count": region.count,
                    "source_feature": region.source_feature,
                }
                if region.kind.value in {"face", "surface_set"}:
                    area = 0.0
                    cx = cy = cz = 0.0
                    nx = ny = nz = 0.0
                    for face in region.objects:
                        a = float(face.Area())
                        c = face.Center()
                        area += a
                        cx += a * float(c.x); cy += a * float(c.y); cz += a * float(c.z)
                        try:
                            n = face.normalAt()
                            nx += a * float(n.x); ny += a * float(n.y); nz += a * float(n.z)
                        except Exception:
                            pass
                    if area > 0:
                        entry["area_mm2"] = area
                        entry["centroid_mm"] = {"x": cx/area, "y": cy/area, "z": cz/area}
                        norm = (nx*nx + ny*ny + nz*nz) ** 0.5
                        if norm > 0:
                            entry["average_normal"] = {"x": nx/norm, "y": ny/norm, "z": nz/norm}
                semantic[name] = entry
        except Exception as exc:
            warnings.append(f"Semantic-region resolution warning: {exc}")

        return GeometryInspectionReport(
            valid=bool(shape.isValid()),
            shape_type=shape.ShapeType(),
            solids=len(shape.Solids()),
            faces=len(shape.Faces()),
            edges=len(shape.Edges()),
            volume_mm3=float(shape.Volume()),
            area_mm2=float(shape.Area()),
            bbox_mm={"x": float(bbox.xlen), "y": float(bbox.ylen), "z": float(bbox.zlen)},
            center_mm={"x": float(center.x), "y": float(center.y), "z": float(center.z)},
            semantic_regions=semantic,
            warnings=warnings,
        )
