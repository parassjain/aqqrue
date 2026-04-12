"""
Streamlit entry point for the AI CSV Workflow Agent.
Run with: streamlit run app.py
"""

import os
import shutil
import uuid
import json
from pathlib import Path

import pandas as pd
import plotly.io as pio
import streamlit as st

from agent import loop as agent_loop
from agent.planner import (
    PlanCreated,
    PlanStepStarted,
    PlanStepCompleted,
    PlanStepFailed,
    DataFrameResult,
    ChartGenerated,
    StatsResult,
    FinalResponse,
    AgentError,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).parent
_INPUT_DIR = _ROOT / "input"
_OUTPUT_DIR = _ROOT / "output"
_INPUT_DIR.mkdir(exist_ok=True)
_OUTPUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="CSV AI Agent",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
defaults = {
    "messages": [],           # Claude API conversation history
    "ui_messages": [],        # Rendered chat log for display
    "working_file": None,     # Current output/ CSV path
    "session_id": None,       # UUID for this upload session
    "uploaded_filename": None,
    "step_counter": [0],      # Mutable counter for versioned output paths
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------------------------------------------------------
# Sidebar — file upload
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("📊 CSV AI Agent")
    st.caption("Upload a CSV, then describe what you want done.")

    uploaded = st.file_uploader("Upload CSV", type=["csv"], key="file_uploader")

    if uploaded and uploaded.name != st.session_state.uploaded_filename:
        # New file — reset session
        session_id = uuid.uuid4().hex[:8]
        st.session_state.session_id = session_id
        st.session_state.uploaded_filename = uploaded.name
        st.session_state.messages = []
        st.session_state.ui_messages = []
        st.session_state.step_counter = [0]

        # Save original to input/ (immutable)
        input_path = _INPUT_DIR / f"{session_id}_{uploaded.name}"
        input_path.write_bytes(uploaded.getvalue())

        # Copy to output/ (working copy)
        output_path = _OUTPUT_DIR / f"{session_id}_{uploaded.name}"
        shutil.copy2(input_path, output_path)
        st.session_state.working_file = str(output_path)

        # Show schema preview
        try:
            df_preview = pd.read_csv(str(output_path))
            st.success(f"Loaded: **{uploaded.name}**  \n{len(df_preview):,} rows × {len(df_preview.columns)} columns")
            with st.expander("Column preview", expanded=False):
                col_info = pd.DataFrame({
                    "Column": df_preview.columns,
                    "Type": df_preview.dtypes.values,
                    "Nulls": df_preview.isnull().sum().values,
                })
                st.dataframe(col_info, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Could not read CSV: {e}")

    if st.session_state.working_file:
        st.divider()
        if st.button("🗑️ Clear session", use_container_width=True):
            for key in list(defaults.keys()):
                st.session_state[key] = defaults[key]
            st.rerun()

# ---------------------------------------------------------------------------
# Main chat area
# ---------------------------------------------------------------------------
st.header("Chat with your data")

def _render_ui_message(msg: dict) -> None:
    """Render a stored UI message."""
    if msg.get("text"):
        st.markdown(msg["text"])
    if msg.get("plan_markdown"):
        st.markdown(msg["plan_markdown"])
    if msg.get("dataframes"):
        for df_info in msg["dataframes"]:
            st.caption(df_info["caption"])
            st.dataframe(df_info["data"], use_container_width=True)
            if df_info.get("download_path"):
                _offer_download(df_info["download_path"], df_info.get("label", "Download CSV"))
    if msg.get("charts"):
        for chart_info in msg["charts"]:
            try:
                fig = pio.from_json(open(chart_info["path"]).read())
                st.plotly_chart(fig, use_container_width=True)
            except Exception:
                st.warning(f"Could not render chart: {chart_info['path']}")
    if msg.get("stats"):
        for stat in msg["stats"]:
            st.caption(stat["message"])
            st.dataframe(pd.DataFrame(stat["data"]), use_container_width=True)
    if msg.get("error"):
        st.error(msg["error"])


# Re-render history properly
for msg in st.session_state.ui_messages:
    with st.chat_message(msg["role"]):
        _render_ui_message(msg)


def _offer_download(file_path: str, label: str = "Download CSV") -> None:
    try:
        with open(file_path, "rb") as f:
            st.download_button(
                label=label,
                data=f.read(),
                file_name=os.path.basename(file_path),
                mime="text/csv",
                key=f"dl_{uuid.uuid4().hex[:6]}",
            )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------
if not st.session_state.working_file:
    st.info("Upload a CSV file in the sidebar to get started.")
    st.stop()

user_input = st.chat_input("Describe what you want to do with this data...")

if user_input:
    # Show user message
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.ui_messages.append({"role": "user", "text": user_input})

    # Prepare UI message accumulator for this assistant turn
    assistant_ui: dict = {
        "role": "assistant",
        "text": "",
        "plan_markdown": "",
        "dataframes": [],
        "charts": [],
        "stats": [],
        "error": "",
    }

    with st.chat_message("assistant"):
        status_container = st.status("Thinking...", expanded=True)
        final_text_placeholder = st.empty()

        with status_container:
            plan_placeholder = st.empty()
            progress_lines: list[str] = []

            def _update_progress(line: str) -> None:
                progress_lines.append(line)
                plan_placeholder.markdown("\n".join(progress_lines))

            try:
                for event in agent_loop.run(
                    user_message=user_input,
                    working_file=st.session_state.working_file,
                    conversation_history=st.session_state.messages,
                    session_id=st.session_state.session_id,
                    step_counter=st.session_state.step_counter,
                ):
                    if isinstance(event, PlanCreated):
                        plan_md = event.plan.to_markdown()
                        plan_placeholder.markdown(plan_md)
                        assistant_ui["plan_markdown"] = plan_md
                        status_container.update(label="Executing plan...")

                    elif isinstance(event, PlanStepStarted):
                        _update_progress(f"🔄 **Step {event.step.step_number}:** {event.step.description}")

                    elif isinstance(event, PlanStepCompleted):
                        # Update the last progress line to show completion
                        if progress_lines:
                            progress_lines[-1] = f"✅ **Step {event.step.step_number}:** {event.step.description}"
                            plan_placeholder.markdown("\n".join(progress_lines))

                    elif isinstance(event, PlanStepFailed):
                        if progress_lines:
                            progress_lines[-1] = f"❌ **Step {event.step.step_number}:** {event.step.description} — {event.error}"
                            plan_placeholder.markdown("\n".join(progress_lines))

                    elif isinstance(event, DataFrameResult):
                        try:
                            df = pd.read_csv(event.output_file).head(10)
                            st.caption(f"📄 {event.message}")
                            st.dataframe(df, use_container_width=True)
                            _offer_download(event.output_file, "Download result CSV")
                            assistant_ui["dataframes"].append({
                                "caption": event.message,
                                "data": df,
                                "download_path": event.output_file,
                            })
                        except Exception as e:
                            st.warning(f"Could not preview result: {e}")

                    elif isinstance(event, ChartGenerated):
                        try:
                            fig = pio.from_json(open(event.chart_file).read())
                            st.plotly_chart(fig, use_container_width=True)
                            assistant_ui["charts"].append({"path": event.chart_file})
                        except Exception as e:
                            st.warning(f"Could not render chart: {e}")

                    elif isinstance(event, StatsResult):
                        try:
                            stats_df = pd.DataFrame(event.statistics).round(4)
                            st.caption(f"📊 {event.message}")
                            st.dataframe(stats_df, use_container_width=True)
                            assistant_ui["stats"].append({"message": event.message, "data": event.statistics})
                        except Exception:
                            st.json(event.statistics)

                    elif isinstance(event, FinalResponse):
                        status_container.update(label="Done ✅", state="complete", expanded=False)
                        final_text_placeholder.markdown(event.text)
                        assistant_ui["text"] = event.text

                    elif isinstance(event, AgentError):
                        status_container.update(label="Error ❌", state="error", expanded=True)
                        st.error(event.message)
                        assistant_ui["error"] = event.message

            except Exception as e:
                status_container.update(label="Error ❌", state="error", expanded=True)
                error_msg = f"Agent error: {e}"
                st.error(error_msg)
                assistant_ui["error"] = error_msg

    st.session_state.ui_messages.append(assistant_ui)
