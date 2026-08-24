# GeometryFeaturePlan — AgentCAD v3 CAD IR

`GeometryFeaturePlan` is the contract between natural-language planning and deterministic CAD construction.

## Rules

1. Every step has a stable unique `id`.
2. Dependencies must reference previously defined steps.
3. `root_feature` identifies the final part/compound.
4. All dimensions are in the plan unit system; v3.0 uses millimetres internally.
5. No Python expressions, method names or executable source are permitted in the IR.
6. Semantic regions are defined independently from transient OCCT topology indices.

## Operations

| Operation | Purpose | Main parameters |
|---|---|---|
| `box` | rectangular solid | `x`, `y`, `z`, optional `centered` |
| `cylinder` | cylindrical solid | `height`, `radius` or `diameter` |
| `cone` | cone/frustum | `radius1`, `radius2`, `height` |
| `sphere` | sphere | `radius` |
| `extrude` | extruded profile | `profile`, `distance` |
| `revolve` | revolved profile | `profile`, optional axis/angle |
| `hole` | hole(s) on selected face | `diameter`, `face_selector`, `positions`, optional `depth` |
| `cut/fuse/intersect` | Boolean operations | `inputs` |
| `fillet/chamfer` | edge treatment | target + selector + size |
| `translate/rotate/mirror` | transform | target + transform data |
| `linear_pattern/circular_pattern` | repeated solids/features | target + count/spacing/axis |

## Profiles

v3.0 provides rectangle, circle, polygon and regular polygon profiles. More sophisticated sketch constraints can be added later without changing the LLM/executor separation.

## Semantic-region selectors

The resolver supports:

- CadQuery selector expressions such as `>Z`, `<X`, `%Cylinder`;
- explicit `extreme` selectors (`axis=X/Y/Z`, `side=min/max`);
- surface-type selectors;
- whole entities from a named source feature.

Each rule can declare `expected_count`. A mismatch is a deterministic verification failure instead of a silently changed boundary condition.

## STEP transfer constraint

B-Rep semantic resolution is richer than what survives a neutral STEP round trip. The direct Gmsh adapter currently transfers stable selector classes that can be reconstructed geometrically after import (extreme planar surfaces and surface type). More complex semantic regions should eventually be serialized as geometric fingerprints or passed through a native OCCT/Gmsh bridge.
