"""
Safety layer: path traversal guard, column validation, query sanitizer.
All tool functions must call these validators before operating on data.
"""

import os
from pathlib import Path

# Resolve the output directory once at import time
_OUTPUT_DIR = str(Path(__file__).parent.parent / "output")


class ToolError(Exception):
    """Structured error returned to Claude as a tool_result with is_error=True."""
    pass


def validate_output_path(file_path: str) -> str:
    """
    Ensure file_path resolves to within the output/ directory.
    Returns the resolved absolute path.
    Raises ToolError on path traversal attempts.
    """
    resolved = os.path.realpath(os.path.abspath(file_path))
    output_real = os.path.realpath(os.path.abspath(_OUTPUT_DIR))
    if not resolved.startswith(output_real + os.sep) and resolved != output_real:
        raise ToolError(
            f"File path '{file_path}' is outside the allowed output/ directory. "
            "All operations must use files within the output/ directory."
        )
    return resolved


def validate_file_exists(file_path: str) -> str:
    """Validate path is in output/ and file exists. Returns resolved path."""
    resolved = validate_output_path(file_path)
    if not os.path.isfile(resolved):
        raise ToolError(f"File not found: '{file_path}'")
    return resolved


def validate_columns_exist(df, columns: list[str]) -> None:
    """Raise ToolError if any column name is not in the DataFrame."""
    missing = [c for c in columns if c not in df.columns]
    if missing:
        available = list(df.columns)
        raise ToolError(
            f"Column(s) not found: {missing}. "
            f"Available columns: {available}"
        )


def sanitize_query_string(query: str) -> str:
    """
    Block dangerous patterns in pandas .query() strings.
    Raises ToolError if dangerous patterns are detected.
    """
    if len(query) > 500:
        raise ToolError("Query string too long (max 500 characters).")

    dangerous_patterns = ["__", "import", "exec", "eval", "open", " os", " sys", "subprocess"]
    lower_query = query.lower()
    for pattern in dangerous_patterns:
        if pattern in lower_query:
            raise ToolError(
                f"Query string contains disallowed pattern '{pattern}'. "
                "Only simple column comparisons are permitted."
            )
    return query


def validate_row_count(df, warn_threshold: int = 1_000_000) -> dict | None:
    """Return a warning dict if the DataFrame is very large, else None."""
    if len(df) > warn_threshold:
        return {
            "warning": f"DataFrame has {len(df):,} rows (> {warn_threshold:,}). "
                       "Consider filtering or sampling first for better performance."
        }
    return None
