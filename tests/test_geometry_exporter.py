import json
from pathlib import Path

from agentcad.geometry import CadQueryGeometryCompiler, GeometryExporter
from agentcad.models.feature_plan import GeometryFeaturePlan


def test_geometry_exporter_writes_step_stl_glb(tmp_path):
    example = Path(__file__).parents[1] / "examples" / "plate_feature_plan.json"
    plan = GeometryFeaturePlan.model_validate(json.loads(example.read_text(encoding="utf-8")))
    build = CadQueryGeometryCompiler().compile(plan)
    manifest = GeometryExporter().export(build, tmp_path)
    for key in ("step", "stl", "glb"):
        path = Path(manifest.files[key])
        assert path.exists()
        assert path.stat().st_size > 0
