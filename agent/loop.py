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
    UndoPerformed,
    TokenUsageUpdate,
)
from tools.csv_io import get_schema


# Tools that permanently update the working file (tracked for undo)
_CSV_WRITE_TOOLS = {"transform_columns", "save_result"}

# Tools that produce a result CSV for display only — working file must NOT change
_CSV_DISPLAY_TOOLS = {"filter_rows", "aggregate_data"}


def run(
    user_message: str,
    working_file: str,
    conversation_history: list[BaseMessage],
    file_history: list[str] | None = None,
) -> Generator[Any, None, None]:
    """
    Generator — yields typed events for app.py to render in real time.

    conversation_history is mutated in-place (appended) for multi-turn support.
    file_history is mutated in-place: each CSV-writing tool appends its output_file,
    and undo_last_operation pops the latest entry to restore the previous state.
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
    total_input_tokens: int = 0
    total_output_tokens: int = 0

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

                    elif tool_name == "undo_last_operation":
                        if file_history is not None and len(file_history) > 1:
                            file_history.pop()  # remove current (last) file
                            restored = file_history[-1]
                            yield UndoPerformed(
                                restored_file=restored,
                                message=f"Reverted to previous file: {restored}",
                            )
                        else:
                            yield AgentError(message="Nothing to undo — no previous operation found.")

                    elif tool_name in _CSV_WRITE_TOOLS or tool_name in _CSV_DISPLAY_TOOLS:
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
                            output_file = result.get("output_file", "")
                            display_only = tool_name in _CSV_DISPLAY_TOOLS
                            # Only track in undo history for true write operations
                            if not display_only and file_history is not None and output_file:
                                file_history.append(output_file)
                            yield DataFrameResult(
                                output_file=output_file,
                                row_count=result.get("row_count", 0),
                                columns=result.get("columns", []),
                                message=result.get("message", ""),
                                display_only=display_only,
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
                    if isinstance(msg, AIMessage):
                        usage = getattr(msg, "usage_metadata", None) or {}
                        total_input_tokens += usage.get("input_tokens", 0)
                        total_output_tokens += usage.get("output_tokens", 0)

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

    if total_input_tokens or total_output_tokens:
        yield TokenUsageUpdate(
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            total_tokens=total_input_tokens + total_output_tokens,
        )


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
