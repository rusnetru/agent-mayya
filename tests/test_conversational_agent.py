import json

from src.agent.conversational import MAX_HISTORY_MESSAGES, ConversationalAgent
from src.memory.api import Memory


class FakeTool:
    def __init__(self, result: str) -> None:
        self.result = result
        self.calls: list[dict] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class FakeClient:
    """Scripted client: pops one response per complete_with_tools call."""

    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.seen_messages: list[list[dict]] = []

    def complete_with_tools(self, system_prompt, user_message, tools, temperature=0.3, messages=None):
        self.seen_messages.append(list(messages or []))
        return self.responses.pop(0) if self.responses else {"content": "готово"}


def test_plain_text_reply_and_history():
    client = FakeClient([{"content": "привет!"}])
    agent = ConversationalAgent(client, tools={})

    reply = agent.chat("привет")

    assert reply == "привет!"
    assert agent.messages == [
        {"role": "user", "content": "привет"},
        {"role": "assistant", "content": "привет!"},
    ]
    # system prompt goes first and carries the personality
    assert client.seen_messages[0][0]["role"] == "system"
    assert "Майя" in client.seen_messages[0][0]["content"]


def test_tool_call_executed_and_result_fed_back():
    tool = FakeTool(json.dumps({"success": True, "results": [{"title": "MCP"}]}))
    client = FakeClient([
        {
            "content": "",
            "tool_calls": [
                {"id": "t1", "name": "web_search", "arguments": '{"query": "MCP"}'},
            ],
        },
        {"content": "MCP — это протокол."},
    ])
    agent = ConversationalAgent(client, tools={"web_search": tool})

    reply = agent.chat("что такое MCP?")

    assert reply == "MCP — это протокол."
    assert tool.calls == [{"query": "MCP"}]
    # second LLM call must contain the tool result message
    second = client.seen_messages[1]
    tool_msgs = [m for m in second if m.get("role") == "tool"]
    assert tool_msgs and "MCP" in tool_msgs[0]["content"]
    # persistent history holds only user/assistant text — no orphan tool ids
    assert all(m["role"] in ("user", "assistant") for m in agent.messages)
    assert all("tool_calls" not in m for m in agent.messages)


def test_step_budget_forces_final_answer():
    endless_tool_call = {
        "content": "",
        "tool_calls": [{"id": "x", "name": "noop", "arguments": "{}"}],
    }
    client = FakeClient([endless_tool_call] * 12 + [{"content": "вот что успела найти"}])
    agent = ConversationalAgent(client, tools={"noop": FakeTool("ok")})

    reply = agent.chat("зациклись")

    assert reply == "вот что успела найти"


def test_unknown_tool_and_bad_arguments_do_not_crash():
    client = FakeClient([
        {
            "content": "",
            "tool_calls": [
                {"id": "a", "name": "no_such_tool", "arguments": "{"},
            ],
        },
        {"content": "ок"},
    ])
    agent = ConversationalAgent(client, tools={})

    assert agent.chat("сделай") == "ок"


def test_memory_recall_and_store():
    memory = Memory(db_path=":memory:")
    memory.store("Диалог. User: как меня зовут → Mayya: тебя зовут Руслан")

    client = FakeClient([{"content": "Руслан!"}])
    agent = ConversationalAgent(client, memory=memory, tools={})

    agent.chat("как меня зовут?")

    system = client.seen_messages[0][0]["content"]
    assert "Руслан" in system  # recalled episode injected into system prompt
    stored = [e.content for e in memory.episodic.all()]
    assert any("как меня зовут?" in s for s in stored)  # exchange remembered


def test_history_trimmed_and_starts_with_user():
    client = FakeClient([{"content": f"r{i}"} for i in range(40)])
    agent = ConversationalAgent(client, tools={})

    for i in range(40):
        agent.chat(f"msg {i}")

    assert len(agent.messages) <= MAX_HISTORY_MESSAGES
    assert agent.messages[0]["role"] == "user"


def test_reset_clears_history():
    client = FakeClient([{"content": "a"}])
    agent = ConversationalAgent(client, tools={})
    agent.chat("hi")
    agent.reset()
    assert agent.messages == []
