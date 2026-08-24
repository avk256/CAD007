from agentcad.models.feature_plan import FeatureOperation, FeatureStep, GeometryFeaturePlan
from agentcad.validators.feature_plan_validator import FeaturePlanValidator


def test_valid_box_plan():
    plan = GeometryFeaturePlan(
        root_feature="base",
        steps=[FeatureStep(id="base", operation=FeatureOperation.BOX, parameters={"x": 10, "y": 20, "z": 3})],
    )
    assert FeaturePlanValidator().validate(plan).is_valid


def test_rejects_forward_dependency():
    plan = GeometryFeaturePlan(
        root_feature="hole",
        steps=[
            FeatureStep(id="hole", operation=FeatureOperation.HOLE, target="base", parameters={"diameter": 3}),
            FeatureStep(id="base", operation=FeatureOperation.BOX, parameters={"x": 10, "y": 20, "z": 3}),
        ],
    )
    assert not FeaturePlanValidator().validate(plan).is_valid
