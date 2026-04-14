import io
import logging
import pandas as pd

from app.agent.state import AgentState
from app.agent.tools.sandbox import run_in_sandbox

logger = logging.getLogger(__name__)


def preview_node(state: AgentState) -> dict:
    """Run the generated code on a sample of the CSV to produce a before/after preview."""
    from app.services.session_manager import session_manager

    csv_mgr = session_manager.get_session(state["session_id"])
    if csv_mgr is None:
        return {"error": "Session not found", "preview": {}}

    df = csv_mgr.get_current_dataframe()
    if df is None:
        return {"error": "No CSV loaded", "preview": {}}

    sample_bytes = df.to_csv(index=False).encode()

    # Run in sandbox on full CSV
    result = run_in_sandbox(state["generated_code"], sample_bytes)

    if not result["success"]:
        return {
            "preview": {
                "rows_affected": 0,
                "sample_before": [],
                "sample_after": [],
                "columns_added": [],
                "columns_removed": [],
                "summary": f"Preview failed: {result['error']}",
            },
            "last_error": result["error"],
        }

    # Parse output
    after_df = pd.read_csv(io.BytesIO(result["csv_output"]))
    before_cols = set(df.columns)
    after_cols = set(after_df.columns)

    preview = {
        "rows_affected": len(after_df),
        "sample_before": df.to_dict(orient="records"),
        "sample_after": after_df.to_dict(orient="records"),
        "columns_added": list(after_cols - before_cols),
        "columns_removed": list(before_cols - after_cols),
        "summary": _build_summary(df, after_df),
    }

    return {"preview": preview, "last_error": ""}


def _build_summary(before: pd.DataFrame, after: pd.DataFrame) -> str:
    parts = []
    before_cols = set(before.columns)
    after_cols = set(after.columns)

    added = after_cols - before_cols
    removed = before_cols - after_cols

    if added:
        parts.append(f"Columns added: {', '.join(added)}")
    if removed:
        parts.append(f"Columns removed: {', '.join(removed)}")
    if len(after) != len(before):
        parts.append(f"Row count: {len(before)} → {len(after)}")
    if not parts:
        parts.append("Data modified in existing columns")

    return "; ".join(parts)
