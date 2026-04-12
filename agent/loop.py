"""
Streaming wrapper around the LangGraph graph.

run() is a generator that:
  1. Builds the full message list (system + history + user message)
  2. Streams the LangGraph graph using stream_mode="updates"
  3. Parses each node update into typed events (from agent/planner.py)
  4. Updates conversation_history in-place for multi-turn support
"""

import json
from typing import Generator, Any

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
)

from agent.graph import create_graph
from agent.prompts import build_system_message
from agent.planner import (
    Plan,
    StepStatus,
    PlanCreated,
    PlanStepCompleted,
    PlanStepFailed,
    DataFrameResult,
    ChartGenerated,
    StatsResult,
    FinalResponse,
    AgentError,
)
from tools.csv_io import get_schema


# Tools that write a CSV and return an output_file
_CSV_OUTPUT_TOOLS = {"filter_rows", "transform_columns", "aggregate_data", "save_result"}


def run(
    user_message: str,
    working_file: str,
    conversation_history: list[BaseMessage],
) -> Generator[Any, None, None]:
    """
    Generator — yields typed events for app.py to render in real time.

    conversation_history is mutated in-place: the current turn's messages
    (HumanMessage + all AIMessages + ToolMessages) are appended at the end,
    preserving full multi-turn context for the next call.
    """
    graph = create_graph()

    # Build fresh schema-aware system message every turn
    schema = get_schema(working_file)
    system_msg = build_system_message(schema, working_file)

    # Full message list = system + prior history + current user message
    current_user_msg = HumanMessage(content=user_message)
    full_messages = [system_msg, *conversation_history, current_user_msg]

    plan: Plan | None = None
    new_messages: list[BaseMessage] = []  # messages added by nodes this turn

    try:
        for chunk in graph.stream(
            {"messages": full_messages},
            stream_mode="updates",
        ):
            # ── Tools node ran ────────────────────────────────────────────
            if "tools" in chunk:
                tool_messages: list[BaseMessage] = chunk["tools"].get("messages", [])
                new_messages.extend(tool_messages)

                for msg in tool_messages:
                    if not isinstance(msg, ToolMessage):
                        continue

                    result = _parse_tool_result(msg.content)
                    tool_name = msg.name or ""

                    if tool_name == "provide_plan":
                        plan = Plan.from_tool_result(result)
                        yield PlanCreated(plan=plan)

                    elif tool_name in _CSV_OUTPUT_TOOLS:
                        if result.get("status") == "error":
                            _mark_step_failed(plan, tool_name, result.get("message", ""))
                            yield PlanStepFailed(
                                step=_dummy_step(tool_name),
                                error=result.get("message", "Tool error"),
                            )
                        else:
                            step = _mark_step_done(plan, tool_name)
                            if step:
                                yield PlanStepCompleted(
                                    step=step,
                                    result_summary=result.get("message", ""),
                                )
                            yield DataFrameResult(
                                output_file=result.get("output_file", ""),
                                row_count=result.get("row_count", 0),
                                columns=result.get("columns", []),
                                message=result.get("message", ""),
                            )

                    elif tool_name == "generate_chart":
                        if result.get("status") == "error":
                            yield AgentError(message=result.get("message", "Chart error"))
                        else:
                            _mark_step_done(plan, tool_name)
                            yield ChartGenerated(
                                chart_file=result.get("chart_file", ""),
                                chart_type=result.get("chart_type", ""),
                                title=result.get("title", ""),
                            )

                    elif tool_name == "describe_statistics":
                        if result.get("status") == "success":
                            _mark_step_done(plan, tool_name)
                            yield StatsResult(
                                statistics=result.get("statistics", {}),
                                message=result.get("message", ""),
                            )

            # ── Agent node ran ────────────────────────────────────────────
            if "agent" in chunk:
                agent_messages: list[BaseMessage] = chunk["agent"].get("messages", [])
                new_messages.extend(agent_messages)

                for msg in agent_messages:
                    if isinstance(msg, AIMessage) and not msg.tool_calls:
                        # No more tool calls → this is the final text response
                        text = msg.content if isinstance(msg.content, str) else str(msg.content)
                        yield FinalResponse(text=text)

    except Exception as e:
        yield AgentError(message=f"Agent error: {e}")

    finally:
        # Persist this turn into conversation history for multi-turn support.
        # Includes: current HumanMessage + all AIMessages + all ToolMessages.
        conversation_history.append(current_user_msg)
        conversation_history.extend(new_messages)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_tool_result(content: Any) -> dict:
    """Safely parse a ToolMessage's content into a dict."""
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return {"status": "error", "message": content}
    return {"status": "error", "message": str(content)}


def _mark_step_done(plan: Plan | None, tool_name: str):
    """Mark the first matching plan step as DONE and return it."""
    if plan is None:
        return None
    step = plan.get_step_for_tool(tool_name)
    if step:
        step.status = StepStatus.DONE
    return step


def _mark_step_failed(plan: Plan | None, tool_name: str, error: str) -> None:
    if plan is None:
        return
    step = plan.get_step_for_tool(tool_name)
    if step:
        step.status = StepStatus.FAILED


def _dummy_step(tool_name: str):
    """Return a minimal PlanStep for tools not found in the plan (safety fallback)."""
    from agent.planner import PlanStep
    return PlanStep(step_number=0, description=tool_name, tool_to_use=tool_name, status=StepStatus.FAILED)
