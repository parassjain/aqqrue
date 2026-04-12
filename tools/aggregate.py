"""
Aggregation and summary statistics tools.
"""

import pandas as pd

from tools.csv_io import load_csv, save_csv
from tools.safety import validate_columns_exist, ToolError

_VALID_AGG_FUNCS = {"sum", "mean", "median", "min", "max", "count", "std", "first", "last"}


def group_by_aggregate(
    file_path: str,
    group_by_columns: list[str],
    aggregations: dict,
    output_file: str,
) -> dict:
    """
    Group by columns and aggregate.

    aggregations: {column_name: ["sum", "mean", ...]}
    Returns path to aggregated CSV.
    """
    df = load_csv(file_path)
    validate_columns_exist(df, group_by_columns)
    validate_columns_exist(df, list(aggregations.keys()))

    # Validate agg functions
    for col, funcs in aggregations.items():
        invalid = [f for f in funcs if f not in _VALID_AGG_FUNCS]
        if invalid:
            raise ToolError(
                f"Invalid aggregation function(s) {invalid} for column '{col}'. "
                f"Valid: {sorted(_VALID_AGG_FUNCS)}"
            )

    result = df.groupby(group_by_columns).agg(aggregations)
    result.columns = ["_".join(c).strip("_") if isinstance(c, tuple) else c for c in result.columns]
    result = result.reset_index()

    saved_path = save_csv(result, output_file)
    return {
        "status": "success",
        "message": (
            f"Grouped by {group_by_columns} with {sum(len(v) for v in aggregations.values())} "
            f"aggregation(s). Result: {len(result):,} rows."
        ),
        "output_file": saved_path,
        "row_count": len(result),
        "columns": list(result.columns),
    }


def describe_statistics(file_path: str, columns: list[str] | None = None) -> dict:
    """
    Return summary statistics for specified columns (read-only, no file created).
    Defaults to all numeric columns if columns is None.
    """
    df = load_csv(file_path)
    if columns:
        validate_columns_exist(df, columns)
        subset = df[columns]
    else:
        subset = df.select_dtypes(include="number")

    if subset.empty or len(subset.columns) == 0:
        return {
            "status": "success",
            "message": "No numeric columns found for statistics.",
            "statistics": {},
        }

    stats = subset.describe().round(4).to_dict()
    return {
        "status": "success",
        "message": f"Statistics computed for {len(subset.columns)} column(s).",
        "statistics": stats,
        "row_count": len(df),
    }


def value_counts(file_path: str, column: str, top_n: int = 20) -> dict:
    """Return value counts for a categorical column (read-only)."""
    df = load_csv(file_path)
    validate_columns_exist(df, [column])
    counts = df[column].value_counts().head(top_n)
    return {
        "status": "success",
        "message": f"Top {min(top_n, len(counts))} value counts for '{column}'.",
        "value_counts": counts.to_dict(),
        "total_unique": int(df[column].nunique()),
    }
