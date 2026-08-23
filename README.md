# AgentCAD v2

AgentCAD v2 is a modular LangGraph-based prototype that converts a natural-language description of a mechanical part into a validated CAD/FEM task specification, generates a headless FreeCAD Python implementation, executes it through `FreeCADCmd`, and inspects the produced geometry and FEM artifacts.

The central architectural rule is that **Streamlit talks only to `AgentCADEngine`**. Planners, validators, LLM integrations, FreeCAD execution and result inspection are independent classes/modules hidden behind the engine API.

## Architecture

```text
Streamlit / CLI
      |
      v
+--------------------------+
|     AgentCADEngine       |
|       LangGraph          |
+------------+-------------+
             |
             v
+----------------------------------------------------+
|       UNIFIED PLANNING & VALIDATION LOOP          |
|                                                    |
| GeometryPlanner (LLM)                              |
|       |                                            |
| StructuralAnalysisPlanner (LLM / optional FEM)     |
|       |                                            |
| UnifiedConsistencyValidator (deterministic)        |
|       |                                            |
|   VALID? ---- no ---> ClarificationManager         |
|       |                    |                       |
|       |                  interrupt() <--- USER     |
|       |                    |                       |
|       |              both planners rerun           |
+-------+--------------------------------------------+
        |
        v
UnifiedModelSpecification
        |
        v
CodeGenerator (LLM)
        |
        v
FreeCADExecutor (deterministic)
        |
        v
STLInspector (deterministic)
        |
        +--- structural task ---> FEMResultInspector
        |
        v
       END
```

If FEM inspection indicates a likely model-definition problem (for example rigid-body motion / a singular system), `FailureClassifier` can route the task back to the shared planning loop. Code/API failures are routed back to `CodeGenerator`.

## Module types

| Module | Nature | Responsibility |
|---|---|---|
| `GeometryPlanner` | LLM + structured output | Natural language -> `GeometrySpec`; detects ambiguities/conflicts and names semantic regions |
| `StructuralAnalysisPlanner` | LLM + structured output | Natural language + geometry -> linear-static FEM specification |
| `UnifiedConsistencyValidator` | deterministic | Units, ranges, completeness, cross-references, mesh/FEM compatibility |
| `ClarificationManager` | deterministic | Converts validation issues into human questions |
| `ParameterExplainer` | deterministic | Short explanations of engineering parameter influence |
| `UnifiedModelSpecification` | data model | Frozen machine-readable contract before code generation |
| `CodeGenerator` | LLM + structured output | Contract -> FreeCAD/FEM Python implementation; repair after implementation failures |
| `CodeValidator` | deterministic | Syntax/AST guardrails for generated code |
| `FreeCADExecutor` | deterministic | Executes `FreeCADCmd`, captures stdout/stderr and artifacts |
| `STLInspector` | deterministic | Mesh validity, bounding box, area and dimensional verification |
| `FEMResultInspector` | deterministic | Checks solver/result artifacts and known solver failure markers |
| `FailureClassifier` | deterministic heuristic | Routes implementation failures vs model-specification failures |
| `AgentCADEngine` | orchestrator | Public API and LangGraph lifecycle |

## Project structure

```text
AgentCAD_v2/
├── agentcad/
│   ├── config/
│   │   └── settings.py
│   ├── engine/
│   │   ├── agentcad_engine.py
│   │   ├── graph_builder.py
│   │   ├── result.py
│   │   └── state.py
│   ├── planners/
│   │   ├── geometry_planner.py
│   │   ├── structural_analysis_planner.py
│   │   ├── parameter_explainer.py
│   │   └── clarification_manager.py
│   ├── validators/
│   │   ├── unified_consistency_validator.py
│   │   ├── geometry_validator.py
│   │   ├── material_validator.py
│   │   ├── boundary_condition_validator.py
│   │   ├── load_validator.py
│   │   ├── mesh_validator.py
│   │   ├── fem_validator.py
│   │   ├── code_validator.py
│   │   └── units.py
│   ├── generators/
│   │   └── code_generator.py
│   ├── executors/
│   │   └── freecad_executor.py
│   ├── inspectors/
│   │   ├── stl_inspector.py
│   │   ├── fem_result_inspector.py
│   │   └── failure_classifier.py
│   ├── llm/
│   │   ├── model_factory.py
│   │   ├── prompt_loader.py
│   │   └── prompts/
│   └── models/
│       ├── common.py
│       ├── geometry.py
│       ├── material.py
│       ├── boundary_conditions.py
│       ├── loads.py
│       ├── mesh.py
│       ├── simulation.py
│       ├── planning.py
│       ├── validation.py
│       ├── unified_specification.py
│       └── artifacts.py
├── app/
│   └── streamlit_agentcad.py
├── tests/
├── cli.py
├── pyproject.toml
├── agentcad_environment_v2.yml
└── .env.example
```

