# Next Gen Agent — Terminal tool (перенесено из Hermes: инструмент terminal)

import json
import os
import subprocess


def run_command(command: str, cwd: str = "", timeout: int = 60) -> str:
    """Run a shell command and return stdout/stderr/returncode as JSON."""
    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        timeout = 60
    timeout = min(timeout, 300)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd or os.getcwd(),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return json.dumps(
            {
                "success": result.returncode == 0,
                "stdout": (result.stdout or "")[:8000],
                "stderr": (result.stderr or "")[:3000],
                "returncode": result.returncode,
            },
            ensure_ascii=False,
        )
    except subprocess.TimeoutExpired:
        return json.dumps({"success": False, "error": f"Timeout after {timeout}s", "command": command})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "command": command})
