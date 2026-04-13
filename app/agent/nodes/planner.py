import json
import litellm

from app.config import get_litellm_kwargs
from app.agent.state import AgentState
from app.agent.prompts.planner import PLANNER_SYSTEM_PROMPT, PLANNER_USER_TEMPLATE


def planner_node(state: AgentState) -> dict:
    """Analyze user instruction + CSV metadata → produce a plan."""
    metadata = state["csv_metadata"]

    user_prompt = PLANNER_USER_TEMPLATE.format(
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
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    plan = response.choices[0].message.content.strip()
    return {"plan": plan}
