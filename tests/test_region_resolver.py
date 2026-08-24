from agentcad.geometry import CadQueryGeometryCompiler, SemanticRegionResolver
from agentcad.models.feature_plan import (
    FeatureOperation, FeatureStep, GeometryFeaturePlan,
    RegionSelector, RegionSelectorType, SemanticRegionRule,
)
from agentcad.models.geometry import RegionKind


def test_top_face_region():
    plan = GeometryFeaturePlan(
        root_feature="base",
        steps=[FeatureStep(id="base", operation=FeatureOperation.BOX, parameters={"x": 10, "y": 20, "z": 3})],
        semantic_regions=[
            SemanticRegionRule(
                name="top_surface",
                kind=RegionKind.FACE,
                selector=RegionSelector(selector_type=RegionSelectorType.CADQUERY, expression=">Z", expected_count=1),
            )
        ],
    )
    build = CadQueryGeometryCompiler().compile(plan)
    resolved = SemanticRegionResolver().resolve_all(build)
    assert resolved["top_surface"].count == 1
