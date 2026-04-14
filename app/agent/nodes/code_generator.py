import json
import litellm

from app.config import get_litellm_kwargs
from app.agent.state import AgentState
from app.agent.prompts.code_generator import (
    CODE_GENERATOR_SYSTEM_PROMPT,
    CODE_GENERATOR_USER_TEMPLATE,
    CODE_GENERATOR_RETRY_CONTEXT,
)


def code_generator_node(state: AgentState) -> dict:
    """Generate pandas transform code based on the plan."""
    metadata = state["csv_metadata"]

    # Build error context for retries
    error_context = ""
    if state.get("last_error") and state.get("generated_code"):
        error_context = CODE_GENERATOR_RETRY_CONTEXT.format(
            error=state["last_error"],
            previous_code=state["generated_code"],
        )

    user_prompt = CODE_GENERATOR_USER_TEMPLATE.format(
        columns=metadata.get("columns", []),
        dtypes=metadata.get("dtypes", {}),
        rows=metadata.get("rows", 0),
        sample_rows=json.dumps(metadata.get("sample_rows", []), indent=2, default=str),
        plan=state["plan"],
        error_context=error_context,
    )

    response = litellm.completion(
        **get_litellm_kwargs(),
        messages=[
            {"role": "system", "content": CODE_GENERATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )

    code = response.choices[0].message.content.strip()
    # Strip markdown code fences if the LLM adds them despite instructions
    if code.startswith("```"):
        lines = code.split("\n")
        # Remove first and last fence lines
        lines = [l for l in lines if not l.strip().startswith("```")]
        code = "\n".join(lines)

    return {
        "generated_code": code,
    }
