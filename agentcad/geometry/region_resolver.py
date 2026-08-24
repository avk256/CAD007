from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cadquery as cq

from agentcad.geometry.compiler import GeometryBuildResult
from agentcad.models.feature_plan import RegionSelectorType, SemanticRegionRule
from agentcad.models.geometry import RegionKind


class RegionResolutionError(RuntimeError):
    pass


@dataclass
class ResolvedRegion:
    name: str
    kind: RegionKind
    count: int
    objects: list[Any]
    source_feature: str | None = None


class SemanticRegionResolver:
    """Resolves stable semantic names to B-Rep entities after deterministic construction."""

    def resolve_all(self, build: GeometryBuildResult) -> dict[str, ResolvedRegion]:
        result: dict[str, ResolvedRegion] = {}
        for rule in build.plan.semantic_regions:
            result[rule.name] = self.resolve(rule, build)
        return result

    def resolve(self, rule: SemanticRegionRule, build: GeometryBuildResult) -> ResolvedRegion:
        source = build.objects.get(rule.source_feature) if rule.source_feature else build.root
        if source is None:
            raise RegionResolutionError(f"Source feature '{rule.source_feature}' for region '{rule.name}' is missing.")

        selector = rule.selector
        wp = self._entity_workplane(source, rule.kind)

        if selector.selector_type == RegionSelectorType.CADQUERY:
            if not selector.expression:
                raise RegionResolutionError(f"Region '{rule.name}' requires a CadQuery selector expression.")
            wp = self._apply_selector(source, rule.kind, selector.expression)
        elif selector.selector_type == RegionSelectorType.EXTREME:
            axis = (selector.axis or "").upper()
            side = (selector.side or "").lower()
            if axis not in {"X", "Y", "Z"} or side not in {"min", "max"}:
                raise RegionResolutionError(f"Invalid extreme selector for region '{rule.name}'.")
            expr = (">" if side == "max" else "<") + axis
            wp = self._apply_selector(source, rule.kind, expr)
        elif selector.selector_type == RegionSelectorType.SURFACE_TYPE:
            if rule.kind not in {RegionKind.FACE, RegionKind.SURFACE_SET}:
                raise RegionResolutionError("surface_type selector is valid only for face regions.")
            st = (selector.surface_type or "").capitalize()
            wp = source.faces(f"%{st}")
        elif selector.selector_type == RegionSelectorType.SOURCE_FEATURE:
            wp = self._entity_workplane(source, rule.kind)
        else:
            raise RegionResolutionError(f"Unsupported selector type: {selector.selector_type}")

        vals = list(wp.vals())
        if selector.expected_count is not None and len(vals) != selector.expected_count:
            raise RegionResolutionError(
                f"Region '{rule.name}' resolved to {len(vals)} entities; expected {selector.expected_count}."
            )
        if not vals:
            raise RegionResolutionError(f"Region '{rule.name}' resolved to zero entities.")
        return ResolvedRegion(rule.name, rule.kind, len(vals), vals, rule.source_feature)

    @staticmethod
    def _entity_workplane(source: cq.Workplane, kind: RegionKind) -> cq.Workplane:
        if kind in {RegionKind.FACE, RegionKind.SURFACE_SET}:
            return source.faces()
        if kind in {RegionKind.EDGE, RegionKind.EDGE_SET}:
            return source.edges()
        if kind == RegionKind.VERTEX:
            return source.vertices()
        if kind == RegionKind.SOLID:
            return source.solids()
        raise RegionResolutionError(f"Unsupported region kind: {kind}")

    @staticmethod
    def _apply_selector(source: cq.Workplane, kind: RegionKind, expr: str) -> cq.Workplane:
        if kind in {RegionKind.FACE, RegionKind.SURFACE_SET}:
            return source.faces(expr)
        if kind in {RegionKind.EDGE, RegionKind.EDGE_SET}:
            return source.edges(expr)
        if kind == RegionKind.VERTEX:
            return source.vertices(expr)
        if kind == RegionKind.SOLID:
            return source.solids(expr)
        raise RegionResolutionError(f"Unsupported region kind: {kind}")
