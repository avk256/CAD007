# Migration from AgentCAD v2

## Keep

The following concepts from v2 remain valuable and are retained conceptually:

- `AgentCADEngine` as the only application-facing facade;
- LangGraph orchestration;
- Pydantic structured outputs;
- separate geometry and structural planners;
- deterministic unified consistency validation;
- semantic region names;
- clarification/HITL boundary;
- failure classification;
- provider-neutral LLM factory.

## Replace

```text
v2
UnifiedModelSpecification
  → CodeGenerator (LLM FreeCAD Python)
  → CodeValidator
  → FreeCADExecutor
  → STLInspector
```

becomes:

```text
v3
UnifiedEngineeringModel
  → FeaturePlanPlanner (typed CAD IR)
  → FeaturePlanValidator
  → CadQueryGeometryCompiler
  → B-Rep GeometryInspector
```

For FEM:

```text
v2: generated FreeCAD FEM Python → FreeCAD/solver integration
v3: STEP → GmshMeshAdapter → CalculiXModelBuilder → ccx
```

## Component mapping

| v2 component | v3 component | Migration decision |
|---|---|---|
| `AgentCADEngine` | `AgentCADEngine` | retain facade |
| `GeometryPlanner` | `GeometryPlanner` | retain, update prompt/schema |
| `StructuralAnalysisPlanner` | same | retain, constrain backend capability |
| `UnifiedConsistencyValidator` | same | retain and strengthen |
| `UnifiedModelSpecification` | `UnifiedEngineeringModel` | evolve schema to v3 |
| `CodeGenerator` | `FeaturePlanPlanner` | replace source generation with CAD IR |
| `CodeValidator` | `FeaturePlanValidator` | replace AST/API validation with semantic IR validation |
| `FreeCADExecutor` | `CadQueryGeometryCompiler` | remove FreeCAD from critical path |
| `STLInspector` | `GeometryInspector` | inspect OCCT B-Rep before tessellation |
| FEM script generation | `GmshMeshAdapter` + `CalculiXModelBuilder` | deterministic direct backend |
| `FailureClassifier` | `FailureClassifier` | retain, use abstraction-level categories |

## Suggested migration sequence

1. Freeze v2 as a regression/reference branch.
2. Port shared Pydantic material/BC/load/mesh models first.
3. Adopt `UnifiedEngineeringModel` and v3 validators.
4. Train/iterate the `FeaturePlanPlanner` against a curated set of CAD requests.
5. Grow deterministic CadQuery operations only when accompanied by tests.
6. Build a geometry benchmark comparing requested dimensions/features with B-Rep inspection.
7. Enable direct FEM only for validated `solid_3d` cases.
8. Add field-level CalculiX result parsing and benchmark against known solutions/FreeCAD v2 cases.
9. Add assemblies and advanced analyses as separate capabilities rather than enlarging one generated script.
