from app.agent.state import AgentState
from app.agent.tools.sandbox import run_in_sandbox


def executor_node(state: AgentState) -> dict:
    """Execute the generated code on the full CSV in the Docker sandbox."""
    from app.services.session_manager import session_manager

    csv_mgr = session_manager.get_session(state["session_id"])
    if csv_mgr is None:
        return {
            "execution_result": {
                "success": False,
                "csv_output": None,
                "error": "Session not found",
            }
        }

    csv_bytes = csv_mgr.get_current_csv_bytes()
    if csv_bytes is None:
        return {
            "execution_result": {
                "success": False,
                "csv_output": None,
                "error": "No CSV loaded",
            }
        }

    result = run_in_sandbox(state["generated_code"], csv_bytes)

    return {
        "execution_result": {
            "success": result["success"],
            "csv_output": result.get("csv_output"),
            "error": result.get("error"),
            "rows": result.get("rows"),
            "columns": result.get("columns"),
        },
        "last_error": result.get("error", "") if not result["success"] else "",
    }
