from __future__ import annotations

import json
import os
import struct
import sys
from pathlib import Path

# Allow running the Streamlit app directly from the repository without
# requiring an editable install first. An editable install is still recommended.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import streamlit as st
from dotenv import load_dotenv

from agentcad.config.settings import EngineSettings
from agentcad.engine.agentcad_engine import AgentCADEngine


load_dotenv(PROJECT_ROOT / ".env")

st.set_page_config(
    page_title="AgentCAD v3",
    page_icon="🧊",
    layout="wide",
)

st.markdown(
    "<style>.main .block-container{padding-bottom:7rem}</style>",
    unsafe_allow_html=True,
)


@st.cache_resource
def create_engine(
    provider: str,
    model: str,
    temperature: float,
    max_planning_iterations: int,
    max_feature_plan_attempts: int,
    output_root: str,
    gmsh_executable: str,
    calculix_executable: str,
    solver_timeout_seconds: int,
) -> AgentCADEngine:
    """Create and cache an engine instance for the selected runtime settings."""
    settings = EngineSettings(
        llm_provider=provider,
        llm_model=model.strip(),
        llm_temperature=float(temperature),
        output_root=Path(output_root).expanduser(),
        max_planning_iterations=int(max_planning_iterations),
        max_feature_plan_attempts=int(max_feature_plan_attempts),
        gmsh_executable=gmsh_executable.strip() or "gmsh",
        calculix_executable=calculix_executable.strip() or "ccx",
        solver_timeout_seconds=int(solver_timeout_seconds),
    )
    return AgentCADEngine(settings=settings)


# ---------------------------------------------------------------------------
# STL loading and visualization
# ---------------------------------------------------------------------------


def _load_ascii_stl(path: Path) -> np.ndarray:
    vertices: list[list[float]] = []
    triangles: list[list[list[float]]] = []

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            stripped = line.strip()
            if not stripped.lower().startswith("vertex "):
                continue
            parts = stripped.split()
            if len(parts) < 4:
                continue
            try:
                vertex = [float(parts[1]), float(parts[2]), float(parts[3])]
            except ValueError:
                continue
            vertices.append(vertex)
            if len(vertices) == 3:
                triangles.append(vertices)
                vertices = []

    if not triangles:
        raise ValueError("No triangles were found in the ASCII STL file.")
    return np.asarray(triangles, dtype=np.float64)


def _load_binary_stl(path: Path) -> np.ndarray:
    with path.open("rb") as f:
        header = f.read(80)
        if len(header) != 80:
            raise ValueError("Invalid binary STL header.")
        count_bytes = f.read(4)
        if len(count_bytes) != 4:
            raise ValueError("Invalid binary STL triangle count.")

        triangle_count = struct.unpack("<I", count_bytes)[0]
        triangles = np.empty((triangle_count, 3, 3), dtype=np.float64)
        for idx in range(triangle_count):
            record = f.read(50)
            if len(record) != 50:
                raise ValueError(f"Unexpected end of binary STL at triangle {idx + 1}.")
            values = struct.unpack("<12fH", record)
            triangles[idx, 0] = values[3:6]
            triangles[idx, 1] = values[6:9]
            triangles[idx, 2] = values[9:12]
    return triangles


@st.cache_data(show_spinner=False)
def load_stl_triangles(path_str: str, modified_ns: int, file_size: int) -> np.ndarray:
    del modified_ns
    path = Path(path_str)
    with path.open("rb") as f:
        header = f.read(84)

    # Binary STL may also begin with "solid", therefore file size is a safer
    # discriminator than the header text alone.
    if len(header) >= 84:
        triangle_count = struct.unpack("<I", header[80:84])[0]
        if 84 + triangle_count * 50 == file_size:
            return _load_binary_stl(path)
    return _load_ascii_stl(path)


