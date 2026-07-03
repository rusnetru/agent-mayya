# Next Gen Agent — Python REPL tool (sandboxed subprocess)

import json
import os
import subprocess


def python_exec(code: str, timeout: int = 30) -> str:
    """Execute Python code in a subprocess. Returns JSON with stdout/stderr."""
    try:
        result = subprocess.run(
            ["python", "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd(),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return json.dumps(
            {
                "success": result.returncode == 0,
                "stdout": result.stdout[:5000],
                "stderr": result.stderr[:2000],
                "returncode": result.returncode,
            }
        )
    except subprocess.TimeoutExpired:
        return json.dumps({"success": False, "error": f"Timeout after {timeout}s"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
