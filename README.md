# Aqqrue — Agentic CSV Processor for Accountants

Aqqrue is an AI-powered tool that lets accountants transform CSV/ledger files using plain English instructions. Upload a CSV, describe what you want to change, and the agent writes, validates, and executes the code for you — all in a secure sandbox.

Built with **LangGraph** for agentic orchestration, **LiteLLM** for model-agnostic LLM support, **FastAPI** for the backend, and **Streamlit** for the chat UI.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Agent Flow](#agent-flow)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Running the App](#running-the-app)
  - [Running with Docker](#running-with-docker)
- [Usage](#usage)
  - [Example Session](#example-session)
  - [Supported Operations](#supported-operations)
- [API Reference](#api-reference)
- [How It Works — Deep Dive](#how-it-works--deep-dive)
  - [1. Planner](#1-planner)
  - [2. Code Generator](#2-code-generator)
  - [3. Validator](#3-validator)
  - [4. Preview](#4-preview)
  - [5. Executor](#5-executor)
  - [6. Auditor](#6-auditor)
- [Security Model](#security-model)
- [Version Control & Undo](#version-control--undo)
- [Supported LLM Providers](#supported-llm-providers)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Natural language CSV editing** — Describe changes in plain English; the agent writes and executes pandas code.
- **Dynamic tool generation** — The agent generates Python functions on-the-fly for each operation. No pre-built tools needed.
- **Accounting-domain awareness** — Understands ledger terms (narration, voucher, folio, debit/credit, GST, TDS, aging, trial balance, journal entries).
- **Secure Docker sandbox** — Generated code runs in an isolated container with no network access and memory limits.
- **AST-based code validation** — Blocks dangerous imports (`os`, `subprocess`, etc.) and unsafe builtins (`exec`, `eval`, `open`) before code ever runs.
- **LLM semantic validation** — A second LLM pass verifies the generated code matches the user's intent and follows accounting rules.
- **Version chain with undo** — Every operation creates a new CSV version. Undo reverts to the previous state instantly.
- **Multi-turn chat** — Each instruction operates on the latest CSV version. Turn 2 gets the output of Turn 1.
- **Preview before execution** — See a sample diff (before/after) before the full CSV is modified.
- **Audit trail** — Every operation is logged with the instruction, generated code, timestamp, and row counts.
- **Model-agnostic** — Swap LLM providers via a single `.env` variable (OpenAI, Anthropic, Google, open-source models via Ollama).

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────────────┐
│  Streamlit   │────▶│   FastAPI    │────▶│     LangGraph Agent      │
│  Chat UI     │◀────│   Backend    │◀────│                          │
└──────────────┘     └──────────────┘     │  Planner                 │
                                          │  ↓                       │
                                          │  Code Generator          │
                                          │  ↓                       │
                                          │  Validator (AST + LLM)   │
                                          │  ↓                       │
                                          │  Preview ──▶ Executor    │
                                          │              ↓           │
                                          │           Docker Sandbox │
                                          │              ↓           │
                                          │           Auditor        │
                                          └──────────────────────────┘
                                                       ↓
                                          ┌──────────────────────────┐
                                          │  Filesystem (CSV versions│
                                          │  + audit log)            │
                                          └──────────────────────────┘
```

---

## Agent Flow

```
START → Planner → Code Generator → Validator
                        ↑                 │
                        │            ┌────┴────┐
                        │          valid?    invalid?
                        │            │         │
                        │            ▼         │ (retry, max 3)
                        │         Preview ─────┘
                        │            │
                        │            ▼
                        │         Executor
                        │            │
                        │       ┌────┴────┐
                        │     success?   error?
                        │       │         │ (retry, max 3)
                        │       ▼         │
                        │     Auditor ────┘
                        │       │
                        └───────┘
                              │
                              ▼
                             END → Response to user
```

- **Max 3 retries** across validation failures and execution errors.
- On retry, the Code Generator receives the previous error message as context.
- After 3 failures, the agent returns a clear error message to the user.

---

## Project Structure

```
aqqrue/
├── .env                          # LLM config (MODEL_NAME, API_KEY)
├── .env.example                  # Template for .env
├── .gitignore
├── requirements.txt              # Python dependencies
├── Dockerfile                    # FastAPI app container
├── Dockerfile.sandbox            # Isolated Python+pandas execution sandbox
├── docker-compose.yml            # Orchestrates app + sandbox image build
│
├── app/
│   ├── __init__.py
│   ├── main.py                   # FastAPI entry point
│   ├── config.py                 # Loads .env, provides LiteLLM kwargs
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py             # REST endpoints (create, upload, chat, undo, download, history)
│   │   └── schemas.py            # Pydantic request/response models
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── graph.py              # LangGraph graph definition — the core agent loop
│   │   ├── state.py              # AgentState TypedDict — all data flowing through the graph
│   │   │
│   │   ├── nodes/
│   │   │   ├── __init__.py
│   │   │   ├── planner.py        # Understands user intent with accounting domain knowledge
│   │   │   ├── code_generator.py # Generates pandas transform() functions
│   │   │   ├── validator.py      # AST static analysis + LLM semantic validation
│   │   │   ├── preview.py        # Runs code on sample rows, produces before/after diff
│   │   │   ├── executor.py       # Runs code on full CSV in Docker sandbox
│   │   │   └── auditor.py        # Logs operation, bumps CSV version
│   │   │
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   └── sandbox.py        # Docker sandbox client (send code + CSV, get result)
│   │   │
│   │   └── prompts/
│   │       ├── __init__.py
│   │       ├── planner.py        # System prompt with accounting domain knowledge
│   │       ├── code_generator.py # Prompt for constrained code generation
│   │       └── validator.py      # Prompt for semantic code validation
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── csv_manager.py        # CSV loading, version chain, undo, metadata extraction
│   │   └── session_manager.py    # In-memory session lifecycle
│   │
│   └── sandbox/
│       └── runner.py             # Script executed inside Docker sandbox container
│
├── streamlit_app/
│   ├── app.py                    # Streamlit chat UI with CSV preview
│   ├── api_client.py             # Wrapper around FastAPI endpoints
│   └── components/               # UI components (extensible)
│
├── data/
│   └── sessions/                 # CSV versions stored here per session (gitignored)
│
└── tests/
    └── __init__.py
```

---

## Getting Started

### Prerequisites

- **Python 3.9+**
- **Docker** (for the secure code execution sandbox)
- An API key from a supported LLM provider (OpenAI, Anthropic, Google, etc.) — or a local model via Ollama

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/aqqrue.git
cd aqqrue

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Copy the example env file and fill in your API key:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# LLM provider — change MODEL_NAME to switch providers
MODEL_NAME=gpt-4o
API_KEY=sk-your-openai-api-key-here

# For Anthropic:
# MODEL_NAME=claude-sonnet-4-20250514
# API_KEY=sk-ant-your-key-here

# For Google Gemini:
# MODEL_NAME=gemini/gemini-2.0-flash
# API_KEY=your-google-api-key

# For local models via Ollama:
# MODEL_NAME=ollama/llama3
# API_BASE=http://localhost:11434

# Sandbox settings
SANDBOX_TIMEOUT=30
SANDBOX_MEMORY_LIMIT=512m

# Session storage
SESSION_DATA_DIR=data/sessions
MAX_RETRIES=3
```

### Running the App

**Step 1: Build the sandbox Docker image**

```bash
docker build -f Dockerfile.sandbox -t aqqrue-sandbox .
```

**Step 2: Start the FastAPI backend**

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Step 3: Start the Streamlit frontend** (in a separate terminal)

```bash
streamlit run streamlit_app/app.py
```

The Streamlit UI will open at `http://localhost:8501`. The API is available at `http://localhost:8000`.

### Running with Docker

```bash
# Build and start everything
docker compose up --build

# Build just the sandbox image (required for code execution)
docker compose build sandbox
```

---

## Usage

### Example Session

1. **Upload** a CSV file (e.g., `ledger.csv`) via the sidebar.
2. **Type an instruction** in the chat:

```
"Add a GST column at 18% of the Amount"
```

3. The agent:
   - Plans the operation
   - Generates a `transform()` function
   - Validates it (AST check + LLM review)
   - Shows you a preview (first 5 rows before/after)
   - Executes on the full CSV
   - Saves as a new version

4. **Next instruction** operates on the updated CSV:

```
"Remove all rows where GST is less than 500"
```

5. **Undo** if something went wrong — reverts to the previous version.
6. **Download** the final CSV when done.

### Supported Operations

The agent can handle a wide range of operations. Here are examples organized by complexity:

#### Simple Operations
| Instruction | What It Does |
|---|---|
| "Rename 'Amt' to 'Amount'" | Renames a column |
| "Sort by date descending" | Sorts rows |
| "Remove duplicate rows" | Deduplicates |
| "Delete the 'Notes' column" | Drops a column |
| "Show only March 2026 transactions" | Filters rows |
| "Fix date format to DD-MM-YYYY" | Reformats dates |
| "Replace 'Misc' with 'Miscellaneous'" | Find & replace |

#### Accounting Operations
| Instruction | What It Does |
|---|---|
| "Add a running balance column" | Cumulative sum |
| "Split Amount into Base + 18% GST" | Tax calculations |
| "Create AR aging buckets (0-30, 31-60, 61-90, 90+)" | Aging analysis |
| "Flag duplicate entries by amount + date" | Duplicate detection |
| "Verify voucher numbers are sequential" | Gap analysis |
| "Calculate straight-line depreciation over 5 years" | Asset depreciation |
| "Generate a trial balance summary" | Debit/credit totals per account |
| "Create reversal entries for all items dated 31-Mar" | Journal reversals |

#### Complex Operations
| Instruction | What It Does |
|---|---|
| "Classify transactions into Rent, Salary, Utilities based on narration" | AI-powered categorization |
| "Create debit/credit journal entries for these expenses" | Double-entry generation |
| "Reclassify all Suspense Account entries based on narration" | Smart reclassification |

---

## API Reference

All endpoints are prefixed with `/api`.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/session/create` | Create a new session. Returns `session_id`. |
| `POST` | `/api/session/{id}/upload` | Upload a CSV file. Returns metadata (columns, dtypes, sample rows). |
| `POST` | `/api/session/{id}/chat` | Send a natural language instruction. Returns response + preview + updated metadata. |
| `POST` | `/api/session/{id}/undo` | Undo the last operation. Reverts to previous CSV version. |
| `GET` | `/api/session/{id}/download` | Download the current CSV version. |
| `GET` | `/api/session/{id}/history` | Get version history and audit log. |
| `GET` | `/health` | Health check. |

### Example: Full API Flow

```bash
# 1. Create session
curl -X POST http://localhost:8000/api/session/create
# → {"session_id": "a1b2c3d4e5f6"}

# 2. Upload CSV
curl -X POST http://localhost:8000/api/session/a1b2c3d4e5f6/upload \
  -F "file=@ledger.csv"
# → {"session_id": "...", "metadata": {"rows": 150, "columns": ["Date", "Amount", ...], ...}}

# 3. Send instruction
curl -X POST http://localhost:8000/api/session/a1b2c3d4e5f6/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Add a GST column at 18% of Amount"}'
# → {"response": "Done. Columns added: GST. Output: 150 rows, 5 columns. Version: v1", ...}

# 4. Undo
curl -X POST http://localhost:8000/api/session/a1b2c3d4e5f6/undo
# → {"success": true, "message": "Reverted to version 0", ...}

# 5. Download
curl http://localhost:8000/api/session/a1b2c3d4e5f6/download -o output.csv
```

---

## How It Works — Deep Dive

### 1. Planner

**File:** `app/agent/nodes/planner.py`

The Planner receives the user's natural language instruction along with CSV metadata (column names, data types, sample rows, null counts) — but **never the full CSV** (too large for LLM context).

It produces a structured plan: what operation to perform, which columns are involved, new columns to create, validation rules to enforce, and expected effect on row count.

The Planner's system prompt includes extensive accounting domain knowledge — it understands terms like narration, voucher, folio, debit/credit, GST, TDS, trial balance, aging buckets, and journal entries.

### 2. Code Generator

**File:** `app/agent/nodes/code_generator.py`

Takes the Planner's output and generates a standalone Python function:

```python
def transform(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['GST'] = df['Amount'] * 0.18
    return df
```

Strict constraints enforced via the prompt:
- Must be named `transform`, accept and return a DataFrame
- Only `pandas` and `numpy` allowed (pre-injected, no imports needed)
- No file I/O, network access, or system calls
- Must handle edge cases (NaN, type mismatches)
- Must work on a copy (`df = df.copy()`)

On **retry**, the Code Generator receives the previous error message and its failed code as context.

### 3. Validator

**File:** `app/agent/nodes/validator.py`

Two-layer validation:

**Layer 1 — AST Static Analysis (no LLM, instant):**
- Parses the code's Abstract Syntax Tree
- Blocks dangerous imports: `os`, `sys`, `subprocess`, `shutil`, `socket`, `http`, `urllib`, `requests`, `pickle`, etc.
- Blocks unsafe builtins: `open()`, `exec()`, `eval()`, `compile()`, `__import__()`, `globals()`, `breakpoint()`
- Verifies a `transform` function exists
- Warns if `transform()` has no return statement

**Layer 2 — LLM Semantic Validation:**
- Checks if the code correctly implements the plan
- Verifies it will work with the actual column names and data types
- Checks for edge case handling (nulls, type mismatches)
- Validates accounting rules (e.g., debit = credit balance)

### 4. Preview

**File:** `app/agent/nodes/preview.py`

Runs the validated code on the **first 10 rows** of the CSV inside the Docker sandbox. Produces:
- Before/after sample (first 5 rows)
- Columns added/removed
- Row count change
- Summary description

This lets the user see what will happen before the full CSV is modified.

### 5. Executor

**File:** `app/agent/nodes/executor.py`

Runs the code on the **full CSV** inside the Docker sandbox. The sandbox:
- Is a minimal Python 3.12 container with only pandas and numpy
- Has **no network access** (`network_disabled=True`)
- Has a **memory limit** (default 512MB)
- Runs as a non-root user
- Communicates via mounted files (input CSV + code in, output CSV out)

### 6. Auditor

**File:** `app/agent/nodes/auditor.py`

After successful execution:
- Saves the new CSV as the next version in the version chain
- Logs the operation: instruction, generated code, timestamp, row counts before/after
- Updates CSV metadata for the next turn
- Constructs the response message sent back to the user

---

## Security Model

| Layer | Protection |
|---|---|
| **AST Validator** | Blocks dangerous imports and unsafe builtins at the code level before execution |
| **Docker Sandbox** | Isolated container with no network, memory limits, non-root user, 30s timeout |
| **File Mounting** | Input CSV and code are mounted read-only; only the output file is writable |
| **No Arbitrary Exec** | The sandbox only executes a `transform()` function — not arbitrary scripts |
| **LLM Semantic Check** | Second-pass validation that the code matches intent (catches subtle logic errors) |

---

## Version Control & Undo

Every operation creates a new CSV version stored on disk:

```
data/sessions/{session_id}/
├── v0.csv    ← Original upload
├── v1.csv    ← After "Add GST column"
├── v2.csv    ← After "Remove rows where GST < 500"
└── ...
```

- **Undo** removes the latest version and reverts to the previous one.
- **History** endpoint shows all versions with their operations and timestamps.
- **Download** always returns the latest version.

---

## Supported LLM Providers

Powered by [LiteLLM](https://github.com/BerriAI/litellm), Aqqrue supports 100+ LLM providers via a single `MODEL_NAME` env variable:

| Provider | MODEL_NAME Example | Notes |
|---|---|---|
| OpenAI | `gpt-4o`, `gpt-4.1`, `gpt-4o-mini` | Best overall performance |
| Anthropic | `claude-sonnet-4-20250514`, `claude-opus-4-20250514` | Excellent code generation |
| Google | `gemini/gemini-2.0-flash` | Fast and cost-effective |
| Ollama (local) | `ollama/llama3`, `ollama/codellama` | Free, runs locally. Set `API_BASE=http://localhost:11434` |
| Azure OpenAI | `azure/gpt-4o` | Enterprise deployments |
| AWS Bedrock | `bedrock/anthropic.claude-3` | AWS-native |

---

## Roadmap

- [x] Single CSV upload + natural language editing
- [x] Dynamic code generation (self-tooling agent)
- [x] AST + LLM dual validation
- [x] Docker sandbox execution
- [x] Version chain with undo
- [x] Audit trail
- [x] Streamlit chat UI
- [ ] **Multi-CSV support** — Upload a second CSV for lookups, reconciliation, VLOOKUP-style joins
- [ ] **Human-in-the-loop confirmation** — Require explicit approval for destructive operations (delete rows, overwrite columns)
- [ ] **Persistent sessions** — PostgreSQL-backed session storage (swap `MemorySaver` → `PostgresSaver`)
- [ ] **Accounting validation hooks** — Post-execution checks: debit=credit balance, sequential numbering, period locking
- [ ] **Export to Excel** — Download as `.xlsx` with formatting
- [ ] **Batch operations** — Process multiple instructions in one go
- [ ] **Template library** — Save and reuse common operations (e.g., "Monthly GST reconciliation")

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/multi-csv-support`
3. Make your changes
4. Run tests: `python -m pytest tests/`
5. Submit a pull request

---

## License

MIT
