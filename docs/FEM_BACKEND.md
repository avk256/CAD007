# Direct Gmsh + CalculiX backend

## Objective

The v3 FEM pipeline does not require FreeCAD:

```text
CadQuery/OCCT B-Rep
      ↓ STEP
Gmsh OpenCASCADE import
      ↓
3D tetrahedral mesh + semantic mesh metadata
      ↓
Deterministic CalculiX input writer
      ↓
ccx
      ↓
FRD/DAT/STA + result summary
```

## Supported v3.0-alpha model

- linear static structural analysis;
- homogeneous isotropic elasticity;
- 3D solid idealization;
- tetrahedral elements, first/second order requested through Gmsh;
- explicit or automatic global element size;
- local refinement by semantic surface where transferable;
- fixed translational BC;
- prescribed translational displacement;
- force distributed by boundary nodal area weights;
- pressure mapped to tetrahedral element faces;
- gravity.

## Semantic mesh metadata

After meshing, `mesh_metadata.json` stores for each transferred semantic surface:

- Gmsh surface entity tags;
- boundary node IDs;
- total approximated surface area;
- nodal area weights;
- mapping from each boundary triangle to the parent tetrahedral element and its CalculiX face label (`P1`–`P4`).

This metadata is the bridge between geometry semantics and solver entities.

## Current limitations

The direct backend is deliberately strict. Shell/beam elements, contacts, moments for solids, nonlinear material/geometry, modal/thermal/thermomechanical analysis and assemblies are not silently approximated. They should be implemented as explicit backend capabilities and validated before execution.

The current parser checks solver completion and output production. Field-level FRD parsing for maximum displacement, von Mises stress, extrema locations and tabular exports is the next CAE milestone.
