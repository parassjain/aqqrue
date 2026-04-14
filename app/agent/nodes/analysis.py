import json
import logging
import litellm

from app.config import get_litellm_kwargs
from app.agent.state import AgentState
from app.agent.tools.sandbox import run_in_sandbox

logger = logging.getLogger(__name__)

_SYSTEM = """You are an expert Python/pandas code generator for CSV analysis.

Write a single `transform(df)` function that computes the requested analysis and returns the result.

STRICT RULES:
1. The function MUST be named `transform`
2. Signature: `def transform(df: pd.DataFrame):`
3. You may ONLY use: pandas (as `pd`), numpy (as `np`), and Python builtins
4. NO imports — pd and np are pre-provided
5. NO file I/O, NO network, NO system calls
6. Return the computed result — a scalar, string, Series, or dict. Do NOT return a DataFrame.
7. Format numbers clearly (e.g., use f-strings to show currency, round floats to 2 decimal places)

OUTPUT FORMAT:
Return ONLY the raw Python function. No markdown, no explanation, no code fences.

EXAMPLE:
def transform(df: pd.DataFrame):
    total = df['Amount'].sum()
    return f"Total Amount: {total:,.2f}"
"""

_USER_TEMPLATE = """CSV Metadata:
- Columns: {columns}
- Data types: {dtypes}
- Row count: {rows}
- Sample rows (first 5):
{sample_rows}

User request: {user_message}

Generate the analysis function:"""


def analysis_node(state: AgentState) -> dict:
    """Run a read-only analysis on the full CSV and return the result as a message."""
    logger.info("[NODE: analysis] Running analysis for message: %r", state["user_message"])
    from app.services.session_manager import session_manager

    csv_mgr = session_manager.get_session(state["session_id"])
    if csv_mgr is None:
        return {"response_message": "Session not found.", "error": "Session not found"}

    csv_bytes = csv_mgr.get_current_csv_bytes()
    if csv_bytes is None:
        return {"response_message": "No CSV loaded.", "error": "No CSV loaded"}

    metadata = state["csv_metadata"]

    user_prompt = _USER_TEMPLATE.format(
        columns=metadata.get("columns", []),
        dtypes=metadata.get("dtypes", {}),
        rows=metadata.get("rows", 0),
        sample_rows=json.dumps(metadata.get("sample_rows", []), indent=2, default=str),
        user_message=state["user_message"],
    )

    response = litellm.completion(
        **get_litellm_kwargs(),
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )

    code = response.choices[0].message.content.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(l for l in lines if not l.strip().startswith("```"))

    result = run_in_sandbox(code, csv_bytes)

    if not result["success"]:
        logger.warning("[NODE: analysis] Sandbox execution failed: %s", result.get("error"))
        return {
            "response_message": f"Analysis failed: {result.get('error', 'Unknown error')}",
            "error": result.get("error"),
        }

    value = result.get("result_value", "")
    logger.info("[NODE: analysis] Analysis complete, result: %r", str(value)[:200])
    return {"response_message": str(value), "error": None}
