from __future__ import annotations

import json
import math
import re
from pathlib import Path

from agentcad.models.boundary_conditions import BoundaryConditionType, DegreeOfFreedom
from agentcad.models.loads import LoadType
from agentcad.models.simulation import StructuralAnalysisSpec
from agentcad.validators.units import (
    convert_acceleration_to_mm_s2,
    convert_density_to_tonne_mm3,
    convert_force_to_n,
    convert_length_to_mm,
    convert_stress_to_mpa,
)


class CalculiXModelBuilderError(RuntimeError):
    pass


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name).upper()[:60]


def _id_lines(ids: list[int], width: int = 16) -> list[str]:
    return [", ".join(str(v) for v in ids[i:i+width]) for i in range(0, len(ids), width)]


class CalculiXModelBuilder:
    """Adds deterministic material/BC/load/step cards to the Gmsh Abaqus mesh."""

    def build(self, base_mesh_inp: str | Path, mesh_metadata: str | Path, analysis: StructuralAnalysisSpec, output_dir: str | Path, job_name: str = "agentcad_model") -> Path:
        base = Path(base_mesh_inp)
        metadata = json.loads(Path(mesh_metadata).read_text(encoding="utf-8"))
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        target = out / f"{job_name}.inp"

        lines = [base.read_text(encoding="utf-8", errors="ignore").rstrip(), "", "** AgentCAD v3 deterministic CalculiX section"]
        element_ids = [int(v) for v in metadata.get("volume_element_ids", [])]
        if not element_ids:
            raise CalculiXModelBuilderError("Mesh metadata has no volume elements.")

        lines += ["*ELSET, ELSET=AGENTCAD_ALL_VOLUME", *_id_lines(element_ids)]
        regions = metadata.get("regions", {})
        for name, data in regions.items():
            ids = [int(v) for v in data.get("node_ids", [])]
            if ids:
                lines += [f"*NSET, NSET=AGENTCAD_{_safe(name)}", *_id_lines(ids)]

        E = convert_stress_to_mpa(analysis.material.young_modulus)
        nu = float(analysis.material.poisson_ratio.value)
        density = convert_density_to_tonne_mm3(analysis.material.density)
        lines += [
            "*MATERIAL, NAME=AGENTCAD_MAT",
            "*ELASTIC",
            f"{E:.12g}, {nu:.12g}",
            "*DENSITY",
            f"{density:.12g}",
            "*SOLID SECTION, ELSET=AGENTCAD_ALL_VOLUME, MATERIAL=AGENTCAD_MAT",
            "",
            "*STEP",
            "*STATIC",
        ]

        boundary_lines: list[str] = []
        for bc in analysis.boundary_conditions:
            region_name = f"AGENTCAD_{_safe(bc.target_region)}"
            if not regions.get(bc.target_region, {}).get("node_ids"):
                raise CalculiXModelBuilderError(f"Boundary-condition region '{bc.target_region}' has no mesh nodes.")
            if bc.bc_type == BoundaryConditionType.FIXED:
                boundary_lines.append(f"{region_name}, 1, 3")
            else:
                for dof in bc.constrained_dofs:
                    idx = {DegreeOfFreedom.UX: 1, DegreeOfFreedom.UY: 2, DegreeOfFreedom.UZ: 3}.get(dof)
                    if idx is None:
                        raise CalculiXModelBuilderError("Rotational prescribed DOFs are not supported for solid_3d.")
                    q = bc.values.get(dof.value) or bc.values.get(dof.name) or bc.values.get(str(dof.value))
                    if q is None:
                        raise CalculiXModelBuilderError(f"Prescribed displacement '{bc.id}' lacks a value for {dof.value}.")
                    boundary_lines.append(f"{region_name}, {idx}, {idx}, {convert_length_to_mm(q):.12g}")
        if boundary_lines:
            lines += ["*BOUNDARY", *boundary_lines]

        cload_lines: list[str] = []
        dload_lines: list[str] = []
        for load in analysis.loads:
            if load.load_type == LoadType.FORCE:
                if not load.target_region or load.target_region not in regions:
                    raise CalculiXModelBuilderError(f"Force '{load.id}' requires a resolved target surface region.")
                data = regions[load.target_region]
                weights = {int(k): float(v) for k, v in data.get("nodal_area_mm2", {}).items()}
                if not weights:
                    ids = [int(v) for v in data.get("node_ids", [])]
                    weights = {nid: 1.0 for nid in ids}
                total_w = sum(weights.values())
                if total_w <= 0:
                    raise CalculiXModelBuilderError(f"Force region '{load.target_region}' has zero nodal weight.")
                direction = load.direction
                if direction is None:
                    raise CalculiXModelBuilderError(f"Force '{load.id}' requires a direction vector.")
                norm = math.sqrt(direction.x**2 + direction.y**2 + direction.z**2)
                if norm <= 0:
                    raise CalculiXModelBuilderError(f"Force '{load.id}' direction vector is zero.")
                unit = (direction.x/norm, direction.y/norm, direction.z/norm)
                total_force = convert_force_to_n(load.magnitude)
                for node, weight in weights.items():
                    fi = total_force * weight / total_w
                    for dof, comp in enumerate(unit, start=1):
                        if abs(comp) > 1e-15:
                            cload_lines.append(f"{node}, {dof}, {fi*comp:.12g}")

            elif load.load_type == LoadType.PRESSURE:
                if not load.target_region or load.target_region not in regions:
                    raise CalculiXModelBuilderError(f"Pressure '{load.id}' requires a resolved target surface region.")
                pressure = convert_stress_to_mpa(load.magnitude)
                groups: dict[str, list[int]] = {}
                for item in regions[load.target_region].get("element_faces", []):
                    groups.setdefault(item["face"], []).append(int(item["element"]))
                if not groups:
                    raise CalculiXModelBuilderError(f"Pressure region '{load.target_region}' could not be mapped to tetrahedral element faces.")
                for face, ids in sorted(groups.items()):
                    elset = f"AGENTCAD_{_safe(load.target_region)}_{face}"
                    lines += [f"*ELSET, ELSET={elset}", *_id_lines(sorted(set(ids)))]
                    dload_lines.append(f"{elset}, {face}, {pressure:.12g}")

            elif load.load_type == LoadType.GRAVITY:
                if load.direction is None:
                    raise CalculiXModelBuilderError("Gravity requires direction.")
                norm = math.sqrt(load.direction.x**2 + load.direction.y**2 + load.direction.z**2)
                if norm <= 0:
                    raise CalculiXModelBuilderError("Gravity direction is zero.")
                a = convert_acceleration_to_mm_s2(load.magnitude)
                dload_lines.append(f"AGENTCAD_ALL_VOLUME, GRAV, {a:.12g}, {load.direction.x/norm:.12g}, {load.direction.y/norm:.12g}, {load.direction.z/norm:.12g}")
            else:
                raise CalculiXModelBuilderError(f"Load type '{load.load_type.value}' is not supported by the v3.0 solid backend.")

        if cload_lines:
            lines += ["*CLOAD", *cload_lines]
        if dload_lines:
            lines += ["*DLOAD", *dload_lines]

        lines += [
            "*NODE FILE",
            "U",
            "*EL FILE",
            "S, E",
            "*END STEP",
            "",
        ]
        target.write_text("\n".join(lines), encoding="utf-8")
        return target
