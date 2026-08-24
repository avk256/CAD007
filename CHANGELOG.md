# Changelog

## 3.0.0-alpha.1 — 2026-08-23

Initial v3 architecture and implementation:

- replaced LLM-generated FreeCAD source with typed `GeometryFeaturePlan`;
- added deterministic CadQuery/OCCT compiler and B-Rep inspection;
- added stable semantic-region rules;
- added STEP/STL/GLB export;
- added direct Gmsh tetrahedral mesh adapter and mesh metadata;
- added deterministic CalculiX input builder/executor/result status parser;
- retained structured geometry/structural planning, unified validation and LangGraph orchestration;
- added bounded feature-plan repair loop;
- added reproducible artifact workspaces, schemas, CLI, Streamlit UI and tests.

## UI update

- Added a v2-style Streamlit sidebar for AgentCAD v3.
- Sidebar settings now configure `EngineSettings` directly: LLM provider/model/temperature, CAD feature-plan retry limit, output directory, Gmsh executable, CalculiX executable, and solver timeout.
- Added API-key status and repository-root fallback import for direct `streamlit run app/streamlit_agentcad.py` execution.

## 3.0.0-alpha.2 — informative Streamlit / clarification loop

- restored a v2-style iterative clarification workflow in the Streamlit UI;
- added `AgentCADEngine.resume(thread_id, answers)` while preserving the same run directory and accumulated clarification history;
- added automatic retries for invalid LLM structured outputs before treating a planner-formatting error as a hard failure;
- added complete engine event protocol and structured diagnostics to public run results;
- persist round-by-round engineering specifications, validation reports, CAD-plan attempts, failure JSON and tracebacks;
- added Streamlit tabs for Pipeline, Engineering Model, CAD/Validation, 3D STL, FEM, Diagnostics and Files;
- all run files remain inspectable/downloadable after failures;
- strengthened the GeometryPlanner prompt so `overall_dimensions_mm` is emitted as a typed `{x, y, z}` object rather than a formatted string.
