"""Minimal MCP client (stdio transport) — подключение внешних MCP-серверов.

Model Context Protocol: JSON-RPC 2.0, по одному JSON-сообщению на строку через
stdin/stdout дочернего процесса. Реализован необходимый минимум: initialize
handshake, tools/list, tools/call. Никаких внешних зависимостей.

Конфиг — mcp.json в корне проекта:
{
  "servers": {
    "playwright": {"command": "C:\\...\\playwright-mcp.cmd", "args": ["--headless"]},
    "github": {"command": "C:\\...\\mcp-server-github.cmd",
               "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"}}
  }
}
Значения вида ${VAR} в env разворачиваются из окружения.
"""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import threading

PROTOCOL_VERSION = "2024-11-05"
DEFAULT_CONFIG = "mcp.json"
CALL_TIMEOUT = 60
START_TIMEOUT = 25


class MCPError(Exception):
    pass


class MCPServer:
    """One stdio MCP server: spawn, handshake, list/call tools."""

    def __init__(self, name: str, command: str | list[str], args: list[str] | None = None,
                 env: dict[str, str] | None = None) -> None:
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.tools: list[dict] = []
        self._proc: subprocess.Popen | None = None
        self._responses: queue.Queue = queue.Queue()
        self._next_id = 0
        self._lock = threading.Lock()

    # ── lifecycle ─────────────────────────────────────────────

    def start(self) -> None:
        cmd = self._build_cmd()
        env = {**os.environ, **{k: _expand(v) for k, v in self.env.items()}}
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
        )
        threading.Thread(target=self._reader, daemon=True).start()

        self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mayya", "version": "1.0"},
            },
            timeout=START_TIMEOUT,
        )
        self._notify("notifications/initialized")
        result = self._request("tools/list", {}, timeout=START_TIMEOUT)
        self.tools = result.get("tools", [])

    def close(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass
        self._proc = None

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # ── tools ─────────────────────────────────────────────────

    def call_tool(self, tool_name: str, arguments: dict, timeout: int = CALL_TIMEOUT) -> str:
        result = self._request(
            "tools/call", {"name": tool_name, "arguments": arguments}, timeout=timeout
        )
        parts = [
            c.get("text", "")
            for c in result.get("content", [])
            if isinstance(c, dict) and c.get("type") == "text"
        ]
        text = "\n".join(p for p in parts if p) or json.dumps(result, ensure_ascii=False)
        if result.get("isError"):
            return f"MCP tool error: {text}"
        return text

    # ── JSON-RPC plumbing ─────────────────────────────────────

    def _build_cmd(self) -> list[str]:
        cmd = self.command if isinstance(self.command, list) else [self.command]
        cmd = cmd + self.args
        # CreateProcess не запускает .cmd/.bat напрямую — заворачиваем в cmd /c
        if os.name == "nt" and cmd[0].lower().endswith((".cmd", ".bat")):
            cmd = ["cmd", "/c", *cmd]
        return cmd

    def _reader(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue  # stray log line on stdout
            if "id" in msg and ("result" in msg or "error" in msg):
                self._responses.put(msg)
            # notifications/requests from server are ignored — minimal client

    def _send(self, payload: dict) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None or proc.poll() is not None:
            raise MCPError(f"server '{self.name}' is not running")
        proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        proc.stdin.flush()

    def _notify(self, method: str, params: dict | None = None) -> None:
        msg: dict = {"jsonrpc": "2.0", "method": method}
        if params:
            msg["params"] = params
        self._send(msg)

    def _request(self, method: str, params: dict, timeout: int = CALL_TIMEOUT) -> dict:
        with self._lock:
            self._next_id += 1
            req_id = self._next_id
            self._send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
            deadline = timeout
            pending: list[dict] = []
            try:
                while True:
                    msg = self._responses.get(timeout=deadline)
                    if msg.get("id") == req_id:
                        for p in pending:  # put back out-of-order replies
                            self._responses.put(p)
                        if "error" in msg:
                            raise MCPError(f"{method}: {msg['error'].get('message', msg['error'])}")
                        return msg.get("result", {})
                    pending.append(msg)
            except queue.Empty:
                raise MCPError(f"{method}: timeout after {timeout}s") from None


def _expand(value: str) -> str:
    """Expand ${VAR} placeholders from the environment."""
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), value)


class MCPManager:
    """Loads mcp.json, connects servers, exposes their tools as registry Tools."""

    def __init__(self, config_path: str = DEFAULT_CONFIG) -> None:
        self.config_path = config_path
        self.servers: dict[str, MCPServer] = {}
        self.errors: dict[str, str] = {}

    def connect(self) -> None:
        if not os.path.isfile(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            self.errors["mcp.json"] = str(e)
            return
        for name, spec in config.get("servers", {}).items():
            server = MCPServer(
                name,
                command=spec.get("command", ""),
                args=spec.get("args", []),
                env=spec.get("env", {}),
            )
            try:
                server.start()
                self.servers[name] = server
            except Exception as e:
                server.close()
                self.errors[name] = str(e)

    def make_tools(self) -> dict:
        """Wrap every MCP tool as a registry Tool named <server>_<tool>."""
        from src.tools.registry import Tool

        tools: dict = {}
        for server_name, server in self.servers.items():
            for spec in server.tools:
                tool_name = f"{server_name}_{spec['name']}"[:64]
                schema = spec.get("inputSchema", {})
                tools[tool_name] = Tool(
                    name=tool_name,
                    description=(spec.get("description") or "")[:1024],
                    fn=_make_caller(server, spec["name"]),
                    parameters=schema.get("properties", {}),
                    required=schema.get("required", []),
                )
        return tools

    def close(self) -> None:
        for server in self.servers.values():
            server.close()

    def status(self) -> str:
        parts = [f"{n}: {len(s.tools)} tools" for n, s in self.servers.items()]
        parts += [f"{n}: FAILED ({e[:60]})" for n, e in self.errors.items()]
        return "; ".join(parts) if parts else "no servers"


def _make_caller(server: MCPServer, tool_name: str):
    def call(**kwargs):
        return server.call_tool(tool_name, kwargs)
    return call
