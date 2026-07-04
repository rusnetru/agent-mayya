# Next Gen Agent — Tool registry

from typing import Any, Callable

from src.tools.cron import cronjob
from src.tools.file_tools import edit_file, list_dir, read_file, search_files, write_file
from src.tools.python_exec import python_exec
from src.tools.shell import run_command
from src.tools.web_search import web_search
from src.tools.web_extract import web_extract

ToolFn = Callable[..., str]


class Tool:
    """A callable tool with a JSON-schema parameter spec.

    `parameters` maps a param name to its JSON-schema fragment, e.g.
    {"query": {"type": "string", "description": "..."}}. `required` lists the
    params the model must provide; the rest keep their Python defaults.
    """

    def __init__(
        self,
        name: str,
        description: str,
        fn: ToolFn,
        parameters: dict[str, dict[str, Any]] | None = None,
        required: list[str] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.fn = fn
        self.parameters = parameters or {}
        self.required = required if required is not None else list(self.parameters.keys())

    def run(self, **kwargs: Any) -> str:
        return self.fn(**self._coerce(kwargs))

    def _coerce(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Drop undeclared params and cast values to their declared JSON types —
        LLMs routinely pass integers as strings ("5") or invent extra args."""
        clean: dict[str, Any] = {}
        for key, value in kwargs.items():
            spec = self.parameters.get(key)
            if spec is None:
                continue
            expected = spec.get("type")
            try:
                if expected == "integer" and not isinstance(value, int):
                    value = int(str(value).strip())
                elif expected == "number" and not isinstance(value, (int, float)):
                    value = float(str(value).strip())
                elif expected == "boolean" and isinstance(value, str):
                    value = value.strip().lower() in ("true", "1", "yes")
                elif expected == "string" and not isinstance(value, str):
                    value = str(value)
            except (TypeError, ValueError):
                continue  # unusable value — let the Python default apply
            clean[key] = value
        return clean


# ── Registry ──────────────────────────────────────────────
REGISTRY: dict[str, Tool] = {
    "web_search": Tool(
        name="web_search",
        description="Search the web (Serper/Google → Yandex → DuckDuckGo fallback chain). Returns JSON with results: title, url, snippet.",
        fn=web_search,
        parameters={
            "query": {"type": "string", "description": "search query string"},
            "max_results": {"type": "integer", "description": "number of results (default 5)"},
        },
        required=["query"],
    ),
    "web_extract": Tool(
        name="web_extract",
        description="Fetch a web page and return its text content. Use after web_search to read found pages. Returns JSON.",
        fn=web_extract,
        parameters={
            "url": {"type": "string", "description": "page URL to fetch"},
            "max_chars": {"type": "integer", "description": "max characters (default 8000)"},
        },
        required=["url"],
    ),
    "read_file": Tool(
        name="read_file",
        description="Read text from a file. Returns JSON with content.",
        fn=read_file,
        parameters={
            "path": {"type": "string", "description": "absolute or relative file path"},
        },
    ),
    "write_file": Tool(
        name="write_file",
        description="Write text to a file (overwrites). Creates parent directories if needed. Returns JSON.",
        fn=write_file,
        parameters={
            "path": {"type": "string", "description": "file path"},
            "content": {"type": "string", "description": "text content to write"},
        },
    ),
    "edit_file": Tool(
        name="edit_file",
        description="Edit a file by exact find-and-replace. `find` must occur exactly once in the file. Use instead of write_file for small changes.",
        fn=edit_file,
        parameters={
            "path": {"type": "string", "description": "file path"},
            "find": {"type": "string", "description": "exact text fragment to replace (must be unique in the file)"},
            "replace": {"type": "string", "description": "replacement text"},
        },
    ),
    "search_files": Tool(
        name="search_files",
        description="Search text files recursively by regex. Returns matches: file, line number, line text.",
        fn=search_files,
        parameters={
            "pattern": {"type": "string", "description": "regex pattern (case-insensitive)"},
            "path": {"type": "string", "description": "directory to search (default: current dir)"},
            "max_results": {"type": "integer", "description": "max matches (default 50)"},
        },
        required=["pattern"],
    ),
    "run_command": Tool(
        name="run_command",
        description="Run a shell command (Windows cmd). Returns JSON with stdout/stderr/returncode. Use for git, pip, dir, running scripts. Timeout 60s (max 300).",
        fn=run_command,
        parameters={
            "command": {"type": "string", "description": "shell command to execute"},
            "cwd": {"type": "string", "description": "working directory (default: current)"},
            "timeout": {"type": "integer", "description": "seconds before kill (default 60, max 300)"},
        },
        required=["command"],
    ),
    "list_dir": Tool(
        name="list_dir",
        description="List files and directories in a path. Returns JSON.",
        fn=list_dir,
        parameters={
            "path": {"type": "string", "description": "directory path (default: current dir)"},
        },
        required=[],
    ),
    "cronjob": Tool(
        name="cronjob",
        description=(
            "Manage scheduled jobs that run automatically. Actions: create (needs schedule+task), "
            "list, remove (needs job_id). Schedule formats: 'every 10m', 'every 2h', 'daily 09:30', "
            "'in 30m' (one-shot), 'once 2026-07-05 18:00' (one-shot). The task text is executed by "
            "Mayya herself when due."
        ),
        fn=cronjob,
        parameters={
            "action": {"type": "string", "description": "create | list | remove"},
            "schedule": {"type": "string", "description": "when to run (for create)"},
            "task": {"type": "string", "description": "what to do, plain language (for create)"},
            "job_id": {"type": "string", "description": "job id (for remove)"},
        },
        required=["action"],
    ),
    "python_exec": Tool(
        name="python_exec",
        description="Execute Python code in a subprocess. Returns JSON with stdout/stderr/returncode. Timeout: 30s.",
        fn=python_exec,
        parameters={
            "code": {"type": "string", "description": "Python code to execute"},
        },
    ),
}


def get_tool(name: str) -> Tool | None:
    return REGISTRY.get(name)


def get_all_tools() -> dict[str, Tool]:
    return dict(REGISTRY)


def get_tool_schemas(tools: dict[str, Tool] | None = None) -> list[dict[str, Any]]:
    """Return OpenAI-compatible function calling schemas (for REGISTRY by default)."""
    source = REGISTRY if tools is None else tools
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": tool.parameters,
                    "required": tool.required,
                },
            },
        }
        for tool in source.values()
    ]
