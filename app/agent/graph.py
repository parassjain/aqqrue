"""Core LangGraph graph — the heart of the agentic CSV processor."""

from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes.router import router_node
from app.agent.nodes.analysis import analysis_node
from app.agent.nodes.planner import planner_node
from app.agent.nodes.code_generator import code_generator_node
from app.agent.nodes.validator import validator_node
from app.agent.nodes.preview import preview_node
from app.agent.nodes.executor import executor_node
from app.agent.nodes.auditor import auditor_node
from app.config import settings


def _route_after_validation(state: AgentState) -> str:
    """Route after validation: retry code generation or proceed to preview."""
    validation = state.get("validation_result", {})
    if validation.get("valid", False):
        return "preview"

    retry_count = state.get("retry_count", 0)
    if retry_count >= settings.MAX_RETRIES:
        return "fail"

    return "retry_code_gen"


def _route_after_preview(state: AgentState) -> str:
    """Route after preview: if preview failed, retry; otherwise execute."""
    preview = state.get("preview", {})
    if state.get("last_error"):
        retry_count = state.get("retry_count", 0)
        if retry_count >= settings.MAX_RETRIES:
            return "fail"
        return "retry_code_gen"
    return "execute"


def _route_after_execution(state: AgentState) -> str:
    """Route after execution: if failed, retry; otherwise audit."""
    exec_result = state.get("execution_result", {})
    if exec_result.get("success", False):
        return "audit"

    retry_count = state.get("retry_count", 0)
    if retry_count >= settings.MAX_RETRIES:
        return "fail"

    return "retry_code_gen"


def _fail_node(state: AgentState) -> dict:
    """Terminal node for when all retries are exhausted."""
    last_error = state.get("last_error", "Unknown error")
    return {
        "error": last_error,
        "response_message": f"I wasn't able to complete this operation after {settings.MAX_RETRIES} attempts. Last error: {last_error}",
    }


def _increment_retry(state: AgentState) -> dict:
    """Increment retry count before re-entering code generator."""
    return {"retry_count": state.get("retry_count", 0) + 1}


def _route_after_router(state: AgentState) -> str:
    """Route after router: answer questions directly, run analysis, or proceed to planning."""
    intent = state.get("intent")
    if intent == "question":
        return "answer"
    if intent == "analysis":
        return "analysis"
    return "plan"


def build_graph() -> StateGraph:
    """Build and compile the agent graph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("planner", planner_node)
    graph.add_node("code_generator", code_generator_node)
    graph.add_node("validator", validator_node)
    graph.add_node("preview", preview_node)
    graph.add_node("executor", executor_node)
    graph.add_node("auditor", auditor_node)
    graph.add_node("fail", _fail_node)
    graph.add_node("increment_retry", _increment_retry)

    # Entry point
    graph.set_entry_point("router")

    # Router: questions end immediately, operations proceed to planner
    graph.add_conditional_edges("router", _route_after_router, {
        "answer": END,
        "plan": "planner",
    })

    # Edges
    graph.add_edge("planner", "code_generator")
    graph.add_edge("code_generator", "validator")

    # After validation: proceed, retry, or fail
    graph.add_conditional_edges("validator", _route_after_validation, {
        "preview": "preview",
        "retry_code_gen": "increment_retry",
        "fail": "fail",
    })

    # After preview: execute, retry, or fail
    graph.add_conditional_edges("preview", _route_after_preview, {
        "execute": "executor",
        "retry_code_gen": "increment_retry",
        "fail": "fail",
    })

    # After execution: audit, retry, or fail
    graph.add_conditional_edges("executor", _route_after_execution, {
        "audit": "auditor",
        "retry_code_gen": "increment_retry",
        "fail": "fail",
    })

    # Retry loops back to code_generator
    graph.add_edge("increment_retry", "code_generator")

    # Terminal nodes
    graph.add_edge("auditor", END)
    graph.add_edge("fail", END)

    return graph.compile()


# Compiled graph singleton
agent_graph = build_graph()
