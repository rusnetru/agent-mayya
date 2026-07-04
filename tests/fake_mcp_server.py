"""Fake MCP stdio server for tests: initialize, tools/list, one `echo` tool."""

import json
import sys


def main() -> None:
    # Windows: без этого дочерний python читает/пишет в кодировке локали (cp1251)
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        method = msg.get("method")
        if "id" not in msg:  # notification
            continue
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "serverInfo": {"name": "fake", "version": "1.0"},
            }
        elif method == "tools/list":
            result = {
                "tools": [
                    {
                        "name": "echo",
                        "description": "echo text back",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"text": {"type": "string", "description": "text"}},
                            "required": ["text"],
                        },
                    }
                ]
            }
        elif method == "tools/call":
            text = msg["params"]["arguments"].get("text", "")
            result = {"content": [{"type": "text", "text": f"echo: {text}"}]}
        else:
            sys.stdout.write(json.dumps(
                {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "unknown method"}}
            ) + "\n")
            sys.stdout.flush()
            continue
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
