from agentcad.models.common import Dimensions3D, ParameterSource, QuantityParameter, TaskIntent
from agentcad.models.geometry import GeometryFeature, GeometrySpec, RegionKind, SemanticRegion
from agentcad.models.material import MaterialSpec
from agentcad.models.boundary_conditions import BoundaryConditionSpec, BoundaryConditionType
from agentcad.models.loads import LoadSpec, LoadType
from agentcad.models.mesh import ElementFamily, ElementOrder, MeshSizeMode, MeshSpec, ModelDimension, ModelIdealization
from agentcad.models.simulation import StructuralAnalysisSpec
from agentcad.validators.unified_consistency_validator import UnifiedConsistencyValidator


def geometry():
    return GeometrySpec(
        summary="plate",
        overall_dimensions_mm=Dimensions3D(x=80, y=40, z=3),
        features=[GeometryFeature(id="plate", feature_type="box", description="plate")],
        semantic_regions=[
            SemanticRegion(name="left_face", kind=RegionKind.FACE, description="left"),
            SemanticRegion(name="right_face", kind=RegionKind.FACE, description="right"),
        ],
    )


def structural():
    material = MaterialSpec(
        name="steel",
        density=QuantityParameter(name="density", value=7850, unit="kg/m³", source=ParameterSource.USER_EXPLICIT),
        young_modulus=QuantityParameter(name="young_modulus", value=210, unit="GPa", source=ParameterSource.USER_EXPLICIT),
        poisson_ratio=QuantityParameter(name="poisson_ratio", value=0.3, unit="1", source=ParameterSource.USER_EXPLICIT),
    )
    mesh = MeshSpec(
        dimension=ModelDimension.D3, idealization=ModelIdealization.SOLID_3D,
        element_family=ElementFamily.TETRAHEDRON, element_order=ElementOrder.SECOND,
        global_size_mode=MeshSizeMode.EXPLICIT,
        global_element_size=QuantityParameter(name="global_element_size", value=5, unit="mm", source=ParameterSource.USER_EXPLICIT),
    )
    return StructuralAnalysisSpec(
        enabled=True,
        material=material,
        boundary_conditions=[BoundaryConditionSpec(id="bc1", bc_type=BoundaryConditionType.FIXED, target_region="left_face")],
        loads=[LoadSpec(
            id="load1", load_type=LoadType.FORCE,
            magnitude=QuantityParameter(name="force", value=1000, unit="N", source=ParameterSource.USER_EXPLICIT),
            target_region="right_face", direction={"x": 0, "y": -1, "z": 0},
        )],
        mesh=mesh,
    )


def test_complete_structural_spec_is_valid():
    report = UnifiedConsistencyValidator().validate(
        geometry(), structural(), TaskIntent.GEOMETRY_AND_STRUCTURAL_ANALYSIS
    )
    assert report.status.value in {"valid", "valid_with_warnings"}


def test_geometry_only_does_not_require_fem_parameters():
    report = UnifiedConsistencyValidator().validate(
        geometry(), StructuralAnalysisSpec(enabled=False), TaskIntent.GEOMETRY_ONLY
    )
    assert report.status.value in {"valid", "valid_with_warnings"}
