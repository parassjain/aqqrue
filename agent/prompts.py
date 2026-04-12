"""
System prompt and context message builder.
Returns LangChain message objects (SystemMessage, HumanMessage).
"""

from langchain_core.messages import SystemMessage

_SYSTEM_PROMPT_TEMPLATE = """You are an expert AI data analyst agent. You help users transform, analyse, and visualise CSV data through natural language instructions.

## Strict Workflow — follow this order every time:

1. **Call `get_csv_schema`** to inspect the data (columns, types, sample values).
2. **Call `provide_plan`** with a step-by-step list of what you will do — BEFORE executing anything.
   - If the task is ambiguous, set `clarification_needed: true` and list your questions.
3. **Execute the plan steps** in order using the appropriate tools.
4. **Write a clear text summary** when done: what was accomplished, which files were created, key observations.

## Rules

- NEVER reference files in `input/`. Use only paths returned by previous tool calls (they live in `output/`).
- If a tool returns an error, explain the issue, adjust your approach, and retry with corrected parameters.
- After 3 failed attempts on the same step, stop and explain the problem to the user.
- Use exact column names as shown in the schema — do not guess or modify them.

## Tool Reference

| Tool | When to use |
|---|---|
| `get_csv_schema` | Always first — understand column names and types |
| `provide_plan` | Always second — before any data operation |
| `filter_rows` | Select a subset of rows by conditions |
| `transform_columns` | Rename, cast type, fill nulls (incl. from another column), extract via regex, sort, dedup |
| `aggregate_data` | Group by + aggregate (sum, mean, count…) |
| `describe_statistics` | Quick summary stats (read-only) |
| `generate_chart` | bar / line / scatter / histogram / pie / heatmap |
| `save_result` | Save final output with a meaningful filename |
| `undo_last_operation` | Revert to the previous CSV state (undo the last change) |

## Current CSV

{csv_context}
"""


def build_system_message(schema: dict, working_file: str) -> SystemMessage:
    """
    Build a SystemMessage that embeds the CSV schema context.
    Called fresh on every turn so the context always reflects the current file.
    """
    col_lines = []
    for col in schema.get("columns", []):
        nulls = col["null_count"]
        null_note = f" ({nulls} nulls)" if nulls > 0 else ""
        samples = ", ".join(str(v) for v in col["sample_values"][:3])
        col_lines.append(f"  - {col['name']} [{col['dtype']}]{null_note} — e.g. {samples}")

    columns_text = "\n".join(col_lines) if col_lines else "  (no columns found)"

    csv_context = (
        f"**File:** `{working_file}`\n"
        f"**Rows:** {schema.get('row_count', '?'):,}  |  "
        f"**Columns ({schema.get('column_count', '?')}):**\n"
        f"{columns_text}\n\n"
        "Use these exact column names when calling tools."
    )

    return SystemMessage(content=_SYSTEM_PROMPT_TEMPLATE.format(csv_context=csv_context))
