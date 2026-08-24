# AgentCAD v3 roadmap

## v3.0 — CadQuery core

- typed `UnifiedEngineeringModel`;
- typed `GeometryFeaturePlan` CAD IR;
- deterministic CadQuery/OCCT compiler;
- semantic B-Rep regions and geometry inspection;
- STEP/STL/GLB artifacts;
- LangGraph planning/validation/execution boundaries;
- feature-plan repair loop;
- direct solid-3D Gmsh/CalculiX alpha backend.

## v3.1 — validated CAE

- integration benchmark on installed Gmsh/CalculiX;
- mesh-quality inspector (Jacobian/aspect/size statistics);
- FRD field parser: U, S, E, von Mises, extrema and locations;
- reaction-force extraction and equilibrium checks;
- mesh-convergence workflow;
- regression cases against analytical solutions and trusted FEM models.

## v3.2 — richer geometry semantics

- topology fingerprints (surface type + centroid + normal + area/radius + parent feature);
- stable transfer of compound semantic regions through OCCT/Gmsh;
- richer sketch/profile constraints;
- imported STEP components and geometry healing;
- collision/clearance verification.

## v3.3 — assemblies

- typed assembly model;
- components and transforms;
- mating/connection semantics;
- piping/component library;
- contacts and connector abstractions for CAE.

## v3.4 — advanced CAE and optimization

- shell and beam idealizations;
- modal and thermal/thermomechanical analyses;
- nonlinear static analysis where explicitly supported;
- agentic design loop: propose → construct → simulate → verify → modify parameters;
- objective/constraint model for mass, stress, displacement, frequency and manufacturing constraints.

## Research track

- feedback-tuned FeaturePlanPlanner/CAD planner;
- multimodal verification from CAD renders;
- neural operators/PINN as optional surrogate or hybrid CAE backends;
- uncertainty/provenance propagation from natural-language assumptions into simulation results;
- benchmark suite for natural-language CAD/CAE task correctness.
