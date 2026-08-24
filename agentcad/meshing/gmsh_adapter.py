from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from agentcad.models.feature_plan import GeometryFeaturePlan, RegionSelectorType, SemanticRegionRule
from agentcad.models.mesh import ElementOrder, MeshSizeMode, MeshSpec
from agentcad.validators.units import convert_length_to_mm


class GmshAdapterError(RuntimeError):
    pass


class GmshMeshAdapter:
    """Direct STEP/OCCT -> Gmsh tetrahedral mesh backend.

    The adapter also creates a solver-neutral metadata file with semantic region
    node sets and a mapping from boundary triangles to tetrahedral CalculiX faces.
    This lets the CalculiX writer apply BCs and pressure without FreeCAD FaceN ids.
    """

    def mesh(self, step_path: str | Path, feature_plan: GeometryFeaturePlan, mesh_spec: MeshSpec, output_dir: str | Path) -> dict[str, Any]:
        try:
            import gmsh
        except ImportError as exc:
            raise GmshAdapterError("Python package 'gmsh' is required for structural analysis.") from exc

        step_path = Path(step_path).resolve()
        out = Path(output_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)
        msh_path = out / "model.msh"
        base_inp = out / "mesh_base.inp"
        metadata_path = out / "mesh_metadata.json"
        warnings: list[str] = []

        gmsh.initialize()
        try:
            gmsh.model.add("AgentCAD_v3")
            imported = gmsh.model.occ.importShapes(str(step_path))
            gmsh.model.occ.synchronize()
            volumes = [tag for dim, tag in imported if dim == 3] or [tag for _, tag in gmsh.model.getEntities(3)]
            if not volumes:
                raise GmshAdapterError("STEP import produced no 3D volume.")

            all_points = gmsh.model.getEntities(0)
            if mesh_spec.global_size_mode == MeshSizeMode.EXPLICIT and mesh_spec.global_element_size.value is not None:
                global_size = convert_length_to_mm(mesh_spec.global_element_size)
            else:
                bbox = self._global_bbox(gmsh)
                global_size = max(bbox[3]-bbox[0], bbox[4]-bbox[1], bbox[5]-bbox[2]) / 20.0
            if all_points:
                gmsh.model.mesh.setSize(all_points, global_size)

            region_surface_tags: dict[str, list[int]] = {}
            for rule in feature_plan.semantic_regions:
                tags = self._resolve_surface_tags(gmsh, rule, warnings)
                region_surface_tags[rule.name] = tags

            for refinement in mesh_spec.local_refinements:
                tags = region_surface_tags.get(refinement.target_region, [])
                if not tags:
                    warnings.append(f"Local refinement region '{refinement.target_region}' did not resolve in Gmsh.")
                    continue
                size = convert_length_to_mm(refinement.element_size)
                points: set[tuple[int, int]] = set()
                for tag in tags:
                    for dimtag in gmsh.model.getBoundary([(2, tag)], combined=False, oriented=False, recursive=True):
                        if dimtag[0] == 0:
                            points.add(dimtag)
                if points:
                    gmsh.model.mesh.setSize(list(points), size)

            gmsh.model.mesh.generate(3)
            if mesh_spec.element_order == ElementOrder.SECOND:
                gmsh.model.mesh.setOrder(2)

            gmsh.write(str(msh_path))
            gmsh.write(str(base_inp))

            coords = self._node_coordinates(gmsh)
            volume_elements, face_lookup = self._tetra_face_lookup(gmsh)
            if not volume_elements:
                raise GmshAdapterError("No tetrahedral volume elements were found after meshing.")

            regions: dict[str, Any] = {}
            for name, tags in region_surface_tags.items():
                regions[name] = self._collect_region_mesh_data(gmsh, tags, coords, face_lookup, warnings)

            metadata = {
                "version": "3.0",
                "mesh_file": str(msh_path),
                "base_inp": str(base_inp),
                "global_size_mm": global_size,
                "element_order": (mesh_spec.element_order.value if mesh_spec.element_order else None),
                "volume_element_ids": volume_elements,
                "regions": regions,
                "warnings": warnings,
            }
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            return {"msh": str(msh_path), "base_inp": str(base_inp), "metadata": str(metadata_path), "warnings": warnings}
        finally:
            gmsh.finalize()

    @staticmethod
    def _global_bbox(gmsh) -> tuple[float, float, float, float, float, float]:
        boxes = [gmsh.model.getBoundingBox(dim, tag) for dim, tag in gmsh.model.getEntities(3)]
        return (
            min(b[0] for b in boxes), min(b[1] for b in boxes), min(b[2] for b in boxes),
            max(b[3] for b in boxes), max(b[4] for b in boxes), max(b[5] for b in boxes),
        )

    def _resolve_surface_tags(self, gmsh, rule: SemanticRegionRule, warnings: list[str]) -> list[int]:
        if rule.kind.value not in {"face", "surface_set"}:
            return []
        surfaces = [tag for _, tag in gmsh.model.getEntities(2)]
        sel = rule.selector

        if sel.selector_type == RegionSelectorType.EXTREME:
            return self._extreme_surfaces(gmsh, surfaces, (sel.axis or "Z").upper(), (sel.side or "max").lower(), sel.tolerance)

        if sel.selector_type == RegionSelectorType.CADQUERY:
            expr = (sel.expression or "").strip()
            if len(expr) == 2 and expr[0] in "<>" and expr[1].upper() in "XYZ":
                return self._extreme_surfaces(gmsh, surfaces, expr[1].upper(), "max" if expr[0] == ">" else "min", sel.tolerance)
            if expr.startswith("%"):
                wanted = expr[1:].lower()
                return [tag for tag in surfaces if wanted in str(gmsh.model.getType(2, tag)).lower()]
            warnings.append(f"Gmsh cannot translate CadQuery selector '{expr}' for region '{rule.name}'; region left unresolved.")
            return []

        if sel.selector_type == RegionSelectorType.SURFACE_TYPE:
            wanted = (sel.surface_type or "").lower()
            return [tag for tag in surfaces if wanted in str(gmsh.model.getType(2, tag)).lower()]

        warnings.append(f"Selector type '{sel.selector_type.value}' for region '{rule.name}' is not transferable through STEP.")
        return []

    def _extreme_surfaces(self, gmsh, surfaces: list[int], axis: str, side: str, tol: float) -> list[int]:
        idx = {"X": (0, 3), "Y": (1, 4), "Z": (2, 5)}[axis]
        boxes = {tag: gmsh.model.getBoundingBox(2, tag) for tag in surfaces}
        target = max(b[idx[1]] for b in boxes.values()) if side == "max" else min(b[idx[0]] for b in boxes.values())
        scale = max(1.0, abs(target))
        eps = max(tol, 1e-7 * scale)
        result = []
        for tag, b in boxes.items():
            value = b[idx[1]] if side == "max" else b[idx[0]]
            # Require the whole surface to lie on the extreme plane, not merely touch it.
            other = b[idx[0]] if side == "max" else b[idx[1]]
            if abs(value - target) <= eps and abs(other - target) <= eps:
                result.append(tag)
        return result

    @staticmethod
    def _node_coordinates(gmsh) -> dict[int, tuple[float, float, float]]:
        tags, xyz, _ = gmsh.model.mesh.getNodes()
        return {int(tags[i]): (float(xyz[3*i]), float(xyz[3*i+1]), float(xyz[3*i+2])) for i in range(len(tags))}

    @staticmethod
    def _tetra_face_lookup(gmsh) -> tuple[list[int], dict[tuple[int, int, int], tuple[int, str]]]:
        element_ids: list[int] = []
        lookup: dict[tuple[int, int, int], tuple[int, str]] = {}
        types, tag_blocks, node_blocks = gmsh.model.mesh.getElements(3)
        face_defs = [((0, 1, 2), "P1"), ((0, 3, 1), "P2"), ((1, 3, 2), "P3"), ((2, 3, 0), "P4")]
        for etype, tags, nodes in zip(types, tag_blocks, node_blocks):
            name, dim, order, num_nodes, _, num_primary = gmsh.model.mesh.getElementProperties(etype)
            if dim != 3 or num_primary != 4:
                continue
            for i, etag in enumerate(tags):
                conn = [int(v) for v in nodes[i*num_nodes:(i+1)*num_nodes]]
                primary = conn[:4]
                eid = int(etag)
                element_ids.append(eid)
                for inds, label in face_defs:
                    key = tuple(sorted(primary[j] for j in inds))
                    lookup[key] = (eid, label)
        return element_ids, lookup

    def _collect_region_mesh_data(self, gmsh, surface_tags: list[int], coords: dict[int, tuple[float, float, float]], face_lookup: dict[tuple[int, int, int], tuple[int, str]], warnings: list[str]) -> dict[str, Any]:
        nodes: set[int] = set()
        element_faces: list[dict[str, Any]] = []
        nodal_area: dict[int, float] = {}
        total_area = 0.0

        for s in surface_tags:
            ntags, _, _ = gmsh.model.mesh.getNodes(2, s, includeBoundary=True)
            nodes.update(int(n) for n in ntags)
            types, tag_blocks, node_blocks = gmsh.model.mesh.getElements(2, s)
            for etype, tags, block in zip(types, tag_blocks, node_blocks):
                name, dim, order, num_nodes, _, num_primary = gmsh.model.mesh.getElementProperties(etype)
                if dim != 2 or num_primary != 3:
                    continue
                for i, _ in enumerate(tags):
                    conn = [int(v) for v in block[i*num_nodes:(i+1)*num_nodes]]
                    tri = conn[:3]
                    key = tuple(sorted(tri))
                    mapped = face_lookup.get(key)
                    if mapped:
                        element_faces.append({"element": mapped[0], "face": mapped[1]})
                    else:
                        warnings.append(f"Boundary triangle {key} could not be mapped to a tetrahedral face.")
                    try:
                        area = self._triangle_area(coords[tri[0]], coords[tri[1]], coords[tri[2]])
                        total_area += area
                        for n in tri:
                            nodal_area[n] = nodal_area.get(n, 0.0) + area / 3.0
                    except KeyError:
                        pass
        return {
            "surface_tags": sorted(surface_tags),
            "node_ids": sorted(nodes),
            "element_faces": element_faces,
            "nodal_area_mm2": {str(k): v for k, v in nodal_area.items()},
            "surface_area_mm2": total_area,
        }

    @staticmethod
    def _triangle_area(a, b, c) -> float:
        ux, uy, uz = b[0]-a[0], b[1]-a[1], b[2]-a[2]
        vx, vy, vz = c[0]-a[0], c[1]-a[1], c[2]-a[2]
        cx, cy, cz = uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx
        return 0.5 * math.sqrt(cx*cx + cy*cy + cz*cz)
