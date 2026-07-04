from types import SimpleNamespace

from src.agent.conversational import ConversationalAgent
from src.llm.client import assemble_stream


def _chunk(content=None, tool_calls=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def _tc(index, id=None, name=None, arguments=None):
    fn = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(index=index, id=id, function=fn)


def test_assemble_stream_joins_text_and_forwards_deltas():
    deltas = []
    result = assemble_stream(
        [_chunk("При"), _chunk("вет"), SimpleNamespace(choices=[]), _chunk("!")],
        deltas.append,
    )
    assert result == {"content": "Привет!"}
    assert deltas == ["При", "вет", "!"]


def test_assemble_stream_stitches_tool_call_fragments():
    chunks = [
        _chunk(tool_calls=[_tc(0, id="call_1", name="web_search", arguments='{"que')]),
        _chunk(tool_calls=[_tc(0, arguments='ry": "MCP"}')]),
        _chunk(tool_calls=[_tc(1, id="call_2", name="read_file", arguments='{"path": "a.py"}')]),
    ]
    result = assemble_stream(chunks, lambda t: None)
    assert result["tool_calls"] == [
        {"id": "call_1", "name": "web_search", "arguments": '{"query": "MCP"}'},
        {"id": "call_2", "name": "read_file", "arguments": '{"path": "a.py"}'},
    ]


class StreamingFakeClient:
    """Fake client that streams content char-by-char when on_delta is passed."""

    def __init__(self, responses):
        self.responses = list(responses)

    def complete_with_tools(self, system_prompt, user_message, tools,
                            temperature=0.3, messages=None, on_delta=None):
        resp = self.responses.pop(0)
        if on_delta is not None:
            for ch in resp.get("content", ""):
                on_delta(ch)
        return resp

    def complete(self, system_prompt, user_message, temperature=0.3):
        return "конспект"


class FakeTool:
    name = "t"
    description = "d"
    parameters: dict = {}
    required: list = []

    def run(self, **kwargs):
        return "ok"


def test_chat_emits_text_and_tool_events():
    client = StreamingFakeClient([
        {"content": "", "tool_calls": [{"id": "1", "name": "t", "arguments": "{}"}]},
        {"content": "готово"},
    ])
    agent = ConversationalAgent(client, tools={"t": FakeTool()}, allow_delegate=False)

    events = []
    reply = agent.chat("сделай", on_event=events.append)

    assert reply == "готово"
    tool_events = [e for e in events if e["type"] == "tool"]
    assert tool_events == [{"type": "tool", "name": "t", "args": "{}"}]
    text = "".join(e["delta"] for e in events if e["type"] == "text")
    assert text == "готово"


def test_chat_without_on_event_never_passes_on_delta():
    class StrictClient:
        """Fails if on_delta is passed — mimics older client signatures."""

        def complete_with_tools(self, system_prompt, user_message, tools,
                                temperature=0.3, messages=None):
            return {"content": "ок"}

        def complete(self, *a, **k):
            return ""

    agent = ConversationalAgent(StrictClient(), tools={}, allow_delegate=False)
    assert agent.chat("привет") == "ок"
