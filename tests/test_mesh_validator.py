from agentcad.models.common import ParameterSource, QuantityParameter
from agentcad.models.mesh import (
    ElementFamily, ElementOrder, MeshSizeMode, MeshSpec, ModelDimension, ModelIdealization,
)
from agentcad.validators.mesh_validator import MeshValidator


def test_valid_3d_tetra_mesh():
    mesh = MeshSpec(
        dimension=ModelDimension.D3,
        idealization=ModelIdealization.SOLID_3D,
        element_family=ElementFamily.TETRAHEDRON,
        element_order=ElementOrder.SECOND,
        global_size_mode=MeshSizeMode.EXPLICIT,
        global_element_size=QuantityParameter(
            name="global_element_size", value=5, unit="mm", source=ParameterSource.USER_EXPLICIT,
        ),
    )
    issues = MeshValidator().validate(mesh, set())
    assert not [i for i in issues if i.severity.value == "error"]


def test_incompatible_family_is_rejected():
    mesh = MeshSpec(
        dimension=ModelDimension.D3,
        idealization=ModelIdealization.SOLID_3D,
        element_family=ElementFamily.TRIANGLE,
        element_order=ElementOrder.FIRST,
        global_size_mode=MeshSizeMode.AUTO,
    )
    issues = MeshValidator().validate(mesh, set())
    assert any(i.code == "mesh.family.incompatible" for i in issues)
