"""
Core agentic loop: orchestrates Claude API calls and tool dispatch.
run() is a generator — yields typed event objects consumed by app.py.
"""

import os
from typing import Generator, Any

import anthropic
from dotenv import load_dotenv

from agent.tools import TOOL_DEFINITIONS, dispatch
from agent.prompts import SYSTEM_PROMPT, build_context_message
from agent.planner import (
    Plan,
    PlanStep,
    StepStatus,
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
from tools.csv_io import get_schema
from tools.safety import ToolError

load_dotenv()

_MAX_TOOL_ERRORS = 3
_MODEL = "claude-sonnet-4-6"


def _make_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")
    return anthropic.Anthropic(api_key=api_key)


def _extract_text(content_blocks: list) -> str:
    return " ".join(b.text for b in content_blocks if b.type == "text")


def _tool_result_block(tool_use_id: str, result: dict, is_error: bool = False) -> dict:
    import json
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": json.dumps(result),
        "is_error": is_error,
    }


def run(
    user_message: str,
    working_file: str,
    conversation_history: list[dict],
    session_id: str,
    step_counter: list[int],  # mutable list used as a counter across calls
) -> Generator[Any, None, None]:
    """
    Generator-based agentic loop.

    Yields typed events (PlanCreated, PlanStepStarted, DataFrameResult, etc.)
    for app.py to render in real time.

    conversation_history is mutated in-place so multi-turn context is preserved.
    step_counter is a [int] list so the caller can track the global step number
    across multiple user messages in the same session.
    """
    client = _make_client()

    # Build context + user message
    schema = get_schema(working_file)
    context_msg = build_context_message(schema, working_file)

    # For the first turn, inject context as a separate user message (simulates assistant memory)
    # For subsequent turns, conversation_history already has prior context
    messages = list(conversation_history)
    if not messages:
        messages.append(context_msg)
        messages.append({"role": "assistant", "content": "I've loaded your CSV. What would you like me to do with it?"})

    messages.append({"role": "user", "content": user_message})

    plan: Plan | None = None
    consecutive_errors = 0

    while True:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Append Claude's response to history
        messages.append({"role": "assistant", "content": response.content})

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        # No tool calls → Claude gave a final text response
        if not tool_use_blocks:
            text = _extract_text(response.content)
            conversation_history.clear()
            conversation_history.extend(messages)
            yield FinalResponse(text=text)
            return

        # Process all tool_use blocks in this response
        tool_results = []

        for block in tool_use_blocks:
            tool_name = block.name
            tool_input = block.input

            # --- provide_plan: special handling ---
            if tool_name == "provide_plan":
                plan = Plan.from_tool_input(tool_input)
                yield PlanCreated(plan=plan)
                tool_results.append(_tool_result_block(block.id, {"status": "success", "message": "Plan displayed to user."}))
                consecutive_errors = 0
                continue

            # Advance the step counter for output file naming
            step_counter[0] += 1
            current_step = step_counter[0]

            # Update matching plan step status
            matching_step: PlanStep | None = None
            if plan:
                matching_step = plan.get_step_for_tool(tool_name)
                if matching_step:
                    matching_step.status = StepStatus.ACTIVE
                    yield PlanStepStarted(step=matching_step)

            # Inject output_file path if tool requires it (but caller didn't provide one)
            if "output_file" in _get_required_params(tool_name) and "output_file" not in tool_input:
                tool_input = dict(tool_input)  # don't mutate the original
                tool_input["output_file"] = _make_output_path(session_id, current_step, tool_name, working_file)

            # Dispatch to tool implementation
            try:
                result = dispatch(tool_name, tool_input)
                consecutive_errors = 0

                # Yield domain-specific events
                if tool_name == "generate_chart":
                    yield ChartGenerated(
                        chart_file=result.get("chart_file", ""),
                        chart_type=result.get("chart_type", ""),
                        title=result.get("title", ""),
                    )
                elif tool_name == "describe_statistics":
                    yield StatsResult(
                        statistics=result.get("statistics", {}),
                        message=result.get("message", ""),
                    )
                elif result.get("output_file"):
                    yield DataFrameResult(
                        output_file=result["output_file"],
                        row_count=result.get("row_count", 0),
                        columns=result.get("columns", []),
                        message=result.get("message", ""),
                    )

                if matching_step:
                    matching_step.status = StepStatus.DONE
                    yield PlanStepCompleted(step=matching_step, result_summary=result.get("message", ""))

                tool_results.append(_tool_result_block(block.id, result))

            except ToolError as e:
                consecutive_errors += 1
                error_result = {"status": "error", "message": str(e)}
                tool_results.append(_tool_result_block(block.id, error_result, is_error=True))

                if matching_step:
                    matching_step.status = StepStatus.FAILED
                    yield PlanStepFailed(step=matching_step, error=str(e))

                if consecutive_errors >= _MAX_TOOL_ERRORS:
                    yield AgentError(
                        message=f"Too many consecutive errors on '{tool_name}'. Last error: {e}"
                    )
                    conversation_history.clear()
                    conversation_history.extend(messages)
                    return

            except Exception as e:
                consecutive_errors += 1
                error_result = {"status": "error", "message": f"Unexpected error: {e}"}
                tool_results.append(_tool_result_block(block.id, error_result, is_error=True))

                if matching_step:
                    matching_step.status = StepStatus.FAILED
                    yield PlanStepFailed(step=matching_step, error=str(e))

        # Feed all tool results back to Claude in one message
        messages.append({"role": "user", "content": tool_results})

        # Loop continues — Claude will call more tools or give final text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOOLS_WITH_OUTPUT = {"filter_rows", "transform_columns", "aggregate_data", "generate_chart", "save_result"}


def _get_required_params(tool_name: str) -> list[str]:
    """Return list of required param names for a tool."""
    for t in TOOL_DEFINITIONS:
        if t["name"] == tool_name:
            return t["input_schema"].get("required", [])
    return []


def _make_output_path(session_id: str, step: int, tool_name: str, working_file: str) -> str:
    """Generate a versioned output path for a tool's result."""
    import os
    from pathlib import Path

    output_dir = str(Path(__file__).parent.parent / "output")
    base = os.path.splitext(os.path.basename(working_file))[0]

    if tool_name == "generate_chart":
        charts_dir = os.path.join(output_dir, "charts")
        os.makedirs(charts_dir, exist_ok=True)
        return os.path.join(charts_dir, f"{session_id}_step{step}_{base}.json")

    return os.path.join(output_dir, f"{session_id}_step{step}_{tool_name}_{base}.csv")
