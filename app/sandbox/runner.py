"""Sandbox runner — executed inside Docker container.

Receives:
  - /home/sandbox/input.csv   (mounted)
  - /home/sandbox/code.py     (mounted, contains `def transform(df)`)

Produces:
  - /home/sandbox/output.csv  (result)
  - stdout: JSON with status and error info
"""

import json
import sys
import traceback

import pandas as pd


def main():
    try:
        # Read input CSV
        df = pd.read_csv("/home/sandbox/input.csv")

        # Read and exec the transform code
        with open("/home/sandbox/code.py", "r") as f:
            code = f.read()

        local_ns: dict = {}
        exec(code, {"pd": pd, "pandas": pd, "np": __import__("numpy"), "numpy": __import__("numpy")}, local_ns)

        if "transform" not in local_ns:
            print(json.dumps({"success": False, "error": "No 'transform' function defined in generated code"}))
            sys.exit(1)

        # Execute transform
        result = local_ns["transform"](df)

        if not isinstance(result, pd.DataFrame):
            print(json.dumps({"success": False, "error": f"transform() returned {type(result).__name__}, expected DataFrame"}))
            sys.exit(1)

        # Write output
        result.to_csv("/home/sandbox/output.csv", index=False)
        print(json.dumps({
            "success": True,
            "rows": len(result),
            "columns": list(result.columns),
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
