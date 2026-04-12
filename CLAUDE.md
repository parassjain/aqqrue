# Project Context

An AI-powered CSV workflow agent built with Streamlit + LangGraph. Users upload a CSV, describe operations in natural language, and the agent plans and executes data transformations, filters, aggregations, and visualizations in real time.

The agent uses a ReAct loop (LangGraph state machine) where the LLM binds to a set of CSV tools, inspects the file schema, creates a step-by-step plan, and executes each step — streaming typed events back to the Streamlit UI.

# Rules

- Always ask clarifying questions before starting a complex task
- Show your plan and steps before executing
- Keep updating the plan as you progress and learn more about the task
- Keep the original CSV file unchanged and work on a copy of it
- Keep separate `input/` (immutable originals) and `output/` (working copies + charts) folders
- Validate column names and file paths before every operation
- Never allow path traversal outside `output/`

# Project Structure

```
aqqrue/
├── app.py                  # Streamlit entry point
├── config.py               # LLM provider factory (Anthropic, Groq, Google, OpenAI, Ollama)
├── requirements.txt
├── .env / .env.example     # LLM_PROVIDER, MODEL_NAME, API keys
├── agent/
│   ├── graph.py            # LangGraph ReAct state graph
│   ├── loop.py             # Streaming wrapper; builds system prompt per turn; manages undo history
│   ├── tools.py            # LangChain @tool definitions (9 tools)
│   ├── planner.py          # Typed event dataclasses (PlanCreated, DataFrameResult, etc.)
│   └── prompts.py          # System prompt builder (injects CSV schema each turn)
├── tools/
│   ├── csv_io.py           # Load, save, schema inspection
│   ├── transform.py        # rename, cast, fill_nulls (7 strategies), regex extract, dedup, sort
│   ├── filter.py           # Row filtering (10 operators, AND logic)
│   ├── aggregate.py        # Group-by aggregation + describe_statistics
│   ├── charts.py           # Plotly charts (bar, line, scatter, histogram, pie, heatmap)
│   └── safety.py           # Path validation and query sanitization
├── input/                  # Original uploaded CSVs (never modified)
└── output/                 # Working CSVs (UUID-named), generated chart PNGs
```

# Tech Stack

- **UI**: Streamlit ≥ 1.35
- **Orchestration**: LangGraph ≥ 0.2 (ReAct pattern), LangChain ≥ 0.3
- **Data**: Pandas ≥ 2.1, NumPy ≥ 1.26
- **Visualization**: Plotly ≥ 5.20, Kaleido ≥ 0.2.1
- **LLM providers**: Anthropic (default, claude-sonnet-4-6), Groq, Google Gemini, OpenAI, Ollama
- **Python env**: conda `aqqrue`, Python 3.10

# Available Agent Tools

| Tool | What it does |
|---|---|
| `get_csv_schema` | Inspect column names, types, null counts, sample values |
| `filter_rows` | Filter rows by conditions (==, !=, >, <, >=, <=, contains, startswith, isnull, notnull) |
| `transform_columns` | rename, cast type, fill nulls, regex extract, drop duplicates, sort |
| `aggregate_data` | Group-by with sum/mean/median/min/max/count/std/first/last |
| `describe_statistics` | Read-only summary stats (count, mean, std, percentiles) |
| `generate_chart` | Bar, line, scatter, histogram, pie, heatmap via Plotly |
| `undo_last_operation` | Revert working CSV to previous state |
| `save_result` | Export final CSV to output/ with a custom filename |

# Key Design Decisions

- **Schema-aware prompting**: System message is rebuilt each turn with fresh CSV schema so the LLM always has current column info.
- **Streaming events**: The agent emits typed dataclass events (`PlanCreated`, `PlanStepCompleted`, `DataFrameResult`, `ChartGenerated`, `UndoPerformed`, `AgentError`, etc.) for real-time UI updates.
- **Undo stack**: Every CSV-writing tool appends to a file history list in session state; `undo_last_operation` pops and restores.
- **Multi-turn**: Full conversation history is kept in Streamlit session state, enabling follow-up instructions on the same file.
- **Safety**: All file paths are validated against `output/`; column names are checked before operations; query strings are sanitized.

# Environment Setup

```bash
conda activate aqqrue
cp .env.example .env   # fill in LLM_PROVIDER, MODEL_NAME, and the relevant API key
streamlit run app.py
```
