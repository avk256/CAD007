from agentcad.models.common import ParameterSource, QuantityParameter
from agentcad.models.material import MaterialSpec
from agentcad.validators.material_validator import MaterialValidator


def valid_material():
    return MaterialSpec(
        name="steel",
        density=QuantityParameter(name="density", value=7850, unit="kg/m³", source=ParameterSource.USER_EXPLICIT),
        young_modulus=QuantityParameter(name="young_modulus", value=210, unit="GPa", source=ParameterSource.USER_EXPLICIT),
        poisson_ratio=QuantityParameter(name="poisson_ratio", value=0.3, unit="1", source=ParameterSource.USER_EXPLICIT),
    )


def test_valid_material_has_no_errors():
    issues = MaterialValidator().validate(valid_material())
    assert not [i for i in issues if i.severity.value == "error"]


def test_invalid_poisson_is_rejected():
    material = valid_material()
    material.poisson_ratio.value = 0.55
    issues = MaterialValidator().validate(material)
    assert any(i.code == "material.poisson_ratio.range" for i in issues)
