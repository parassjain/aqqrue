import ast
import json
import litellm

from app.config import get_litellm_kwargs
from app.agent.state import AgentState
from app.agent.prompts.validator import VALIDATOR_SYSTEM_PROMPT, VALIDATOR_USER_TEMPLATE

# Imports that are blocked in generated code
BLOCKED_MODULES = {
    "os",
    "sys",
    "subprocess",
    "shutil",
    "pathlib",
    "socket",
    "http",
    "urllib",
    "requests",
    "ftplib",
    "smtplib",
    "ctypes",
    "importlib",
    "code",
    "codeop",
    "compile",
    "eval",
    "exec",
    "pickle",
    "shelve",
    "marshal",
    "tempfile",
    "glob",
    "fnmatch",
    "signal",
    "threading",
    "multiprocessing",
    "asyncio",
    "webbrowser",
}

BLOCKED_BUILTINS = {
    "open",
    "exec",
    "eval",
    "compile",
    "__import__",
    "globals",
    "locals",
    "breakpoint",
}


def _static_validate(code: str) -> tuple[bool, list[str], list[str]]:
    """AST-based static analysis. Returns (valid, errors, warnings)."""
    errors = []
    warnings = []

    # Parse AST
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, [f"Syntax error: {e}"], []

    # Check for transform function
    func_names = [
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    ]
    if "transform" not in func_names:
        errors.append("No 'transform' function defined")

    # Check for blocked imports
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules_to_check = []
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules_to_check.append(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                # node.module is None for relative imports like `from . import x`
                if node.module is not None:
                    modules_to_check.append(node.module.split(".")[0])

            for module in modules_to_check:
                if module and module in BLOCKED_MODULES:
                    errors.append(f"Blocked import: {module}")

        # Check for blocked builtins used as function calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_BUILTINS:
                errors.append(f"Blocked builtin call: {node.func.id}()")
            elif isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                    errors.append(f"Blocked call: os.{node.func.attr}()")

    # Warning: if no return statement in transform
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "transform":
            has_return = any(isinstance(n, ast.Return) for n in ast.walk(node))
            if not has_return:
                warnings.append("transform() has no return statement — may return None")

    valid = len(errors) == 0
    return valid, errors, warnings


def validator_node(state: AgentState) -> dict:
    """Validate generated code: static analysis + LLM semantic check."""
    code = state["generated_code"]

    # Step 1: Static validation (fast, no LLM)
    static_valid, static_errors, static_warnings = _static_validate(code)

    if not static_valid:
        return {
            "validation_result": {
                "valid": False,
                "errors": static_errors,
                "warnings": static_warnings,
            },
            "last_error": "; ".join(static_errors),
        }

    # Step 2: LLM semantic validation
    metadata = state["csv_metadata"]
    user_prompt = VALIDATOR_USER_TEMPLATE.format(
        plan=state["plan"],
        columns=metadata.get("columns", []),
        dtypes=metadata.get("dtypes", {}),
        sample_rows=json.dumps(metadata.get("sample_rows", []), indent=2, default=str),
        code=code,
    )

    response = litellm.completion(
        **get_litellm_kwargs(),
        messages=[
            {"role": "system", "content": VALIDATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
    )

    raw = response.choices[0].message.content.strip()
    # Parse JSON from response (handle markdown fences)
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Cannot parse LLM response — fail closed, do not assume valid
        error_msg = f"LLM validator returned non-JSON response: {raw[:200]}"
        return {
            "validation_result": {
                "valid": False,
                "errors": [error_msg],
                "warnings": static_warnings,
            },
            "last_error": error_msg,
        }

    # Merge static warnings
    result["warnings"] = static_warnings + result.get("warnings", [])

    is_valid = result.get("valid", False)
    return {
        "validation_result": {
            "valid": is_valid,
            "errors": result.get("errors", []),
            "warnings": result.get("warnings", []),
        },
        "last_error": (
            "; ".join(result.get("errors", [])) if not is_valid else ""
        ),
    }