def render_stl_preview(path: Path, key: str, height: int) -> None:
    try:
        import plotly.graph_objects as go
    except ImportError:
        st.warning("Interactive STL preview requires Plotly (`pip install plotly`).")
        return

    try:
        stat = path.stat()
        triangles = load_stl_triangles(str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    except Exception as exc:
        st.error(f"Could not load STL file: {exc}")
        return

    flat_vertices = triangles.reshape(-1, 3)
    tri_count = len(triangles)
    indices = np.arange(tri_count * 3, dtype=np.int64).reshape(-1, 3)
    mins = flat_vertices.min(axis=0)
    maxs = flat_vertices.max(axis=0)
    size = maxs - mins

    fig = go.Figure(
        data=[
            go.Mesh3d(
                x=flat_vertices[:, 0],
                y=flat_vertices[:, 1],
                z=flat_vertices[:, 2],
                i=indices[:, 0],
                j=indices[:, 1],
                k=indices[:, 2],
                opacity=1.0,
                flatshading=True,
                lighting=dict(
                    ambient=0.35,
                    diffuse=0.8,
                    specular=0.25,
                    roughness=0.55,
                    fresnel=0.1,
                ),
                lightposition=dict(x=100, y=200, z=300),
                hoverinfo="skip",
            )
        ]
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=height,
        scene=dict(
            aspectmode="data",
            xaxis_title="X, mm",
            yaxis_title="Y, mm",
            zaxis_title="Z, mm",
        ),
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
        key=f"stl_plot_{key}",
        config={"displaylogo": False},
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Triangles", f"{tri_count:,}")
    c2.metric("X size", f"{size[0]:.3f} mm")
    c3.metric("Y size", f"{size[1]:.3f} mm")
    c4.metric("Z size", f"{size[2]:.3f} mm")


# ---------------------------------------------------------------------------
# Run artifacts / diagnostic helpers
# ---------------------------------------------------------------------------


def scan_run_files(output_dir: str | None) -> list[Path]:
    if not output_dir:
        return []
    root = Path(output_dir).expanduser()
    if not root.is_dir():
        return []
    return sorted(
        [p for p in root.rglob("*") if p.is_file()],
        key=lambda p: str(p.relative_to(root)).lower(),
    )


def find_stl_artifacts(result: dict) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    seen: set[Path] = set()

    files = (result.get("artifacts") or {}).get("files", {}) or {}
    for name, value in files.items():
        if not value:
            continue
        path = Path(value).expanduser()
        if path.suffix.lower() != ".stl":
            continue
        resolved = path.resolve() if path.exists() else path
        if resolved not in seen:
            seen.add(resolved)
            found.append((str(name), path))

    for path in scan_run_files(result.get("output_dir")):
        if path.suffix.lower() != ".stl":
            continue
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            found.append((path.name, path))
    return found


def diagnostic_files(output_dir: str | None) -> list[Path]:
    suffixes = {".json", ".txt", ".log", ".out", ".err", ".dat"}
    return [p for p in scan_run_files(output_dir) if p.suffix.lower() in suffixes]


def show_text_file(path: Path, max_chars: int = 250_000) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        st.error(f"Could not read {path.name}: {exc}")
        return

    truncated = len(text) > max_chars
    shown = text[:max_chars]
    if path.suffix.lower() == ".json":
        try:
            st.json(json.loads(shown), expanded=True)
        except Exception:
            st.code(shown, language="json")
    else:
        st.code(shown, language="text")
    if truncated:
        st.warning(f"Preview truncated to {max_chars:,} characters. Download the file to inspect it completely.")


def store_result(result_obj) -> None:
    raw = result_obj.model_dump(mode="json")
    st.session_state["agentcad_result"] = raw
    st.session_state["agentcad_thread_id"] = raw.get("thread_id")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("🧊 AgentCAD v3")
st.caption(
    "Natural-language engineering intent → planning/validation loop → typed CAD IR → "
    "CadQuery/OCCT → optional Gmsh/CalculiX"
)


# ---------------------------------------------------------------------------
# Sidebar settings
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Settings")

    st.subheader("LLM")
    provider = st.selectbox(
        "LLM provider",
        options=["openrouter", "openai"],
        index=0 if os.getenv("LLM_PROVIDER", "openrouter").lower() == "openrouter" else 1,
    )

    env_model = os.getenv("LLM_MODEL", "").strip()
    default_model = env_model or ("openai/gpt-5.5" if provider == "openrouter" else "gpt-5.5")
    model = st.text_input(
        "Model",
        value=default_model,
        help=(
            "For OpenRouter, use a complete model slug such as `openai/gpt-5.5`. "
            "For OpenAI, use the OpenAI model name."
        ),
    )

    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.0,
        value=float(os.getenv("LLM_TEMPERATURE", "0")),
        step=0.05,
        help="A value between 0.0 and 0.2 is recommended for engineering planning.",
    )

    max_planning_iterations = st.slider(
        "Maximum clarification rounds",
        min_value=1,
        max_value=10,
        value=int(os.getenv("AGENTCAD_MAX_PLANNING_ITERATIONS", "4")),
        help=(
            "Maximum number of user clarification rounds before the engineering "
            "specification is considered unresolved."
        ),
    )

    max_feature_plan_attempts = st.slider(
        "Maximum CAD plan attempts",
        min_value=1,
        max_value=8,
        value=int(os.getenv("AGENTCAD_MAX_FEATURE_PLAN_ATTEMPTS", "3")),
        help=(
            "Maximum number of GeometryFeaturePlan regeneration attempts when "
            "typed validation or CadQuery execution fails."
        ),
    )

    viewer_height = st.slider(
        "3D viewer height, px",
        min_value=320,
        max_value=900,
        value=560,
        step=20,
    )

    st.divider()
    st.subheader("CAE backend")

    gmsh_executable = st.text_input(
        "Gmsh executable",
        value=os.getenv("GMSH_EXECUTABLE", "gmsh"),
        placeholder="gmsh",
        help="Command or full path to Gmsh. Used only for FEM analysis.",
    )

    calculix_executable = st.text_input(
        "CalculiX executable",
        value=os.getenv("CALCULIX_EXECUTABLE", "ccx"),
        placeholder="ccx",
        help="Command or full path to CalculiX ccx. Used only for FEM analysis.",
    )

    solver_timeout_seconds = st.number_input(
        "CalculiX timeout, s",
        min_value=30,
        max_value=7200,
        value=int(os.getenv("AGENTCAD_SOLVER_TIMEOUT", "600")),
        step=30,
    )
    st.caption("CadQuery/OCCT runs directly as a Python library.")

    st.divider()
    st.subheader("Artifacts")
    output_root = st.text_input(
        "Run output directory",
        value=os.getenv("AGENTCAD_OUTPUT_ROOT", "./agentcad_outputs"),
        help="AgentCAD creates a separate workspace for each new task.",
    )

    st.divider()
    st.subheader("Environment status")
    api_var = "OPENROUTER_API_KEY" if provider == "openrouter" else "OPENAI_API_KEY"
    if os.getenv(api_var):
        st.success(f"{api_var} found")
    else:
        st.warning(f"{api_var} was not found in the environment or .env file")
    st.caption(f"Project root: `{PROJECT_ROOT}`")


# ---------------------------------------------------------------------------
# Engine configured from the sidebar
# ---------------------------------------------------------------------------

try:
    engine = create_engine(
        provider=provider,
        model=model,
        temperature=float(temperature),
        max_planning_iterations=int(max_planning_iterations),
        max_feature_plan_attempts=int(max_feature_plan_attempts),
        output_root=output_root,
        gmsh_executable=gmsh_executable,
        calculix_executable=calculix_executable,
        solver_timeout_seconds=int(solver_timeout_seconds),
    )
except Exception as exc:
    st.error(f"Could not create AgentCADEngine: {exc}")
    st.stop()


# ---------------------------------------------------------------------------
# New request
# ---------------------------------------------------------------------------

with st.form("agentcad_task"):
    request = st.text_area(
        "Describe the structure and, if required, the analysis setup",
        height=180,
        placeholder=(
            "Create a steel plate 80 × 40 × 3 mm with four through holes Ø4 mm. "
            "If FEM is required, specify material, supports, loads and mesh settings..."
        ),
    )

    run_fem = st.checkbox(
        "Run structural analysis (Gmsh + CalculiX)",
        value=False,
    )

    submitted = st.form_submit_button(
        "Run AgentCAD",
        type="primary",
        use_container_width=True,
    )


if submitted:
    request = request.strip()
    if not request:
        st.error("Enter a task description.")
    elif not model.strip():
        st.error("Specify an LLM model.")
    else:
        # Starting a new task deliberately replaces the previous session result.
        st.session_state.pop("agentcad_result", None)
        st.session_state.pop("agentcad_thread_id", None)
        with st.status(
            "AgentCAD v3 is running the planning and validation pipeline...",
            expanded=True,
        ) as status_box:
            try:
                result_obj = engine.start(
                    request,
                    perform_structural_analysis=run_fem,
                )
                store_result(result_obj)
                status_box.write(result_obj.message)
            except Exception as exc:
                status_box.update(label="AgentCAD failed", state="error", expanded=True)
                st.exception(exc)
            else:
                if result_obj.status == "needs_input":
                    status_box.update(
                        label="Additional engineering information is required",
                        state="complete",
                        expanded=True,
                    )
                elif result_obj.failure:
                    status_box.update(
                        label="AgentCAD completed with an error",
                        state="error",
                        expanded=True,
                    )
                else:
                    status_box.update(
                        label="AgentCAD completed successfully",
                        state="complete",
                        expanded=False,
                    )


# ---------------------------------------------------------------------------
# Clarification loop
# ---------------------------------------------------------------------------

result = st.session_state.get("agentcad_result")
if result and result.get("status") == "needs_input" and result.get("clarification_questions"):
    st.divider()
    round_no = int(result.get("clarification_round", 0))
    st.subheader("⚠ Engineering clarification required")
    st.info(
        f"Clarification round {round_no + 1} of {max_planning_iterations}. "
        "The same task and run directory will be reused after your answers."
    )

    with st.form(f"clarification_form_{result.get('thread_id')}_{round_no}"):
        answers: dict[str, str] = {}
        for index, question in enumerate(result["clarification_questions"], 1):
            qid = str(question.get("id", index))
            st.markdown(f"**{index}. {question.get('question', 'Please provide the missing parameter.')}**")
            if question.get("path"):
                st.caption(f"Parameter: `{question['path']}`")
            if question.get("explanation"):
                st.info(question["explanation"])
            answers[qid] = st.text_input(
                "Answer",
                key=f"clarification_answer_{result.get('thread_id')}_{round_no}_{qid}",
            )

        continue_clicked = st.form_submit_button(
            "Continue AgentCAD",
            type="primary",
            use_container_width=True,
        )

    if continue_clicked:
        cleaned = {key: value.strip() for key, value in answers.items() if value.strip()}
        if not cleaned:
            st.warning("Provide at least one clarification answer before continuing.")
        else:
            with st.status(
                "Re-running GeometryPlanner / StructuralAnalysisPlanner with the clarification history...",
                expanded=True,
            ) as status_box:
                try:
                    resumed = engine.resume(str(result["thread_id"]), cleaned)
                    store_result(resumed)
                    status_box.write(resumed.message)
                    status_box.update(
                        label=(
                            "Additional engineering information is required"
                            if resumed.status == "needs_input"
                            else resumed.message
                        ),
                        state="error" if resumed.failure else "complete",
                        expanded=resumed.status == "needs_input" or bool(resumed.failure),
                    )
                    st.rerun()
                except Exception as exc:
                    status_box.update(label="Could not continue the AgentCAD run", state="error", expanded=True)
                    st.exception(exc)


# ---------------------------------------------------------------------------
# Results: keep the v2 level of transparency even when the run fails
# ---------------------------------------------------------------------------

result = st.session_state.get("agentcad_result")
if result:
    state = result.get("state") or {}
    st.divider()

    if result.get("status") == "needs_input":
        st.warning(result.get("message") or "AgentCAD is waiting for clarification.")
    elif result.get("failure"):
        st.error(result.get("message") or "AgentCAD completed with an error.")
    else:
        st.success(result.get("message") or "AgentCAD completed successfully.")

    if result.get("output_dir"):
        st.caption(f"Run directory: `{result['output_dir']}`")
    if result.get("thread_id"):
        st.caption(f"Run thread: `{result['thread_id']}`")

    tabs = st.tabs(
        [
            "Pipeline",
            "Engineering Model",
            "CAD / Validation",
            "3D STL",
            "FEM",
            "Diagnostics",
            "Files",
        ]
    )

    # ------------------------------------------------------------------
    # Pipeline protocol
    # ------------------------------------------------------------------
    with tabs[0]:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Status", str(result.get("status", "unknown")))
        c2.metric("Clarification round", int(result.get("clarification_round", 0)))
        c3.metric("CAD plan attempts", int(state.get("feature_plan_attempts", 0)))
        c4.metric("Diagnostics", len(result.get("diagnostics") or []))

        st.markdown("#### Engine protocol")
        events = result.get("events") or state.get("events") or []
        if events:
            for index, event in enumerate(events, 1):
                st.write(f"**{index}.** {event}")
        else:
            st.info("No engine events were recorded.")

        if result.get("clarifications"):
            st.markdown("#### Clarification history")
            st.dataframe(result["clarifications"], hide_index=True, use_container_width=True)

        if result.get("validation_report"):
            st.markdown("#### Engineering validation report")
            st.json(result["validation_report"], expanded=True)

        if result.get("failure"):
            st.markdown("#### Current failure")
            st.json(result["failure"], expanded=True)

    # ------------------------------------------------------------------
    # Typed engineering specification
    # ------------------------------------------------------------------
    with tabs[1]:
        if state.get("geometry_spec"):
            st.markdown("#### GeometrySpec")
            st.json(state["geometry_spec"], expanded=True)
        else:
            st.info("GeometrySpec has not been produced yet.")

        if state.get("structural_analysis"):
            st.markdown("#### StructuralAnalysisSpec")
            st.json(state["structural_analysis"], expanded=False)

        if result.get("unified_model"):
            st.markdown("#### UnifiedEngineeringModel")
            st.json(result["unified_model"], expanded=False)
        else:
            st.info("UnifiedEngineeringModel has not been frozen yet.")

    # ------------------------------------------------------------------
    # CAD-IR + deterministic validation
    # ------------------------------------------------------------------
    with tabs[2]:
        if result.get("feature_plan"):
            st.markdown("#### GeometryFeaturePlan")
            st.json(result["feature_plan"], expanded=True)
        else:
            st.info("GeometryFeaturePlan has not been produced yet.")

        if result.get("feature_plan_validation"):
            st.markdown("#### Feature plan validation")
            st.json(result["feature_plan_validation"], expanded=True)

        if result.get("geometry_inspection"):
            st.markdown("#### CadQuery / OCCT geometry inspection")
            st.json(result["geometry_inspection"], expanded=True)

    # ------------------------------------------------------------------
    # STL preview
    # ------------------------------------------------------------------
    with tabs[3]:
        stl_artifacts = find_stl_artifacts(result)
        valid_stls = [(name, path) for name, path in stl_artifacts if path.is_file()]
        if not valid_stls:
            st.info("No STL artifact is available yet.")
        else:
            labels = [f"{name} — {path.name}" for name, path in valid_stls]
            selected_label = st.selectbox("STL file", options=labels)
            selected_name, selected_path = valid_stls[labels.index(selected_label)]
            st.caption(f"`{selected_path}`")
            render_stl_preview(
                selected_path,
                key=f"{selected_name}_{selected_path.name}_{selected_path.stat().st_mtime_ns}",
                height=int(viewer_height),
            )
            st.download_button(
                "Download STL",
                data=selected_path.read_bytes(),
                file_name=selected_path.name,
                mime="model/stl",
                key=f"download_stl_{selected_path}_{selected_path.stat().st_mtime_ns}",
            )

    # ------------------------------------------------------------------
    # FEM
    # ------------------------------------------------------------------
    with tabs[4]:
        if not result.get("perform_structural_analysis"):
            st.info("Structural analysis was not requested for this run.")
        else:
            if result.get("simulation_summary"):
                st.markdown("#### FEM result summary")
                st.json(result["simulation_summary"], expanded=True)
            else:
                st.info("No FEM result summary is available yet.")

            if state.get("mesh_result"):
                st.markdown("#### Gmsh result")
                st.json(state["mesh_result"], expanded=False)
            if state.get("solver_result"):
                st.markdown("#### CalculiX execution result")
                st.json(state["solver_result"], expanded=False)

    # ------------------------------------------------------------------
    # Diagnostics: visible even after early planner / schema failures
    # ------------------------------------------------------------------
    with tabs[5]:
        if result.get("failure"):
            st.markdown("#### Failure classification")
            st.json(result["failure"], expanded=True)

        diagnostics = result.get("diagnostics") or []
        if diagnostics:
            st.markdown("#### In-memory diagnostics")
            for index, item in enumerate(diagnostics, 1):
                with st.expander(
                    f"Diagnostic {index}: {item.get('stage') or item.get('category') or 'event'}",
                    expanded=index == len(diagnostics),
                ):
                    st.json(item, expanded=True)

        st.markdown("#### Persisted protocol / JSON files")
        diag_files = diagnostic_files(result.get("output_dir"))
        if diag_files:
            root = Path(result["output_dir"])
            labels = [str(path.relative_to(root)) for path in diag_files]
            selected = st.selectbox("Diagnostic file", labels, key="diagnostic_file_selector")
            selected_path = diag_files[labels.index(selected)]
            st.caption(
                f"{selected_path.stat().st_size:,} bytes · modified "
                f"{selected_path.stat().st_mtime_ns}"
            )
            show_text_file(selected_path)
            st.download_button(
                f"Download {selected_path.name}",
                data=selected_path.read_bytes(),
                file_name=selected_path.name,
                key=f"download_diag_{selected_path}_{selected_path.stat().st_mtime_ns}",
            )
        else:
            st.info("No persisted diagnostic text/JSON files are available.")

        with st.expander("Raw AgentCAD state", expanded=False):
            st.json(state, expanded=True)

    # ------------------------------------------------------------------
    # All run files, not only successful artifacts
    # ------------------------------------------------------------------
    with tabs[6]:
        all_files = scan_run_files(result.get("output_dir"))
        if not all_files:
            st.info("No files are available in the run directory.")
        else:
            root = Path(result["output_dir"])
            rows = []
            for path in all_files:
                rel = path.relative_to(root)
                rows.append(
                    {
                        "Category": rel.parts[0] if len(rel.parts) > 1 else "root",
                        "File": path.name,
                        "Extension": path.suffix.lower() or "—",
                        "Size, bytes": path.stat().st_size,
                        "Relative path": str(rel),
                    }
                )
            st.dataframe(rows, hide_index=True, use_container_width=True)

            selected_rel = st.selectbox(
                "Download file",
                options=[row["Relative path"] for row in rows],
                key="all_file_selector",
            )
            selected_path = root / selected_rel
            st.download_button(
                f"Download {selected_path.name}",
                data=selected_path.read_bytes(),
                file_name=selected_path.name,
                key=f"download_all_{selected_path}_{selected_path.stat().st_mtime_ns}",
                use_container_width=True,
            )
