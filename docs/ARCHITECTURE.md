# AgentCAD v3 architecture

## 1. Design goal

AgentCAD v3 separates probabilistic interpretation from deterministic engineering execution. An LLM may decide *what* engineering operations are intended, but it does not decide *how to call* CadQuery, Gmsh or CalculiX APIs at runtime.

## 2. Layering

```text
┌────────────────────────────────────────────┐
│ UI: Streamlit / CLI / future REST API      │
└───────────────────┬────────────────────────┘
                    ▼
┌────────────────────────────────────────────┐
│ AgentCADEngine + LangGraph                 │
└───────────────────┬────────────────────────┘
                    ▼
┌────────────────────────────────────────────┐
│ Planning layer [LLM]                       │
│ GeometryPlanner                            │
│ StructuralAnalysisPlanner                  │
│ FeaturePlanPlanner                         │
└───────────────────┬────────────────────────┘
                    ▼
┌────────────────────────────────────────────┐
│ Canonical models                           │
│ UnifiedEngineeringModel                    │
│ GeometryFeaturePlan                        │
│ SemanticRegionRule                         │
└───────────────────┬────────────────────────┘
                    ▼
┌────────────────────────────────────────────┐
│ Deterministic verification/execution       │
│ UnifiedConsistencyValidator                │
│ FeaturePlanValidator                       │
│ CadQueryGeometryCompiler                   │
│ SemanticRegionResolver                     │
│ GeometryInspector                          │
└───────────────────┬────────────────────────┘
                    ▼
           OCCT B-Rep + artifacts
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
 STEP / STL / GLB          GmshMeshAdapter
                                ▼
                       CalculiXModelBuilder
                                ▼
                        CalculiXExecutor
                                ▼
                        ResultInspector
```

## 3. LangGraph states

The primary graph is:

```text
START
  ↓
plan_geometry
  ↓
plan_analysis
  ↓
validate_engineering_model
  ├── invalid → prepare_clarification → END/HITL
  └── valid
        ↓
    plan_features
        ↓
    validate_feature_plan
        ├── invalid → failure/repair boundary
        └── valid
              ↓
         build_geometry
              ├── geometry only → END
              └── FEM → run_fem → END
```

The graph never executes LLM-produced source code.

## 4. Failure boundaries

Failures are routed by abstraction level:

- `feature_plan_failure`: invalid CAD IR, unsupported/failed geometric operation or selector;
- `mesh_failure`: STEP import, physical-region transfer, tetrahedralization or mesh-quality problems;
- `model_definition_failure`: insufficient/contradictory BCs, rigid-body modes and solver-model issues;
- `solver_failure`: CalculiX execution/convergence/result production;
- `infrastructure_failure`: missing packages/executables/environment.

This distinction is essential: a mesh error must not trigger arbitrary regeneration of CAD code, and a missing engineering parameter must not be repaired by inventing a solver card.

## 5. Backend independence

`UnifiedEngineeringModel` and `GeometryFeaturePlan` do not expose FreeCAD object IDs. CadQuery is the first v3 geometry backend, but a future backend can implement the same feature operations and semantic-region contract. Likewise, Gmsh and CalculiX are adapters below the engineering specification rather than objects leaked into prompts/UI.

## 6. Reproducibility

Each run stores the request, engineering model, feature plan, validation reports, CAD artifacts, mesh metadata, solver input/output and result summary in a unique directory. This provides a traceable boundary between LLM decisions and deterministic execution.
