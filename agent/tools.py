"""
LangChain @tool definitions wrapping the tools/ data functions.
Output paths are auto-generated (UUID-based) so the LLM never has to specify them.
"""

import os
import uuid
import shutil
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

_OUTPUT_DIR = str(Path(__file__).parent.parent / "output")


def _out(tool_name: str, input_file: str) -> str:
    """Generate a unique output path in output/ for this tool invocation."""
    base = os.path.splitext(os.path.basename(input_file))[0]
    uid = uuid.uuid4().hex[:6]
    return os.path.join(_OUTPUT_DIR, f"{uid}_{tool_name}_{base}.csv")


# ---------------------------------------------------------------------------
# Planning tool — MUST be called first
# ---------------------------------------------------------------------------

@tool
def provide_plan(steps: list[dict], clarification_needed: bool = False, questions: Optional[list[str]] = None) -> dict:
    """MUST be called first before any data operation. Presents the step-by-step plan to the user.
    steps: list of {step_number: int, description: str, tool_to_use: str}.
    Set clarification_needed=true if the task is ambiguous and list your questions."""
    return {
        "status": "success",
        "steps": steps or [],
        "clarification_needed": clarification_needed,
        "questions": questions or [],
    }


# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------

@tool
def get_csv_schema(file_path: str) -> dict:
    """Read CSV schema: column names, dtypes, row count, null counts, and 3 sample rows.
    Always call this before provide_plan to understand the data structure."""
    from tools.csv_io import get_schema
    return get_schema(file_path)


# ---------------------------------------------------------------------------
# Data operations
# ---------------------------------------------------------------------------

@tool
def filter_rows(file_path: str, conditions: list[dict]) -> dict:
    """Filter rows by one or more conditions (AND logic).
    Each condition: {column: str, operator: str, value: any}.
    Operators: ==, !=, >, <, >=, <=, contains, startswith, isnull, notnull.
    Returns path to new CSV with only matching rows."""
    from tools.filter import filter_rows as _filter
    return _filter(file_path, conditions, _out("filter", file_path))


@tool
def transform_columns(file_path: str, operations: list[dict]) -> dict:
    """Apply column-level transformations in sequence.
    Each operation: {operation: str, column: str, params: dict}.
    Operations:
      rename          -> params: {new_name: str}
      cast_type       -> params: {target_type: int|float|str|bool|datetime}
      fill_nulls      -> params: {strategy: mean|median|mode|ffill|bfill|value|from_column,
                                  value?: any,           (for strategy=value)
                                  source_column?: str}   (for strategy=from_column — fill nulls using another column)
      extract         -> params: {pattern: str,          (regex to extract from `column`)
                                  target_column: str,    (new or existing column to write extracted value into)
                                  group?: int}           (capture group index, default 0 = full match)
      drop_columns    -> params: {columns: [col,...]}   (drop one or more columns entirely)
      drop_duplicates -> params: {subset?: [col,...]}
      sort            -> params: {column: str, ascending?: bool}

    Tip — to fill nulls from another column's text (e.g. extract merchant from narration):
      1. extract: pull the relevant text from the source column into a temp column
      2. fill_nulls with strategy=from_column pointing at the temp column
      3. drop_columns to remove the temp column"""
    from tools.transform import transform_columns as _transform
    return _transform(file_path, operations, _out("transform", file_path))


@tool
def aggregate_data(file_path: str, group_by_columns: list[str], aggregations: dict) -> dict:
    """Group rows by columns and aggregate numeric columns.
    aggregations: {column_name: [list of functions]}.
    Functions: sum, mean, median, min, max, count, std, first, last.
    Example: {"amount": ["sum", "mean"], "quantity": ["count"]}.
    Returns path to aggregated CSV."""
    from tools.aggregate import group_by_aggregate
    return group_by_aggregate(file_path, group_by_columns, aggregations, _out("aggregate", file_path))


@tool
def describe_statistics(file_path: str, columns: Optional[list[str]] = None) -> dict:
    """Get summary statistics (count, mean, std, min, max, percentiles) for numeric columns.
    columns: optional list of column names. Defaults to all numeric columns. Read-only."""
    from tools.aggregate import describe_statistics as _stats
    return _stats(file_path, columns)


@tool
def undo_last_operation() -> dict:
    """Undo the last data operation and restore the CSV to its previous state.
    Call this when the user asks to undo, revert, or go back to the previous step.
    No parameters needed — the system handles the file restoration automatically."""
    return {"action": "undo_requested"}


@tool
def save_result(file_path: str, output_filename: str) -> dict:
    """Save the current working CSV to output/ with a meaningful filename.
    output_filename: desired name, e.g. 'sales_filtered.csv'."""
    from tools.safety import validate_file_exists, validate_output_path
    src = validate_file_exists(file_path)
    dest = os.path.join(_OUTPUT_DIR, output_filename)
    validate_output_path(dest)
    shutil.copy2(src, dest)
    return {
        "status": "success",
        "message": f"Saved result as '{output_filename}'",
        "output_file": dest,
    }


# ---------------------------------------------------------------------------
# Registry — order matters for the system prompt tool reference table
# ---------------------------------------------------------------------------

ALL_TOOLS = [
    provide_plan,
    get_csv_schema,
    filter_rows,
    transform_columns,
    aggregate_data,
    describe_statistics,
    save_result,
    undo_last_operation,
]
