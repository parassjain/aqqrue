import logging
import time

from app.agent.state import AgentState

logger = logging.getLogger(__name__)


def auditor_node(state: AgentState) -> dict:
    """Log the completed operation and save the new CSV version."""
    logger.info("[NODE: auditor] Auditing execution result")
    from app.services.session_manager import session_manager

    csv_mgr = session_manager.get_session(state["session_id"])
    exec_result = state["execution_result"]

    if not exec_result["success"] or exec_result.get("csv_output") is None:
        logger.warning("[NODE: auditor] Execution failed, skipping save: %s", exec_result.get("error"))
        return {
            "error": exec_result.get("error", "Execution failed"),
            "response_message": f"Operation failed: {exec_result.get('error', 'Unknown error')}",
        }

    # Save new version
    metadata_before = state["csv_metadata"]
    new_metadata = csv_mgr.save_version(
        exec_result["csv_output"],
        state["user_message"],
    )

    # Create audit entry
    audit_entry = {
        "turn": len(state.get("audit_log", [])) + 1,
        "instruction": state["user_message"],
        "code": state["generated_code"],
        "status": "success",
        "timestamp": time.time(),
        "rows_before": metadata_before.get("rows", 0),
        "rows_after": exec_result.get("rows", 0),
    }

    logger.info("[NODE: auditor] Saved version v%s: %d→%d rows",
                new_metadata["version"],
                audit_entry["rows_before"],
                audit_entry["rows_after"])
    audit_log = list(state.get("audit_log", []))
    audit_log.append(audit_entry)

    # Build response message
    preview = state.get("preview", {})
    response_parts = [f"Done. {preview.get('summary', 'Operation completed.')}"]
    if exec_result.get("rows") is not None:
        response_parts.append(
            f"Output: {exec_result['rows']} rows, {len(exec_result.get('columns', []))} columns."
        )
    response_parts.append(f"Version: v{new_metadata['version']}")

    return {
        "audit_log": audit_log,
        "csv_metadata": new_metadata,
        "error": None,
        "response_message": " ".join(response_parts),
    }
