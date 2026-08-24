from agentcad.models.common import TaskIntent
from agentcad.models.simulation import StructuralAnalysisSpec
from .unified_consistency_validator import UnifiedConsistencyValidator

class GeometryValidator:
    def validate(self, geometry):
        return UnifiedConsistencyValidator().validate(geometry, StructuralAnalysisSpec(enabled=False), TaskIntent.GEOMETRY_ONLY)
