"""Docker sandbox client — sends code + CSV to an isolated container for execution."""

import json
import logging
import tempfile
from pathlib import Path

import docker

logger = logging.getLogger(__name__)

from app.config import settings

SANDBOX_IMAGE = "aqqrue-sandbox"


def ensure_sandbox_image():
    """Build the sandbox Docker image if it doesn't exist."""
    client = docker.from_env()
    try:
        client.images.get(SANDBOX_IMAGE)
    except docker.errors.ImageNotFound:
        project_root = Path(__file__).resolve().parents[2]
        client.images.build(
            path=str(project_root),
            dockerfile="Dockerfile.sandbox",
            tag=SANDBOX_IMAGE,
        )
    finally:
        client.close()


def run_in_sandbox(code: str, csv_bytes: bytes) -> dict:
    """Run generated code on CSV inside a Docker sandbox.

    Args:
        code: Python code string containing a `def transform(df)` function.
        csv_bytes: The CSV file contents.

    Returns:
        dict with keys:
            success: bool
            csv_output: bytes | None  (output CSV if successful)
            error: str | None
            rows: int | None
            columns: list[str] | None
    """
    try:
        client = docker.from_env()
    except docker.errors.DockerException as e:
        logger.error("Docker not available — refusing to run code outside sandbox: %s", e)
        return {
            "success": False,
            "csv_output": None,
            "error": "Docker is not available. Code execution requires a Docker sandbox.",
        }

    logger.info("Running code in Docker sandbox (image: %s)", SANDBOX_IMAGE)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Write input files
        input_csv = tmpdir_path / "input.csv"
        input_csv.write_bytes(csv_bytes)

        code_file = tmpdir_path / "code.py"
        code_file.write_text(code)

        # Create output placeholder
        output_csv = tmpdir_path / "output.csv"
        output_csv.touch()

        try:
            container = client.containers.run(
                SANDBOX_IMAGE,
                volumes={
                    str(input_csv): {"bind": "/home/sandbox/input.csv", "mode": "ro"},
                    str(code_file): {"bind": "/home/sandbox/code.py", "mode": "ro"},
                    str(output_csv): {"bind": "/home/sandbox/output.csv", "mode": "rw"},
                },
                network_disabled=True,
                mem_limit=settings.SANDBOX_MEMORY_LIMIT,
                detach=False,
                remove=True,
                stdout=True,
                stderr=True,
            )

            # Parse container output
            output = container.decode("utf-8").strip()
            try:
                result = json.loads(output)
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "csv_output": None,
                    "error": f"Invalid sandbox output: {output}",
                }

            if result.get("success"):
                # Analysis result (scalar/string) — no CSV written
                if "result_value" in result:
                    return {
                        "success": True,
                        "csv_output": None,
                        "error": None,
                        "result_value": result["result_value"],
                        "rows": None,
                        "columns": None,
                    }
                csv_output = output_csv.read_bytes()
                return {
                    "success": True,
                    "csv_output": csv_output,
                    "error": None,
                    "rows": result.get("rows"),
                    "columns": result.get("columns"),
                }
            else:
                return {
                    "success": False,
                    "csv_output": None,
                    "error": result.get("error", "Unknown sandbox error"),
                }

        except docker.errors.ContainerError as e:
            stderr = e.stderr.decode("utf-8") if e.stderr else str(e)
            # Try to parse JSON from stderr or stdout
            try:
                result = json.loads(stderr.strip())
                return {
                    "success": False,
                    "csv_output": None,
                    "error": result.get("error", stderr),
                }
            except json.JSONDecodeError:
                return {"success": False, "csv_output": None, "error": stderr}

        except Exception as e:
            return {
                "success": False,
                "csv_output": None,
                "error": f"{type(e).__name__}: {e}",
            }

        finally:
            client.close()
