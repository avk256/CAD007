from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from stl import mesh as stl_mesh

from agentcad.config.settings import EngineSettings
from agentcad.engine import AgentCADEngine, EngineRunResult, EngineRunStatus


load_dotenv()
st.set_page_config(page_title="AgentCAD v2", page_icon="🧊", layout="wide")
st.markdown("<style>.main .block-container{padding-bottom:7rem}</style>", unsafe_allow_html=True)


@st.cache_resource
def create_engine(
    provider: str,
    model: str,
    freecad_cmd: str,
    timeout: int,
    max_planning: int,
    max_code_attempts: int,
    output_root: str,
):
    settings = EngineSettings(
        llm_provider=provider,
        llm_model=model,
        freecad_cmd=freecad_cmd.strip() or None,
        freecad_timeout_seconds=timeout,
        max_planning_iterations=max_planning,
        max_code_attempts=max_code_attempts,
        output_root=Path(output_root),
    )
    return AgentCADEngine(settings)


@st.cache_data(show_spinner=False)
def load_stl(path: str, mtime_ns: int):
    del mtime_ns
    model = stl_mesh.Mesh.from_file(path)
    vectors = np.asarray(model.vectors, dtype=float)
    vertices = vectors.reshape(-1, 3)
    base = np.arange(vectors.shape[0]) * 3
    return vertices, base, base + 1, base + 2


def stl_figure(path: Path, height: int):
    vertices, i, j, k = load_stl(str(path), path.stat().st_mtime_ns)
    fig = go.Figure(data=[go.Mesh3d(
        x=vertices[:, 0], y=vertices[:, 1], z=vertices[:, 2],
        i=i, j=j, k=k, flatshading=True, hoverinfo="skip",
    )])
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=35, b=0),
        title=path.name,
        scene=dict(xaxis_title="X, mm", yaxis_title="Y, mm", zaxis_title="Z, mm", aspectmode="data"),
    )
    return fig


def store_result(result: EngineRunResult):
    st.session_state.run_result = result.model_dump(mode="json")
    st.session_state.thread_id = result.thread_id


def current_result() -> EngineRunResult | None:
    raw = st.session_state.get("run_result")
    return EngineRunResult.model_validate(raw) if raw else None


st.title("🧊 AgentCAD v2")
st.caption("LangGraph planning/validation loop → UnifiedModelSpecification → FreeCAD/FEM → inspection")

with st.sidebar:
    st.header("Рушій")
    provider = st.selectbox("LLM provider", ["openrouter", "openai"])
    default_model = os.getenv("LLM_MODEL") or ("openai/gpt-5.5" if provider == "openrouter" else "gpt-5.5")
    model = st.text_input("Модель", default_model)
    freecad_cmd = st.text_input("FreeCADCmd", os.getenv("FREECAD_CMD", ""), placeholder="/usr/bin/freecadcmd")
    timeout = st.number_input("Timeout FreeCAD, с", 30, 3600, 300, 30)
    max_planning = st.slider("Макс. циклів планування", 1, 10, 5)
    max_code_attempts = st.slider("Макс. спроб коду", 1, 6, 3)
    viewer_height = st.slider("Висота 3D, px", 320, 800, 480, 20)
    output_root = st.text_input("Каталог запусків", "./agentcad_runs")

    api_var = "OPENROUTER_API_KEY" if provider == "openrouter" else "OPENAI_API_KEY"
    if os.getenv(api_var):
        st.success(f"{api_var} знайдено")
    else:
        st.warning(f"{api_var} не знайдено")

try:
    engine = create_engine(provider, model, freecad_cmd, int(timeout), max_planning, max_code_attempts, output_root)
except Exception as exc:
    st.error(f"Не вдалося створити AgentCADEngine: {exc}")
    st.stop()

with st.form("new_task"):
    description = st.text_area(
        "Опис конструкції та, за потреби, розрахункової постановки",
        height=180,
        placeholder=(
            "Створи пластину 80×40×3 мм з чотирма отворами Ø4 мм...\n"
            "Матеріал: E=210 GPa, ν=0.3, ρ=7850 kg/m³..."
        ),
    )
    structural = st.checkbox("Виконувати розрахунок напружено-деформованого стану", value=False)
    start_clicked = st.form_submit_button("Запустити AgentCAD", type="primary", use_container_width=True)

