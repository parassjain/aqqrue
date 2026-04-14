import json
import litellm

from app.config import get_litellm_kwargs
from app.agent.state import AgentState

_SYSTEM = """You are a classifier for a CSV processing assistant.

Given a user message and CSV metadata, decide if the user wants:
- "question": they are asking about the data structure/content (describe, explain, what columns, what is this file, show me, etc.) — answerable from metadata alone, no changes to the CSV
- "analysis": they want a computed result from the full data (sum, total, count, average, min, max, group by, distribution, etc.) — needs code to run on full CSV, no changes to the CSV
- "operation": they want to modify, filter, add, remove, transform, or export the CSV

Also, if the intent is "question", provide a direct, helpful answer using the metadata provided.

Respond with JSON only:
{"intent": "question" | "analysis" | "operation", "answer": "<answer if question, else empty string>"}"""

_USER_TEMPLATE = """CSV Metadata:
- Columns: {columns}
- Data types: {dtypes}
- Row count: {rows}
- Null counts: {null_counts}
- Sample rows (first 5):
{sample_rows}

User message: {user_message}"""


def router_node(state: AgentState) -> dict:
    """Classify intent: answer questions directly, route operations to planner."""
    metadata = state["csv_metadata"]

    user_prompt = _USER_TEMPLATE.format(
        columns=metadata.get("columns", []),
        dtypes=metadata.get("dtypes", {}),
        rows=metadata.get("rows", 0),
        null_counts=metadata.get("null_counts", {}),
        sample_rows=json.dumps(metadata.get("sample_rows", []), indent=2, default=str),
        user_message=state["user_message"],
    )

    response = litellm.completion(
        **get_litellm_kwargs(),
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Default to operation if we can't parse
        result = {"intent": "operation", "answer": ""}

    intent = result.get("intent", "operation")
    answer = result.get("answer", "")

    if intent == "question":
        return {"intent": "question", "response_message": answer}

    if intent == "analysis":
        return {"intent": "analysis"}

    return {"intent": "operation"}
