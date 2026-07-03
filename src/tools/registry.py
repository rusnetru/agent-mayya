# Next Gen Agent — Tool registry

from typing import Any, Callable

from src.tools.file_tools import list_dir, read_file, write_file
from src.tools.python_exec import python_exec
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
        description="Search the web using DuckDuckGo. Returns JSON with results: title, url, snippet.",
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
    "list_dir": Tool(
        name="list_dir",
        description="List files and directories in a path. Returns JSON.",
        fn=list_dir,
        parameters={
            "path": {"type": "string", "description": "directory path (default: current dir)"},
        },
        required=[],
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


def get_tool_schemas() -> list[dict[str, Any]]:
    """Return OpenAI-compatible function calling schemas."""
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
        for tool in REGISTRY.values()
    ]
