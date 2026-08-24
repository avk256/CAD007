import json
from pathlib import Path

from agentcad.config.settings import EngineSettings
from agentcad.engine.agentcad_engine import AgentCADEngine
from agentcad.models.feature_plan import GeometryFeaturePlan


def test_engine_can_execute_feature_plan_without_llm_key(tmp_path):
    example = Path(__file__).parents[1] / "examples" / "plate_feature_plan.json"
    plan = GeometryFeaturePlan.model_validate(json.loads(example.read_text(encoding="utf-8")))
    engine = AgentCADEngine(settings=EngineSettings(output_root=tmp_path / "runs"))
    result = engine.execute_feature_plan(plan, tmp_path / "deterministic")
    assert result.status == "geometry_complete"
    assert result.geometry_inspection["valid"] is True
    assert Path(result.artifacts["files"]["step"]).exists()
