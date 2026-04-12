"""
Row filtering tools.
"""

import pandas as pd

from tools.csv_io import load_csv, save_csv
from tools.safety import validate_columns_exist, sanitize_query_string, ToolError

_VALID_OPERATORS = {"==", "!=", ">", "<", ">=", "<=", "contains", "startswith", "isnull", "notnull"}


def filter_rows(file_path: str, conditions: list[dict], output_file: str) -> dict:
    """
    Filter rows based on one or more conditions.

    Each condition: {column, operator, value}
    Operators: ==, !=, >, <, >=, <=, contains, startswith, isnull, notnull

    Returns path to new CSV with filtered results.
    """
    df = load_csv(file_path)
    columns = [c["column"] for c in conditions]
    validate_columns_exist(df, columns)

    mask = pd.Series([True] * len(df), index=df.index)

    for cond in conditions:
        col = cond["column"]
        op = cond.get("operator", "==")
        val = cond.get("value")

        if op not in _VALID_OPERATORS:
            raise ToolError(f"Unknown operator '{op}'. Valid operators: {sorted(_VALID_OPERATORS)}")

        if op == "==":
            mask &= df[col] == val
        elif op == "!=":
            mask &= df[col] != val
        elif op == ">":
            mask &= df[col] > val
        elif op == "<":
            mask &= df[col] < val
        elif op == ">=":
            mask &= df[col] >= val
        elif op == "<=":
            mask &= df[col] <= val
        elif op == "contains":
            mask &= df[col].astype(str).str.contains(str(val), case=False, na=False)
        elif op == "startswith":
            mask &= df[col].astype(str).str.startswith(str(val), na=False)
        elif op == "isnull":
            mask &= df[col].isnull()
        elif op == "notnull":
            mask &= df[col].notnull()

    result = df[mask].reset_index(drop=True)
    saved_path = save_csv(result, output_file)

    return {
        "status": "success",
        "message": f"Filtered from {len(df):,} rows to {len(result):,} rows using {len(conditions)} condition(s).",
        "output_file": saved_path,
        "row_count": len(result),
        "columns": list(result.columns),
    }
