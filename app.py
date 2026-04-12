"""
Streamlit entry point — CSV AI Agent.
Run: streamlit run app.py
"""

import os
import shutil
import uuid
from pathlib import Path

import pandas as pd
import plotly.io as pio
import streamlit as st
from langchain_core.messages import BaseMessage

import agent.loop as agent_loop
from agent.planner import (
    PlanCreated,
    PlanStepCompleted,
    PlanStepFailed,
    DataFrameResult,
    ChartGenerated,
    StatsResult,
    FinalResponse,
    AgentError,
    UndoPerformed,
    TokenUsageUpdate,
)
from config import LLM_PROVIDER, MODEL_NAME

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
st.set_page_config(page_title="CSV AI Agent", page_icon="📊", layout="wide")

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
_DEFAULTS: dict = {
    "messages": [],  # list[BaseMessage] — full LangChain conversation history
    "ui_messages": [],  # list[dict] — rendered chat log
    "working_file": None,  # str | None — current output/ CSV path
    "file_history": [],  # list[str] — stack of output/ paths for undo support
    "session_id": None,  # str — UUID for this upload session
    "uploaded_filename": None,  # str — original filename for display
    "session_tokens": {"input": 0, "output": 0, "total": 0},  # cumulative token usage
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("📊 CSV AI Agent")
    st.caption(f"Model: **{MODEL_NAME}** via **{LLM_PROVIDER}**")
    st.divider()

    uploaded = st.file_uploader("Upload a CSV file", type=["csv"])

    if uploaded and uploaded.name != st.session_state.uploaded_filename:
        sid = uuid.uuid4().hex[:8]
        st.session_state.session_id = sid
        st.session_state.uploaded_filename = uploaded.name
        st.session_state.messages = []
        st.session_state.ui_messages = []
        st.session_state.file_history = []

        # Save original to input/ (immutable)
        (_INPUT_DIR / f"{sid}_{uploaded.name}").write_bytes(uploaded.getvalue())

        # Working copy in output/
        out_path = _OUTPUT_DIR / f"{sid}_{uploaded.name}"
        shutil.copy2(_INPUT_DIR / f"{sid}_{uploaded.name}", out_path)
        st.session_state.working_file = str(out_path)
        st.session_state.file_history = [str(out_path)]

        try:
            df_prev = pd.read_csv(str(out_path))
            st.success(
                f"**{uploaded.name}**\n{len(df_prev):,} rows × {len(df_prev.columns)} columns"
            )
            with st.expander("Column preview", expanded=False):
                st.dataframe(
                    pd.DataFrame(
                        {
                            "Column": df_prev.columns,
                            "Type": df_prev.dtypes.astype(str).values,
                            "Nulls": df_prev.isnull().sum().values,
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
        except Exception as exc:
            st.error(f"Could not read CSV: {exc}")

    if st.session_state.working_file:
        st.divider()
        if st.button("🗑️ Clear session", use_container_width=True):
            for _k, _v in _DEFAULTS.items():
                st.session_state[_k] = _v
            st.rerun()
        st.divider()
        st.caption("**Session token usage**")
        tok = st.session_state.session_tokens
        col1, col2 = st.columns(2)
        col1.metric("Input", f"{tok['input']:,}")
        col2.metric("Output", f"{tok['output']:,}")
        st.caption(f"Total: **{tok['total']:,}**")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _render_ui_message(msg: dict) -> None:
    if msg.get("plan_markdown"):
        st.markdown(msg["plan_markdown"])
    if msg.get("text"):
        st.markdown(msg["text"])
    for df_info in msg.get("dataframes", []):
        st.caption(df_info["caption"])
        st.dataframe(df_info["data"], use_container_width=True)
        if df_info.get("download_path"):
            _offer_download(df_info["download_path"])
    for chart_info in msg.get("charts", []):
        try:
            fig = pio.from_json(open(chart_info["path"]).read())
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.warning(f"Could not render chart: {chart_info['path']}")
    for stat in msg.get("stats", []):
        st.caption(stat["message"])
        try:
            st.dataframe(pd.DataFrame(stat["data"]), use_container_width=True)
        except Exception:
            st.json(stat["data"])
    if msg.get("error"):
        st.error(msg["error"])
    if msg.get("token_usage"):
        tu = msg["token_usage"]
        st.caption(
            f"Tokens — {tu['input']:,} input · {tu['output']:,} output · **{tu['total']:,} total**"
        )


# ---------------------------------------------------------------------------
# Two-column layout: CSV preview (left) | Chat (right)
# ---------------------------------------------------------------------------
left_col, right_col = st.columns([1.1, 1], gap="large")

# ── Left: live CSV preview ──────────────────────────────────────────────────
with left_col:
    st.subheader("Live Data Preview")
    _csv_preview = st.empty()  # placeholder updated live as operations complete


def _update_csv_preview(file_path: str) -> None:
    """Re-render the left-column data table from the given CSV path."""
    try:
        df = pd.read_csv(file_path)
        with _csv_preview.container():
            st.caption(
                f"**{st.session_state.uploaded_filename}** · "
                f"{len(df):,} rows × {len(df.columns)} cols"
            )
            st.dataframe(df, use_container_width=True, height=600)
    except Exception as exc:
        _csv_preview.error(f"Could not read file: {exc}")


if st.session_state.working_file:
    _update_csv_preview(st.session_state.working_file)
else:
    _csv_preview.info("Upload a CSV file in the sidebar to get started.")

# ── Right: chat interface ───────────────────────────────────────────────────
with right_col:
    st.subheader("Chat with your data")

    # Fixed-height scrollable container for all chat messages — keeps input pinned below
    msgs_container = st.container(height=600, border=False)

    # Chat input rendered here so it stays at the bottom of the column
    if st.session_state.working_file:
        user_input = st.chat_input("Describe what you want to do with this data...")
    else:
        st.chat_input("Upload a CSV to get started…", disabled=True)
        user_input = None

    with msgs_container:
        # Re-render history
        for msg in st.session_state.ui_messages:
            with st.chat_message(msg["role"]):
                _render_ui_message(msg)

        if user_input:
            with st.chat_message("user"):
                st.markdown(user_input)
            st.session_state.ui_messages.append({"role": "user", "text": user_input})

            assistant_ui: dict = {
                "role": "assistant",
                "text": "",
                "plan_markdown": "",
                "dataframes": [],
                "charts": [],
                "stats": [],
                "error": "",
                "token_usage": None,
            }

            with st.chat_message("assistant"):
                status_box = st.status("Thinking…", expanded=True)
                final_placeholder = st.empty()
                token_placeholder = st.empty()

                with status_box:
                    progress_md: list[str] = []
                    progress_slot = st.empty()

                    def _refresh_progress() -> None:
                        progress_slot.markdown("\n\n".join(progress_md))

                    try:
                        for event in agent_loop.run(
                            user_message=user_input,
                            working_file=st.session_state.working_file,
                            conversation_history=st.session_state.messages,
                            file_history=st.session_state.file_history,
                        ):
                            if isinstance(event, PlanCreated):
                                plan_md = event.plan.to_markdown()
                                progress_md.clear()
                                progress_md.append(plan_md)
                                _refresh_progress()
                                assistant_ui["plan_markdown"] = plan_md
                                status_box.update(label="Executing plan…")

                            elif isinstance(event, PlanStepCompleted):
                                updated = (
                                    event.plan.to_markdown()
                                    if hasattr(event, "plan")
                                    else ""
                                )
                                if updated:
                                    progress_md[0] = updated
                                else:
                                    progress_md.append(
                                        f"✅ Step {event.step.step_number}: {event.step.description}"
                                    )
                                _refresh_progress()

                            elif isinstance(event, PlanStepFailed):
                                progress_md.append(
                                    f"❌ Step {event.step.step_number}: {event.error}"
                                )
                                _refresh_progress()

                            elif isinstance(event, DataFrameResult):
                                if event.output_file:
                                    if not event.display_only:
                                        # Permanent write — update working file and left-panel preview
                                        st.session_state.working_file = (
                                            event.output_file
                                        )
                                        _update_csv_preview(event.output_file)
                                    try:
                                        preview = pd.read_csv(event.output_file).head(
                                            10
                                        )
                                        st.caption(f"📄 {event.message}")
                                        st.dataframe(preview, use_container_width=True)
                                        if not event.display_only:
                                            _offer_download(event.output_file)
                                        assistant_ui["dataframes"].append(
                                            {
                                                "caption": event.message,
                                                "data": preview,
                                                "download_path": (
                                                    None
                                                    if event.display_only
                                                    else event.output_file
                                                ),
                                            }
                                        )
                                    except Exception as exc:
                                        st.warning(f"Preview failed: {exc}")

                            elif isinstance(event, ChartGenerated):
                                try:
                                    fig = pio.from_json(open(event.chart_file).read())
                                    st.plotly_chart(fig, use_container_width=True)
                                    assistant_ui["charts"].append(
                                        {"path": event.chart_file}
                                    )
                                except Exception as exc:
                                    st.warning(f"Chart render failed: {exc}")

                            elif isinstance(event, StatsResult):
                                try:
                                    st.caption(f"📊 {event.message}")
                                    st.dataframe(
                                        pd.DataFrame(event.statistics).round(4),
                                        use_container_width=True,
                                    )
                                    assistant_ui["stats"].append(
                                        {
                                            "message": event.message,
                                            "data": event.statistics,
                                        }
                                    )
                                except Exception:
                                    st.json(event.statistics)

                            elif isinstance(event, FinalResponse):
                                status_box.update(
                                    label="Done ✅", state="complete", expanded=False
                                )
                                final_placeholder.markdown(event.text)
                                assistant_ui["text"] = event.text

                            elif isinstance(event, UndoPerformed):
                                st.session_state.working_file = event.restored_file
                                _update_csv_preview(event.restored_file)
                                progress_md.append(
                                    f"↩️ Undone — restored to: `{os.path.basename(event.restored_file)}`"
                                )
                                _refresh_progress()
                                assistant_ui["text"] = (
                                    f"Undone. Restored to the previous state: `{os.path.basename(event.restored_file)}`"
                                )

                            elif isinstance(event, TokenUsageUpdate):
                                tu = {
                                    "input": event.input_tokens,
                                    "output": event.output_tokens,
                                    "total": event.total_tokens,
                                }
                                assistant_ui["token_usage"] = tu
                                st.session_state.session_tokens[
                                    "input"
                                ] += event.input_tokens
                                st.session_state.session_tokens[
                                    "output"
                                ] += event.output_tokens
                                st.session_state.session_tokens[
                                    "total"
                                ] += event.total_tokens
                                token_placeholder.caption(
                                    f"Tokens — {event.input_tokens:,} input · {event.output_tokens:,} output · **{event.total_tokens:,} total**"
                                )

                            elif isinstance(event, AgentError):
                                status_box.update(
                                    label="Error ❌", state="error", expanded=True
                                )
                                st.error(event.message)
                                assistant_ui["error"] = event.message

                    except Exception as exc:
                        status_box.update(
                            label="Error ❌", state="error", expanded=True
                        )
                        err = f"Unexpected error: {exc}"
                        st.error(err)
                        assistant_ui["error"] = err

            st.session_state.ui_messages.append(assistant_ui)
