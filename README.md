# CSV AI Agent

An AI-powered CSV workflow agent. Upload a CSV, describe what you want in plain English, and the agent plans and executes data transformations, filters, aggregations, and statistics in real time.

Built with Streamlit + LangGraph (ReAct pattern) and supports multiple LLM providers.

---

## Prerequisites

- Python 3.10
- [conda](https://docs.conda.io/en/latest/) (recommended) or any Python 3.10 virtual environment
- An API key for at least one supported LLM provider (Anthropic, OpenAI, Groq, Google, or a running Ollama instance)

---

## Setup

### 1. Clone the repo

```bash
git clone <repo-url>
cd aqqrue
```

### 2. Create and activate the conda environment

```bash
conda create -n aqqrue python=3.10 -y
conda activate aqqrue
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your LLM provider

```bash
cp .env.example .env
```

Open `.env` and set your provider and API key. The default is Anthropic:

```env
LLM_PROVIDER=anthropic
MODEL_NAME=claude-sonnet-4-6
ANTHROPIC_API_KEY=your_key_here
```

Supported providers:

| Provider | `LLM_PROVIDER` | `MODEL_NAME` example | Key env var |
|---|---|---|---|
| Anthropic (default) | `anthropic` | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| Groq | `groq` | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| Google Gemini | `google` | `gemini-2.0-flash` | `GOOGLE_API_KEY` |
| OpenAI | `openai` | `gpt-4o` | `OPENAI_API_KEY` |
| Ollama (local) | `ollama` | `llama3.2` | `OLLAMA_BASE_URL` (default: `http://localhost:11434`) |

### 5. Run the app

```bash
streamlit run app.py
```

The app opens at [http://localhost:8501](http://localhost:8501).

---

## Usage

1. **Upload a CSV** using the sidebar file picker.
2. The agent displays a live column preview (name, type, null count).
3. **Type a request** in the chat input and press Enter.
4. The agent calls `get_csv_schema`, creates a plan, executes it step by step, and streams results back — including live data previews and download buttons.
5. Use **follow-up messages** to refine or continue working on the same file.
6. Click **Clear session** in the sidebar to start over with a new file.

> Original uploaded files are never modified. All transformations are written to `output/` as separate working copies.

---

## Sample Prompts

### Exploring the data

```
What columns does this file have and what are their types?
```
```
How many rows are there and how many nulls are in each column?
```
```
Show me the first 20 rows where the "status" column is "pending"
```
```
What is the average, min, and max of the "amount" column?
```

### Filtering

```
Show me all rows where revenue is greater than 10000
```
```
Filter to only rows where country is "US" and category is "Electronics"
```
```
Find all rows where the email column is empty
```

### Transforming

```
Rename the column "dt" to "date" and "amt" to "amount"
```
```
Cast the "created_at" column to datetime
```
```
Fill null values in the "region" column with "Unknown"
```
```
Drop duplicate rows based on the "transaction_id" column
```
```
Sort the file by "date" descending
```
```
Extract the domain from the "email" column into a new column called "domain"
```

### Aggregating

```
Group by "category" and show the total and average revenue for each
```
```
Group by "month" and "region" and count the number of transactions
```
```
What are the top 5 categories by total sales?
```

### Multi-step workflows

```
Filter to rows from 2024, then group by "product" and sum the "quantity" sold
```
```
Remove rows where "price" is null, cast "price" to float, then sort by price descending
```
```
Fill nulls in "city" with "Unknown", drop duplicate customer IDs, and save as clean_customers.csv
```

### Undo and save

```
Undo the last operation
```
```
Save the result as quarterly_summary.csv
```
