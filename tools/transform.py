"""
Column transformation tools: rename, cast, fill nulls, drop duplicates, sort.
"""

import pandas as pd

from tools.csv_io import load_csv, save_csv
from tools.safety import validate_columns_exist, ToolError

_VALID_TYPES = {"int", "float", "str", "bool", "datetime"}
_VALID_FILL_STRATEGIES = {"mean", "median", "mode", "ffill", "bfill", "value"}


def transform_columns(file_path: str, operations: list[dict], output_file: str) -> dict:
    """
    Apply a sequence of column-level transformations.

    Each operation: {operation, column, params}
    Supported operations:
      - rename:           params = {new_name: str}
      - cast_type:        params = {target_type: "int|float|str|bool|datetime"}
      - fill_nulls:       params = {strategy: "mean|median|mode|ffill|bfill|value", value: any}
      - drop_duplicates:  params = {subset: [col, ...]} (optional)
      - sort:             params = {column: str, ascending: bool}
    """
    df = load_csv(file_path)
    applied = []

    for op in operations:
        operation = op.get("operation")
        col = op.get("column")
        params = op.get("params", {})

        if operation == "rename":
            if col not in df.columns:
                raise ToolError(f"Column '{col}' not found for rename. Available: {list(df.columns)}")
            new_name = params.get("new_name")
            if not new_name:
                raise ToolError("rename operation requires params.new_name")
            df = df.rename(columns={col: new_name})
            applied.append(f"Renamed '{col}' → '{new_name}'")

        elif operation == "cast_type":
            validate_columns_exist(df, [col])
            target = params.get("target_type")
            if target not in _VALID_TYPES:
                raise ToolError(f"Invalid target_type '{target}'. Valid: {_VALID_TYPES}")
            try:
                if target == "datetime":
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                elif target == "int":
                    df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
                elif target == "float":
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                elif target == "bool":
                    df[col] = df[col].astype(bool)
                else:
                    df[col] = df[col].astype(str)
            except Exception as e:
                raise ToolError(f"Failed to cast '{col}' to {target}: {e}")
            applied.append(f"Cast '{col}' to {target}")

        elif operation == "fill_nulls":
            validate_columns_exist(df, [col])
            strategy = params.get("strategy", "value")
            if strategy not in _VALID_FILL_STRATEGIES:
                raise ToolError(f"Invalid strategy '{strategy}'. Valid: {_VALID_FILL_STRATEGIES}")
            null_before = df[col].isnull().sum()
            if strategy == "mean":
                df[col] = df[col].fillna(df[col].mean())
            elif strategy == "median":
                df[col] = df[col].fillna(df[col].median())
            elif strategy == "mode":
                mode_val = df[col].mode()
                if len(mode_val) > 0:
                    df[col] = df[col].fillna(mode_val[0])
            elif strategy == "ffill":
                df[col] = df[col].ffill()
            elif strategy == "bfill":
                df[col] = df[col].bfill()
            elif strategy == "value":
                fill_val = params.get("value")
                if fill_val is None:
                    raise ToolError("fill_nulls with strategy='value' requires params.value")
                df[col] = df[col].fillna(fill_val)
            applied.append(f"Filled {null_before} nulls in '{col}' using {strategy}")

        elif operation == "drop_duplicates":
            before = len(df)
            subset = params.get("subset")
            if subset:
                validate_columns_exist(df, subset)
            df = df.drop_duplicates(subset=subset).reset_index(drop=True)
            applied.append(f"Dropped {before - len(df)} duplicate rows")

        elif operation == "sort":
            sort_col = params.get("column", col)
            if sort_col not in df.columns:
                raise ToolError(f"Sort column '{sort_col}' not found.")
            ascending = params.get("ascending", True)
            df = df.sort_values(by=sort_col, ascending=ascending).reset_index(drop=True)
            direction = "ascending" if ascending else "descending"
            applied.append(f"Sorted by '{sort_col}' ({direction})")

        else:
            raise ToolError(
                f"Unknown operation '{operation}'. "
                "Valid: rename, cast_type, fill_nulls, drop_duplicates, sort"
            )

    saved_path = save_csv(df, output_file)
    return {
        "status": "success",
        "message": f"Applied {len(applied)} transformation(s): " + "; ".join(applied),
        "output_file": saved_path,
        "row_count": len(df),
        "columns": list(df.columns),
    }
