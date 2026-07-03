# Next Gen Agent — File Read/Write tools

import json
import os


def read_file(path: str) -> str:
    """Read text from a file. Returns JSON with content or error."""
    try:
        if not os.path.isfile(path):
            return json.dumps({"success": False, "error": f"File not found: {path}"})
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return json.dumps({"success": True, "content": content, "path": path, "size": len(content)})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "path": path})


def write_file(path: str, content: str) -> str:
    """Write text to a file (overwrites). Returns JSON with result."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return json.dumps({"success": True, "path": path, "written": len(content)})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "path": path})


def list_dir(path: str = ".") -> str:
    """List files and dirs in a directory. Returns JSON."""
    try:
        entries = []
        with os.scandir(path) as it:
            for entry in it:
                entries.append(
                    {"name": entry.name, "type": "dir" if entry.is_dir() else "file", "path": entry.path}
                )
        return json.dumps({"success": True, "path": path, "entries": entries})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "path": path})
