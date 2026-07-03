# Next Gen Agent — Tool registry

from typing import Any, Callable

from src.tools.file_tools import list_dir, read_file, write_file
from src.tools.python_exec import python_exec
from src.tools.web_search import web_search

ToolFn = Callable[..., str]


class Tool:
    name: str
    description: str
    fn: ToolFn
    parameters: dict[str, Any]

    def __init__(self, name: str, description: str, fn: ToolFn, parameters: dict[str, Any] | None = None) -> None:
        self.name = name
        self.description = description
        self.fn = fn
        self.parameters = parameters or {}

    def run(self, **kwargs: Any) -> str:
        return self.fn(**kwargs)


# ── Registry ──────────────────────────────────────────────
REGISTRY: dict[str, Tool] = {
    "web_search": Tool(
        name="web_search",
        description="Search the web using DuckDuckGo. Returns JSON with results: title, url, snippet.",
        fn=web_search,
        parameters={"query": "search query string", "max_results": "number of results (default 5)"},
    ),
    "read_file": Tool(
        name="read_file",
        description="Read text from a file. Returns JSON with content.",
        fn=read_file,
        parameters={"path": "absolute or relative file path"},
    ),
    "write_file": Tool(
        name="write_file",
        description="Write text to a file (overwrites). Creates parent directories if needed. Returns JSON.",
        fn=write_file,
        parameters={"path": "file path", "content": "text content to write"},
    ),
    "list_dir": Tool(
        name="list_dir",
        description="List files and directories in a path. Returns JSON.",
        fn=list_dir,
        parameters={"path": "directory path (default: current dir)"},
    ),
    "python_exec": Tool(
        name="python_exec",
        description="Execute Python code in a subprocess. Returns JSON with stdout/stderr/returncode. Timeout: 30s.",
        fn=python_exec,
        parameters={"code": "Python code to execute"},
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
                    "properties": {k: {"type": "string", "description": v} for k, v in tool.parameters.items()},
                    "required": list(tool.parameters.keys()),
                },
            },
        }
        for tool in REGISTRY.values()
    ]
