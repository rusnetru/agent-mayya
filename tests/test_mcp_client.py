import os
import sys

import pytest

from src.mcp.client import MCPManager, MCPServer, _expand

FAKE_SERVER = os.path.join(os.path.dirname(__file__), "fake_mcp_server.py")


@pytest.fixture()
def server():
    s = MCPServer("fake", command=[sys.executable, FAKE_SERVER])
    s.start()
    yield s
    s.close()


def test_handshake_and_tools_list(server):
    assert server.alive
    assert [t["name"] for t in server.tools] == ["echo"]
    assert server.tools[0]["inputSchema"]["required"] == ["text"]


def test_call_tool_returns_text(server):
    assert server.call_tool("echo", {"text": "привет"}) == "echo: привет"


def test_manager_wraps_tools_with_namespace(tmp_path, monkeypatch):
    config = tmp_path / "mcp.json"
    config.write_text(
        '{"servers": {"fake": {"command": ["%s", "%s"]}}}'
        % (sys.executable.replace("\\", "\\\\"), FAKE_SERVER.replace("\\", "\\\\")),
        encoding="utf-8",
    )
    manager = MCPManager(config_path=str(config))
    manager.connect()
    try:
        tools = manager.make_tools()
        assert "fake_echo" in tools
        tool = tools["fake_echo"]
        assert tool.required == ["text"]
        assert tool.run(text="hi") == "echo: hi"
        assert "fake: 1 tools" in manager.status()
    finally:
        manager.close()


def test_manager_survives_broken_server(tmp_path):
    config = tmp_path / "mcp.json"
    config.write_text('{"servers": {"bad": {"command": "no_such_binary_xyz.exe"}}}', encoding="utf-8")
    manager = MCPManager(config_path=str(config))
    manager.connect()  # must not raise
    assert manager.servers == {}
    assert "bad" in manager.errors


def test_manager_no_config_is_noop(tmp_path):
    manager = MCPManager(config_path=str(tmp_path / "missing.json"))
    manager.connect()
    assert manager.servers == {}
    assert manager.make_tools() == {}


def test_env_expansion(monkeypatch):
    monkeypatch.setenv("MY_TOKEN", "sekret")
    assert _expand("${MY_TOKEN}") == "sekret"
    assert _expand("prefix-${MY_TOKEN}") == "prefix-sekret"
    assert _expand("${MISSING_VAR_XYZ}") == ""
