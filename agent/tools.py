"""
Anthropic tool schema definitions and TOOL_REGISTRY.

Schemas are passed to client.messages.create(tools=[...]).
TOOL_REGISTRY maps tool name → Python implementation callable.
"""

from tools.csv_io import get_schema
from tools.filter import filter_rows
from tools.transform import transform_columns
from tools.aggregate import group_by_aggregate, describe_statistics
from tools.charts import generate_chart

# ---------------------------------------------------------------------------
# Tool schema definitions (Anthropic format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "provide_plan",
        "description": (
            "MUST be called first, before any data operation. "
            "Presents the step-by-step execution plan to the user. "
            "Use clarification_needed=true if the task is ambiguous and you need more info."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "description": "Ordered list of steps you will execute.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step_number": {"type": "integer"},
                            "description": {"type": "string", "description": "What this step does in plain English."},
                            "tool_to_use": {"type": "string", "description": "Name of the tool this step will call."},
                        },
                        "required": ["step_number", "description", "tool_to_use"],
                    },
                },
                "clarification_needed": {
                    "type": "boolean",
                    "description": "Set to true if you need clarification before executing.",
                },
                "questions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Questions to ask the user if clarification_needed is true.",
                },
            },
            "required": ["steps"],
        },
    },
    {
        "name": "get_csv_schema",
        "description": (
            "Read the schema of the current working CSV. "
            "Returns column names, dtypes, row count, null counts, and 3 sample rows. "
            "Call this before planning to understand the data structure."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the CSV file in the output/ directory.",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "filter_rows",
        "description": "Filter rows based on one or more conditions. Returns a new CSV with only matching rows.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to input CSV in output/."},
                "conditions": {
                    "type": "array",
                    "description": "List of filter conditions (all must be true — AND logic).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "column": {"type": "string"},
                            "operator": {
                                "type": "string",
                                "enum": ["==", "!=", ">", "<", ">=", "<=", "contains", "startswith", "isnull", "notnull"],
                            },
                            "value": {"description": "The comparison value (omit for isnull/notnull)."},
                        },
                        "required": ["column", "operator"],
                    },
                },
                "output_file": {"type": "string", "description": "Absolute path for the output CSV in output/."},
            },
            "required": ["file_path", "conditions", "output_file"],
        },
    },
    {
        "name": "transform_columns",
        "description": (
            "Apply column-level transformations: rename, cast type, fill nulls, drop duplicates, sort. "
            "Multiple operations can be batched in a single call."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "operations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "operation": {
                                "type": "string",
                                "enum": ["rename", "cast_type", "fill_nulls", "drop_duplicates", "sort"],
                            },
                            "column": {"type": "string", "description": "Target column (not needed for drop_duplicates)."},
                            "params": {
                                "type": "object",
                                "description": (
                                    "rename: {new_name} | "
                                    "cast_type: {target_type: int|float|str|bool|datetime} | "
                                    "fill_nulls: {strategy: mean|median|mode|ffill|bfill|value, value?} | "
                                    "drop_duplicates: {subset?: [col,...]} | "
                                    "sort: {column, ascending?: bool}"
                                ),
                            },
                        },
                        "required": ["operation"],
                    },
                },
                "output_file": {"type": "string"},
            },
            "required": ["file_path", "operations", "output_file"],
        },
    },
    {
        "name": "aggregate_data",
        "description": "Group rows by columns and aggregate numeric columns. Returns a summarized CSV.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "group_by_columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Columns to group by.",
                },
                "aggregations": {
                    "type": "object",
                    "description": "Mapping of column_name → list of agg functions. E.g. {\"amount\": [\"sum\", \"mean\"]}",
                    "additionalProperties": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["sum", "mean", "median", "min", "max", "count", "std", "first", "last"],
                        },
                    },
                },
                "output_file": {"type": "string"},
            },
            "required": ["file_path", "group_by_columns", "aggregations", "output_file"],
        },
    },
    {
        "name": "describe_statistics",
        "description": "Get summary statistics (count, mean, std, min, max, percentiles) for numeric columns. Read-only — does not create a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Columns to describe. Defaults to all numeric columns if omitted.",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "generate_chart",
        "description": "Generate an interactive Plotly chart from CSV data and save it for display.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "line", "scatter", "histogram", "pie", "heatmap"],
                },
                "x_column": {"type": "string", "description": "Column for the X axis (or labels for pie)."},
                "output_file": {"type": "string", "description": "Path for output JSON chart file in output/charts/."},
                "y_column": {"type": "string", "description": "Column for Y axis (required for bar/line/scatter/pie)."},
                "title": {"type": "string"},
                "color_column": {"type": "string", "description": "Column to use for color grouping."},
                "top_n": {"type": "integer", "description": "Limit to top N rows by y_column before charting."},
            },
            "required": ["file_path", "chart_type", "x_column", "output_file"],
        },
    },
    {
        "name": "save_result",
        "description": "Copy the current working CSV to a user-friendly named file in output/.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Current working CSV path."},
                "output_filename": {"type": "string", "description": "Desired filename (e.g. 'sales_filtered.csv')."},
            },
            "required": ["file_path", "output_filename"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool dispatch registry
# ---------------------------------------------------------------------------

def _save_result(file_path: str, output_filename: str) -> dict:
    """Copy the current file to a named output path."""
    import shutil
    import os
    from pathlib import Path
    from tools.safety import validate_file_exists, validate_output_path

    resolved_src = validate_file_exists(file_path)
    output_dir = str(Path(__file__).parent.parent / "output")
    dest = os.path.join(output_dir, output_filename)
    validate_output_path(dest)
    shutil.copy2(resolved_src, dest)
    return {
        "status": "success",
        "message": f"Saved result to '{output_filename}'",
        "output_file": dest,
    }


def _provide_plan(steps: list, clarification_needed: bool = False, questions: list | None = None) -> dict:
    """Acknowledge plan receipt (the agent loop handles rendering)."""
    return {
        "status": "success",
        "message": "Plan received and displayed to user.",
        "step_count": len(steps),
    }


TOOL_REGISTRY: dict = {
    "provide_plan": _provide_plan,
    "get_csv_schema": lambda file_path: get_schema(file_path),
    "filter_rows": filter_rows,
    "transform_columns": transform_columns,
    "aggregate_data": group_by_aggregate,
    "describe_statistics": describe_statistics,
    "generate_chart": generate_chart,
    "save_result": _save_result,
}


def dispatch(tool_name: str, tool_input: dict) -> dict:
    """Look up and call the tool, returning a result dict."""
    fn = TOOL_REGISTRY.get(tool_name)
    if fn is None:
        from tools.safety import ToolError
        raise ToolError(f"Unknown tool '{tool_name}'")
    return fn(**tool_input)