if start_clicked:
    if not description.strip():
        st.error("Введіть опис задачі.")
    else:
        with st.status("AgentCAD виконує planning/validation loop…", expanded=True) as status:
            try:
                result = engine.start(description, perform_structural_analysis=structural)
                store_result(result)
                status.write(result.message)
                status.update(
                    label="Потрібне уточнення" if result.status == EngineRunStatus.NEEDS_INPUT else result.message,
                    state="complete" if result.status != EngineRunStatus.FAILED else "error",
                    expanded=result.status == EngineRunStatus.NEEDS_INPUT,
                )
            except Exception as exc:
                status.update(label="Помилка рушія", state="error", expanded=True)
                st.exception(exc)

result = current_result()

if result and result.status == EngineRunStatus.NEEDS_INPUT:
    st.divider()
    st.subheader("⚠ Потрібне уточнення постановки")
    with st.form("clarification_form"):
        answers = {}
        for index, q in enumerate(result.questions, 1):
            st.markdown(f"**{index}. {q.get('question', '')}**")
            if q.get("explanation"):
                st.info(q["explanation"])
            answers[q.get("id", str(index))] = st.text_input(
                "Відповідь",
                key=f"answer_{q.get('id', index)}",
            )
        resume_clicked = st.form_submit_button("Продовжити", type="primary", use_container_width=True)
    if resume_clicked:
        cleaned = {k: v.strip() for k, v in answers.items() if v.strip()}
        if not cleaned:
            st.warning("Дайте відповідь принаймні на одне питання.")
        else:
            with st.status("Повторна перевірка GeometryPlanner + StructuralAnalysisPlanner…") as status:
                try:
                    resumed = engine.resume(result.thread_id, cleaned)
                    store_result(resumed)
                    status.update(
                        label=resumed.message,
                        state="complete" if resumed.status != EngineRunStatus.FAILED else "error",
                        expanded=resumed.status == EngineRunStatus.NEEDS_INPUT,
                    )
                    st.rerun()
                except Exception as exc:
                    status.update(label="Помилка при продовженні", state="error", expanded=True)
                    st.exception(exc)

result = current_result()
if result:
    state = result.state
    st.divider()
    if result.status == EngineRunStatus.COMPLETED:
        st.success(result.message)
    elif result.status == EngineRunStatus.FAILED:
        st.error(result.message)

    tabs = st.tabs(["Стан", "Специфікація", "3D STL", "Код", "Журнали", "Файли"])

    with tabs[0]:
        st.markdown("#### Події рушія")
        for event in state.get("events", []):
            st.write("•", event)
        st.markdown("#### Validation report")
        st.json(state.get("validation_report", {}), expanded=False)
        if state.get("stl_inspection"):
            st.markdown("#### STL inspection")
            st.json(state["stl_inspection"], expanded=False)
        if state.get("fem_inspection"):
            st.markdown("#### FEM inspection")
            st.json(state["fem_inspection"], expanded=False)

    with tabs[1]:
        if state.get("unified_specification"):
            st.json(state["unified_specification"], expanded=True)
        else:
            st.info("UnifiedModelSpecification ще не сформована — planning loop очікує уточнення.")

    artifacts = state.get("execution_result", {}).get("artifacts", {}) if isinstance(state.get("execution_result"), dict) else {}
    stl_files = [Path(x) for x in artifacts.get("stl", []) if Path(x).is_file()]

    with tabs[2]:
        if stl_files:
            selected = st.selectbox("STL", [str(p) for p in stl_files])
            selected_path = Path(selected)
            st.plotly_chart(
                stl_figure(selected_path, viewer_height),
                width="stretch",
                config={"displaylogo": False, "scrollZoom": False},
            )
        else:
            st.info("STL ще не створено.")

    with tabs[3]:
        code = state.get("generated_code", "")
        if code:
            st.code(code, language="python")
        else:
            st.info("Код ще не генерувався.")

    with tabs[4]:
        execution = state.get("execution_result", {})
        if execution:
            st.code(
                f"Reason: {execution.get('reason','')}\n\nSTDOUT:\n{execution.get('stdout','')}\n\nSTDERR:\n{execution.get('stderr','')}",
                language="text",
            )
        else:
            st.info("FreeCAD ще не запускався.")

    with tabs[5]:
        rows = []
        for category, paths in artifacts.items():
            for value in paths:
                p = Path(value)
                if p.is_file():
                    rows.append({"Категорія": category, "Файл": p.name, "Розмір": p.stat().st_size, "Шлях": str(p)})
        if rows:
            st.dataframe(rows, hide_index=True, use_container_width=True)
            selected_file = st.selectbox("Завантажити", [r["Шлях"] for r in rows])
            p = Path(selected_file)
            st.download_button(
                f"Завантажити {p.name}", p.read_bytes(), file_name=p.name,
                key=f"download_{p}_{p.stat().st_mtime_ns}", use_container_width=True,
            )
        else:
            st.info("Артефактів ще немає.")
