"""Sandbox runner — executed inside Docker container.

Receives:
  - /home/sandbox/input.csv   (mounted)
  - /home/sandbox/code.py     (mounted, contains `def transform(df)`)

Produces:
  - /home/sandbox/output.csv  (result)
  - stdout: JSON with status and error info
"""

import json
import os
import sys
import traceback

import pandas as pd

INPUT_CSV = os.environ.get("SANDBOX_INPUT", "/home/sandbox/input.csv")
CODE_FILE = os.environ.get("SANDBOX_CODE", "/home/sandbox/code.py")
OUTPUT_CSV = os.environ.get("SANDBOX_OUTPUT", "/home/sandbox/output.csv")


def main():
    try:
        # Read input CSV
        df = pd.read_csv(INPUT_CSV)

        # Read and exec the transform code
        with open(CODE_FILE, "r") as f:
            code = f.read()

        local_ns: dict = {}
        exec(code, {"pd": pd, "pandas": pd, "np": __import__("numpy"), "numpy": __import__("numpy")}, local_ns)

        if "transform" not in local_ns:
            print(json.dumps({"success": False, "error": "No 'transform' function defined in generated code"}))
            sys.exit(1)

        # Execute transform
        result = local_ns["transform"](df)

        if isinstance(result, pd.DataFrame):
            # Standard operation: write CSV output
            result.to_csv(OUTPUT_CSV, index=False)
            print(json.dumps({
                "success": True,
                "rows": len(result),
                "columns": list(result.columns),
            }))
        else:
            # Analysis result: return value as string, no CSV written
            if hasattr(result, "to_string"):
                result_str = result.to_string()
            else:
                result_str = str(result)
            print(json.dumps({
                "success": True,
                "result_value": result_str,
            }))

    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(),
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
