"""
Chart generation using Plotly. Saves figures as JSON for Streamlit rendering.
"""

import os
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from tools.csv_io import load_csv
from tools.safety import validate_columns_exist, validate_output_path, ToolError

_OUTPUT_DIR = str(Path(__file__).parent.parent / "output")
_VALID_CHART_TYPES = {"bar", "line", "scatter", "histogram", "pie", "heatmap"}


def generate_chart(
    file_path: str,
    chart_type: str,
    x_column: str,
    output_file: str,
    y_column: str | None = None,
    title: str | None = None,
    color_column: str | None = None,
    top_n: int | None = None,
) -> dict:
    """
    Generate an interactive Plotly chart from CSV data.
    Saves the figure as a JSON file and returns the path.

    chart_type: bar, line, scatter, histogram, pie, heatmap
    """
    if chart_type not in _VALID_CHART_TYPES:
        raise ToolError(f"Unknown chart type '{chart_type}'. Valid: {sorted(_VALID_CHART_TYPES)}")

    df = load_csv(file_path)
    cols_to_check = [c for c in [x_column, y_column, color_column] if c]
    validate_columns_exist(df, cols_to_check)

    if top_n and y_column:
        df = df.nlargest(top_n, y_column)

    chart_title = title or f"{chart_type.title()} Chart"
    fig = None

    if chart_type == "bar":
        if not y_column:
            raise ToolError("bar chart requires y_column")
        fig = px.bar(df, x=x_column, y=y_column, color=color_column, title=chart_title)

    elif chart_type == "line":
        if not y_column:
            raise ToolError("line chart requires y_column")
        fig = px.line(df, x=x_column, y=y_column, color=color_column, title=chart_title)

    elif chart_type == "scatter":
        if not y_column:
            raise ToolError("scatter chart requires y_column")
        fig = px.scatter(df, x=x_column, y=y_column, color=color_column, title=chart_title)

    elif chart_type == "histogram":
        fig = px.histogram(df, x=x_column, color=color_column, title=chart_title)

    elif chart_type == "pie":
        if not y_column:
            raise ToolError("pie chart requires y_column (values column)")
        fig = px.pie(df, names=x_column, values=y_column, title=chart_title)

    elif chart_type == "heatmap":
        numeric_df = df.select_dtypes(include="number")
        if numeric_df.empty:
            raise ToolError("heatmap requires numeric columns; none found in the CSV.")
        corr = numeric_df.corr().round(3)
        fig = px.imshow(
            corr,
            text_auto=True,
            title=chart_title,
            color_continuous_scale="RdBu_r",
            zmin=-1,
            zmax=1,
        )

    # Save as JSON for Streamlit to load
    charts_dir = os.path.join(_OUTPUT_DIR, "charts")
    os.makedirs(charts_dir, exist_ok=True)

    resolved = validate_output_path(output_file)
    os.makedirs(os.path.dirname(resolved), exist_ok=True)

    fig_json = fig.to_json()
    with open(resolved, "w") as f:
        f.write(fig_json)

    return {
        "status": "success",
        "message": f"Generated {chart_type} chart: '{chart_title}'",
        "chart_file": resolved,
        "chart_type": chart_type,
        "title": chart_title,
    }
