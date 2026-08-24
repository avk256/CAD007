from agentcad.models.common import TaskIntent
from agentcad.models.geometry import GeometryFeature, GeometrySpec
from agentcad.models.simulation import StructuralAnalysisSpec
from agentcad.validators.unified_consistency_validator import UnifiedConsistencyValidator


def test_geometry_only_valid():
    geometry = GeometrySpec(summary="box", features=[GeometryFeature(id="base", feature_type="box", description="box")])
    report = UnifiedConsistencyValidator().validate(geometry, StructuralAnalysisSpec(enabled=False), TaskIntent.GEOMETRY_ONLY)
    assert report.is_valid
