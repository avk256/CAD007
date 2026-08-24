import json
from pathlib import Path

from agentcad.models.boundary_conditions import BoundaryConditionSpec, BoundaryConditionType
from agentcad.models.common import ParameterSource, QuantityParameter
from agentcad.models.loads import LoadSpec, LoadType
from agentcad.models.material import MaterialSpec
from agentcad.models.simulation import StructuralAnalysisSpec
from agentcad.solvers.calculix.model_builder import CalculiXModelBuilder


def q(name, value, unit):
    return QuantityParameter(name=name, value=value, unit=unit, source=ParameterSource.USER_EXPLICIT)


def test_calculix_builder_writes_semantic_bc_and_pressure(tmp_path):
    base = tmp_path / "mesh_base.inp"
    base.write_text("*NODE\n1,0,0,0\n2,1,0,0\n3,0,1,0\n4,0,0,1\n*ELEMENT,TYPE=C3D4\n1,1,2,3,4\n")
    metadata = tmp_path / "mesh_metadata.json"
    metadata.write_text(json.dumps({
        "volume_element_ids": [1],
        "regions": {
            "fixed_surface": {"node_ids": [1, 2, 3]},
            "pressure_surface": {
                "node_ids": [1, 2, 3],
                "element_faces": [{"element": 1, "face": "P1"}],
                "nodal_area_mm2": {"1": 0.2, "2": 0.2, "3": 0.2}
            }
        }
    }))
    analysis = StructuralAnalysisSpec(
        enabled=True,
        material=MaterialSpec(
            name="steel",
            density=q("density", 7850, "kg/m3"),
            young_modulus=q("young_modulus", 200, "GPa"),
            poisson_ratio=q("poisson_ratio", 0.3, "1"),
        ),
        boundary_conditions=[BoundaryConditionSpec(id="bc1", bc_type=BoundaryConditionType.FIXED, target_region="fixed_surface")],
        loads=[LoadSpec(id="p1", load_type=LoadType.PRESSURE, magnitude=q("pressure", 1.0, "MPa"), target_region="pressure_surface")],
    )
    target = CalculiXModelBuilder().build(base, metadata, analysis, tmp_path / "solver")
    text = target.read_text()
    assert "*MATERIAL, NAME=AGENTCAD_MAT" in text
    assert "AGENTCAD_FIXED_SURFACE, 1, 3" in text
    assert "AGENTCAD_PRESSURE_SURFACE_P1, P1, 1" in text
