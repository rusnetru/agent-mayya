import json

from src.agent.conversational import MAX_HISTORY_MESSAGES, ConversationalAgent
from src.memory.api import Memory


class FakeTool:
    name = "fake"
    description = "fake tool"
    parameters: dict = {}
    required: list = []

    def __init__(self, result: str) -> None:
        self.result = result
        self.calls: list[dict] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class FakeClient:
    """Scripted client: pops one response per complete_with_tools call."""

    def __init__(self, responses: list[dict], summary: str = "конспект: ...") -> None:
        self.responses = list(responses)
        self.seen_messages: list[list[dict]] = []
        self.summary = summary
        self.complete_calls: list[tuple[str, str]] = []

    def complete_with_tools(self, system_prompt, user_message, tools, temperature=0.3, messages=None):
        self.seen_messages.append(list(messages or []))
        return self.responses.pop(0) if self.responses else {"content": "готово"}

    def complete(self, system_prompt, user_message, temperature=0.3):
        self.complete_calls.append((system_prompt, user_message))
        return self.summary


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


def test_compaction_builds_summary_and_injects_it():
    client = FakeClient(
        [{"content": f"r{i}"} for i in range(40)],
        summary="Пользователь — Руслан, обсуждали план запуска.",
    )
    agent = ConversationalAgent(client, tools={})

    for i in range(20):  # 40 messages -> compaction fires
        agent.chat(f"msg {i}")

    assert agent.summary == "Пользователь — Руслан, обсуждали план запуска."
    # evicted messages went into the summarizer
    assert client.complete_calls, "summarizer was never called"
    sys_prompt, evicted_text = client.complete_calls[0]
    assert "конспект" in sys_prompt.lower()
    assert "msg 0" in evicted_text
    # summary is injected into the next turn's system prompt
    agent.chat("ещё")
    system = client.seen_messages[-1][0]["content"]
    assert "Руслан" in system


def test_summarizer_failure_keeps_old_summary():
    class NoCompleteClient(FakeClient):
        def complete(self, *a, **k):
            raise RuntimeError("LLM down")

    client = NoCompleteClient([{"content": f"r{i}"} for i in range(40)])
    agent = ConversationalAgent(client, tools={})
    agent.summary = "старый конспект"

    for i in range(20):
        agent.chat(f"msg {i}")

    assert agent.summary == "старый конспект"  # not lost, dialog not broken


def test_reset_clears_summary():
    agent = ConversationalAgent(FakeClient([{"content": "a"}]), tools={})
    agent.summary = "x"
    agent.reset()
    assert agent.summary == ""


def test_reset_clears_history():
    client = FakeClient([{"content": "a"}])
    agent = ConversationalAgent(client, tools={})
    agent.chat("hi")
    agent.reset()
    assert agent.messages == []


def test_remember_tool_added_with_memory_and_stores_fact():
    memory = Memory(db_path=":memory:")
    client = FakeClient([
        {
            "content": "",
            "tool_calls": [
                {"id": "r1", "name": "remember", "arguments": '{"fact": "Пользователя зовут Руслан"}'},
            ],
        },
        {"content": "Запомнила!"},
    ])
    agent = ConversationalAgent(client, memory=memory, tools={})

    assert "remember" in agent._tools
    reply = agent.chat("запомни: меня зовут Руслан")

    assert reply == "Запомнила!"
    stored = [e.content for e in memory.episodic.all()]
    assert any("Пользователя зовут Руслан" in s for s in stored)


def test_no_remember_tool_without_memory():
    agent = ConversationalAgent(FakeClient([]), tools={})
    assert "remember" not in agent._tools


def test_delegate_tool_runs_subagent_without_recursion():
    tool = FakeTool("data")
    client = FakeClient([
        # parent: delegate the research
        {
            "content": "",
            "tool_calls": [
                {"id": "d1", "name": "delegate_task", "arguments": '{"task": "собери данные"}'},
            ],
        },
        # sub-agent: answers in plain text
        {"content": "готовые данные"},
        # parent: final answer using sub result
        {"content": "итог: готовые данные"},
    ])
    agent = ConversationalAgent(client, tools={"fake": tool})

    assert "delegate_task" in agent._tools
    reply = agent.chat("сделай большую задачу")

    assert reply == "итог: готовые данные"
    # sub-agent call (second) must not see delegate_task among its tools
    sub_call_msgs = client.seen_messages[1]
    assert sub_call_msgs[0]["role"] == "system"
    # and the tool result fed back to the parent contains the sub answer
    parent_final = client.seen_messages[2]
    tool_msgs = [m for m in parent_final if m.get("role") == "tool"]
    assert tool_msgs and "готовые данные" in tool_msgs[0]["content"]


def test_delegate_disabled_flag():
    agent = ConversationalAgent(FakeClient([]), tools={"fake": FakeTool("x")}, allow_delegate=False)
    assert "delegate_task" not in agent._tools
