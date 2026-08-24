import math

from agentcad.geometry import CadQueryGeometryCompiler
from agentcad.models.feature_plan import FeatureOperation, FeatureStep, GeometryFeaturePlan


def test_box_volume():
    plan = GeometryFeaturePlan(
        root_feature="base",
        steps=[FeatureStep(id="base", operation=FeatureOperation.BOX, parameters={"x": 10, "y": 20, "z": 3})],
    )
    result = CadQueryGeometryCompiler().compile(plan)
    assert math.isclose(result.root.val().Volume(), 600.0, rel_tol=1e-9)


def test_plate_with_four_through_holes():
    plan = GeometryFeaturePlan(
        root_feature="holes",
        steps=[
            FeatureStep(id="base", operation=FeatureOperation.BOX, parameters={"x": 80, "y": 40, "z": 3}),
            FeatureStep(
                id="holes",
                operation=FeatureOperation.HOLE,
                target="base",
                parameters={"diameter": 6, "face_selector": ">Z", "positions": [[-30, -10], [-30, 10], [30, -10], [30, 10]]},
            ),
        ],
    )
    result = CadQueryGeometryCompiler().compile(plan)
    expected = 80 * 40 * 3 - 4 * math.pi * 3**2 * 3
    assert math.isclose(result.root.val().Volume(), expected, rel_tol=1e-6)