## Unified planning loop

For every initial request or human clarification, both planners run again:

```text
user request / clarification
        |
        v
GeometryPlanner
        |
        v
StructuralAnalysisPlanner
        |
        v
UnifiedConsistencyValidator
        |
   +----+----+
   |         |
 VALID   clarification needed
   |         |
   |         v
   |    ParameterExplainer
   |         |
   |    ClarificationManager
   |         |
   |      interrupt()
   |         |
   |       USER
   |         |
   +---------+----> GeometryPlanner
```

No FreeCAD code is generated until the planning contract is `VALID` or `VALID_WITH_WARNINGS`.

### Geometry-only mode

Only `GeometrySpec` must validate. `StructuralAnalysisPlanner` returns a disabled structural specification.

### Structural-analysis mode

The shared loop also requires a valid linear-static formulation:

- homogeneous linear-isotropic material;
- density;
- Young modulus;
- Poisson ratio;
- boundary conditions;
- load(s) or prescribed displacement;
- model idealization (`beam_1d`, `shell_2d`, `solid_3d`);
- element dimension/family/order;
- global mesh size or explicit `AUTO` choice;
- shell thickness for shell models;
- beam section information for 1D models;
- CalculiX solver.

## Semantic geometry regions

FEM conditions should not reference unstable FreeCAD identifiers such as `Face7`. `GeometryPlanner` creates stable semantic names, e.g.:

```text
left_end_face
right_end_face
crankpin_surface
mounting_holes
load_surface
```

Boundary conditions, loads and local mesh refinements reference these names. The deterministic validator verifies that referenced names exist in `GeometrySpec`.

## Engineering parameters and provenance

Numeric parameters use `QuantityParameter` and record:

- value;
- unit;
- source (`user_explicit`, `inferred`, `default`, `undefined`);
- whether the parameter is required;
- optional explanation/notes.

The validator uses canonical engineering dimensions for unit checks. Current supported examples include:

- length: `mm`, `cm`, `m`;
- force: `N`, `kN`;
- stress/modulus/pressure: `Pa`, `kPa`, `MPa`, `GPa`, `N/mm²`;
- density: `kg/m³`, `g/cm³`;
- acceleration: `m/s²`, `mm/s²`;
- moment: `N·mm`, `N·m`, `kN·m`.

AgentCAD does not silently reinterpret suspicious units. When user confirmation is required, validation produces a clarification question.

## LangGraph / human-in-the-loop

The graph is compiled with a checkpointer. The prototype uses `InMemorySaver`; the public API uses a stable `thread_id` so a run can pause on a clarification and resume with the same state.

The `ask_user` graph node calls LangGraph `interrupt()`. `AgentCADEngine.resume(thread_id, answer)` resumes it using `Command(resume=...)`.

For a production server, replace `InMemorySaver` with a durable checkpointer (SQLite for local workflows, PostgreSQL for production).

## Public engine API

Streamlit and CLI use only the engine:

```python
from agentcad.engine import AgentCADEngine

engine = AgentCADEngine()

result = engine.start(
    "Create an 80x40x3 mm plate ...",
    perform_structural_analysis=True,
)

if result.status.value == "needs_input":
    result = engine.resume(result.thread_id, {
        "question-id": "210 GPa"
    })

state = engine.get_state(result.thread_id)
artifacts = engine.get_artifacts(result.thread_id)
```

Important public methods:

- `start(...)`
- `resume(thread_id, answer)`
- `get_state(thread_id)`
- `get_result(thread_id)`
- `get_artifacts(thread_id)`
- `stream_updates(...)` (low-level optional UI integration)

