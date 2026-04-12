"""
CSV I/O utilities: load, save, and inspect CSV files.
"""

import os
import pandas as pd
from pathlib import Path

from tools.safety import validate_file_exists, validate_output_path, ToolError

_OUTPUT_DIR = str(Path(__file__).parent.parent / "output")


def load_csv(file_path: str) -> pd.DataFrame:
    """Load a CSV from a validated output/ path and return a DataFrame."""
    resolved = validate_file_exists(file_path)
    try:
        return pd.read_csv(resolved)
    except Exception as e:
        raise ToolError(f"Failed to read CSV '{file_path}': {e}")


def save_csv(df: pd.DataFrame, output_path: str) -> str:
    """
    Save DataFrame to output_path (must be within output/).
    Returns the resolved absolute path.
    """
    resolved = validate_output_path(output_path)
    os.makedirs(os.path.dirname(resolved), exist_ok=True)
    df.to_csv(resolved, index=False)
    return resolved


def get_schema(file_path: str) -> dict:
    """
    Return a rich schema description of the CSV for Claude to reason about.
    Includes column names, dtypes, row count, null counts, and 3 sample rows.
    """
    df = load_csv(file_path)
    null_counts = df.isnull().sum().to_dict()
    sample_rows = df.head(3).fillna("").to_dict(orient="records")

    columns_info = []
    for col in df.columns:
        columns_info.append({
            "name": col,
            "dtype": str(df[col].dtype),
            "null_count": int(null_counts[col]),
            "sample_values": df[col].dropna().head(3).tolist(),
        })

    return {
        "status": "success",
        "file_path": file_path,
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": columns_info,
        "sample_rows": sample_rows,
    }


def make_output_path(session_id: str, step: int, tool_name: str, original_name: str) -> str:
    """Build a versioned output file path."""
    base = os.path.splitext(os.path.basename(original_name))[0]
    filename = f"{session_id}_step{step}_{tool_name}_{base}.csv"
    return os.path.join(_OUTPUT_DIR, filename)
