from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cadquery as cq

from agentcad.models.feature_plan import FeatureOperation, FeatureStep, GeometryFeaturePlan
from agentcad.validators.feature_plan_validator import FeaturePlanValidator


class GeometryCompileError(RuntimeError):
    pass


@dataclass
class GeometryBuildResult:
    plan: GeometryFeaturePlan
    root: cq.Workplane
    objects: dict[str, cq.Workplane] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class CadQueryGeometryCompiler:
    """Deterministic compiler from AgentCAD GeometryFeaturePlan to CadQuery/OCCT."""

    def __init__(self, validator: FeaturePlanValidator | None = None):
        self.validator = validator or FeaturePlanValidator()

    def compile(self, plan: GeometryFeaturePlan) -> GeometryBuildResult:
        report = self.validator.validate(plan)
        if not report.is_valid:
            joined = "; ".join(i.message for i in report.issues)
            raise GeometryCompileError(f"Invalid feature plan: {joined}")

        objects: dict[str, cq.Workplane] = {}
        warnings: list[str] = []
        for step in plan.steps:
            try:
                objects[step.id] = self._execute(step, objects)
            except Exception as exc:
                raise GeometryCompileError(
                    f"Feature '{step.id}' ({step.operation.value}) failed: {exc}"
                ) from exc

        return GeometryBuildResult(plan=plan, root=objects[plan.root_feature], objects=objects, warnings=warnings)

    def _execute(self, step: FeatureStep, objects: dict[str, cq.Workplane]) -> cq.Workplane:
        op = step.operation
        p = step.parameters

        if op == FeatureOperation.BOX:
            centered = p.get("centered", [True, True, True])
            return cq.Workplane(p.get("plane", "XY")).box(float(p["x"]), float(p["y"]), float(p["z"]), centered=centered)

        if op == FeatureOperation.CYLINDER:
            radius = self._radius(p)
            return cq.Workplane(p.get("plane", "XY")).cylinder(float(p["height"]), radius, centered=p.get("centered", [True, True, False]))

        if op == FeatureOperation.CONE:
            return cq.Workplane(p.get("plane", "XY")).cone(float(p["height"]), float(p["radius1"]), float(p["radius2"]), centered=p.get("centered", [True, True, False]))

        if op == FeatureOperation.SPHERE:
            return cq.Workplane(p.get("plane", "XY")).sphere(float(p["radius"]))

        if op == FeatureOperation.EXTRUDE:
            wp = self._make_profile(p.get("plane", "XY"), p["profile"])
            return wp.extrude(float(p["distance"]), both=bool(p.get("both", False)), taper=float(p.get("taper", 0.0)))

        if op == FeatureOperation.REVOLVE:
            wp = self._make_profile(p.get("plane", "XZ"), p["profile"])
            return wp.revolve(
                angleDegrees=float(p.get("angle_deg", 360.0)),
                axisStart=tuple(p.get("axis_start", [0.0, 0.0])),
                axisEnd=tuple(p.get("axis_end", [0.0, 1.0])),
            )

        if op == FeatureOperation.HOLE:
            target = objects[step.target]
            selector = p.get("face_selector", ">Z")
            wp = target.faces(selector).workplane(centerOption=p.get("center_option", "CenterOfBoundBox"))
            positions = p.get("positions", [[0.0, 0.0]])
            wp = wp.pushPoints([tuple(map(float, xy)) for xy in positions])
            diameter = float(p["diameter"])
            depth = p.get("depth")
            if depth is None:
                return wp.hole(diameter)
            return wp.hole(diameter, float(depth))

        if op in {FeatureOperation.CUT, FeatureOperation.FUSE, FeatureOperation.INTERSECT}:
            operands = [objects[i] for i in step.inputs]
            result = operands[0]
            for other in operands[1:]:
                if op == FeatureOperation.CUT:
                    result = result.cut(other)
                elif op == FeatureOperation.FUSE:
                    result = result.union(other)
                else:
                    result = result.intersect(other)
            return result

        if op == FeatureOperation.FILLET:
            target = objects[step.target]
            edges = target.edges(p.get("edge_selector", "*")) if p.get("edge_selector") else target.edges()
            return edges.fillet(float(p["radius"]))

        if op == FeatureOperation.CHAMFER:
            target = objects[step.target]
            edges = target.edges(p.get("edge_selector", "*")) if p.get("edge_selector") else target.edges()
            length2 = p.get("length2")
            if length2 is None:
                return edges.chamfer(float(p["length"]))
            return edges.chamfer(float(p["length"]), float(length2))

        if op == FeatureOperation.TRANSLATE:
            return objects[step.target].translate(tuple(map(float, p["vector"])))

        if op == FeatureOperation.ROTATE:
            return objects[step.target].rotate(tuple(map(float, p["axis_start"])), tuple(map(float, p["axis_end"])), float(p["angle_deg"]))

        if op == FeatureOperation.MIRROR:
            return objects[step.target].mirror(mirrorPlane=p["plane"], basePointVector=tuple(map(float, p.get("base_point", [0, 0, 0]))), union=bool(p.get("union", False)))

        if op == FeatureOperation.LINEAR_PATTERN:
            return self._linear_pattern(objects[step.target], p)

        if op == FeatureOperation.CIRCULAR_PATTERN:
            return self._circular_pattern(objects[step.target], p)

        raise GeometryCompileError(f"Unsupported operation: {op}")

    @staticmethod
    def _radius(p: dict[str, Any]) -> float:
        if "radius" in p:
            return float(p["radius"])
        if "diameter" in p:
            return float(p["diameter"]) / 2.0
        raise GeometryCompileError("Cylinder requires radius or diameter.")

    @staticmethod
    def _make_profile(plane: str, profile: dict[str, Any]) -> cq.Workplane:
        wp = cq.Workplane(plane)
        offset = profile.get("offset")
        if offset:
            wp = wp.center(float(offset[0]), float(offset[1]))
        kind = str(profile.get("type", "")).lower()
        if kind == "rectangle":
            return wp.rect(float(profile["x"]), float(profile["y"]), centered=bool(profile.get("centered", True)))
        if kind == "circle":
            radius = float(profile.get("radius", float(profile["diameter"]) / 2.0 if "diameter" in profile else 0.0))
            if radius <= 0:
                raise GeometryCompileError("Circle profile requires positive radius or diameter.")
            return wp.circle(radius)
        if kind == "polygon":
            pts = [tuple(map(float, pt)) for pt in profile["points"]]
            return wp.polyline(pts).close()
        if kind == "regular_polygon":
            return wp.polygon(int(profile["sides"]), float(profile["diameter"]))
        raise GeometryCompileError(f"Unsupported profile type: {kind}")

    @staticmethod
    def _linear_pattern(target: cq.Workplane, p: dict[str, Any]) -> cq.Workplane:
        count = int(p["count"])
        if count < 1:
            raise GeometryCompileError("Pattern count must be >= 1.")
        spacing = float(p["spacing"])
        direction = tuple(map(float, p["direction"]))
        result = target
        for i in range(1, count):
            v = tuple(component * spacing * i for component in direction)
            result = result.union(target.translate(v))
        return result

    @staticmethod
    def _circular_pattern(target: cq.Workplane, p: dict[str, Any]) -> cq.Workplane:
        count = int(p["count"])
        if count < 1:
            raise GeometryCompileError("Pattern count must be >= 1.")
        axis_start = tuple(map(float, p["axis_start"]))
        axis_end = tuple(map(float, p["axis_end"]))
        total = float(p.get("angle_deg", 360.0))
        result = target
        for i in range(1, count):
            angle = total * i / count
            result = result.union(target.rotate(axis_start, axis_end, angle))
        return result