## Install

### 1. FreeCAD

Install FreeCAD system-wide and verify the headless command:

```bash
which FreeCADCmd
# or
which freecadcmd
```

### 2. Conda environment

```bash
conda env create -f agentcad_environment_v2.yml
conda activate agentcad-v2
```

Optionally install the project in editable mode:

```bash
pip install -e .
```

### 3. Environment file

```bash
cp .env.example .env
```

Edit `.env` and set the LLM API key and FreeCAD path.

Example OpenRouter configuration:

```dotenv
LLM_PROVIDER=openrouter
LLM_MODEL=openai/gpt-5.5
OPENROUTER_API_KEY=sk-or-v1-...
FREECAD_CMD=/usr/bin/freecadcmd
```

## Run Streamlit

From the project root:

```bash
conda activate agentcad-v2
streamlit run app/streamlit_agentcad.py
```

The UI can:

1. start a geometry-only or geometry+FEM task;
2. display planning-validation questions;
3. resume the same LangGraph thread after user clarification;
4. display validation state and `UnifiedModelSpecification`;
5. display generated code and FreeCAD logs;
6. visualize generated STL;
7. expose generated artifacts for download.

## CLI

```bash
python cli.py "Create an 80x40x3 mm plate with four holes"
```

With structural analysis:

```bash
python cli.py "Create ... Material E=210 GPa ..." --structural
```

The CLI asks human-in-the-loop questions in the terminal until the specification becomes valid or the planning iteration limit is reached.

## Testing

Deterministic modules have unit tests independent of LLM and FreeCAD:

```bash
pytest -q
```

The current test set covers:

- material parameter validation;
- Poisson-ratio range;
- mesh family/dimension compatibility;
- valid geometry-only specification;
- valid 3D structural specification;
- generated-code AST guardrails.

## Execution/inspection loop

After the specification is frozen:

```text
UnifiedModelSpecification
        |
        v
CodeGenerator
        |
        v
CodeValidator
        |
        v
FreeCADExecutor
        |
   +----+----+
   |         |
 error    success
   |         |
   +-> repair|
             v
        STLInspector
             |
       +-----+-----+
       |           |
 geometry-only   structural
       |           |
      END     FEMResultInspector
                   |
                 END / repair / re-plan
```

`CodeGenerator` is allowed to repair implementation failures but is not allowed to silently change a validated engineering specification.

## FEM result contract

For structural runs, the generated script is instructed to produce `agentcad_fem_summary.json` in addition to solver files. A minimal form is:

```json
{
  "success": true,
  "solver": "CalculiX",
  "analysis_type": "linear_static",
  "notes": []
}
```

`FEMResultInspector` also looks for non-empty `.frd` results and common failure markers such as `singular`, `zero pivot`, `rigid body`, `no convergence`.

This inspector is intentionally conservative and should be extended later with direct extraction of min/max displacement, strain and stress fields from FreeCAD/CalculiX results.

## Current limitations

AgentCAD v2 is an experimental prototype. In particular:

- LLM-produced FreeCAD FEM code may require adaptation to the exact installed FreeCAD version/API;
- AST checks are guardrails, not a true execution sandbox;
- `InMemorySaver` loses state when the engine process is restarted;
- STL bounding-box verification cannot validate every semantic feature (for example exact hole count) yet;
- FEM result inspection is artifact/log based and does not yet numerically inspect stress/strain fields;
- the initial structural scope is deliberately limited to homogeneous linear-isotropic linear-static analysis.

Before exposing AgentCAD as a public service, execute `FreeCADCmd` in a container with filesystem, CPU/RAM and network restrictions.

## Recommended next development steps

1. persistent SQLite checkpointer for local Streamlit deployments;
2. richer geometry semantic verification (holes, symmetry, region identity);
3. a deterministic FreeCAD topology mapping layer for semantic regions;
4. FEM mesh quality inspector;
5. direct CalculiX/FreeCAD result parser for displacement, strain and stress extrema;
6. convergence study / adaptive local refinement;
7. thermal and thermomechanical analysis specifications;
8. containerized FreeCAD execution;
9. integration tests against the target FreeCAD release.
