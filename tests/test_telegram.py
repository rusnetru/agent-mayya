import threading

import pytest

from src.channels.telegram import MAX_MESSAGE_LEN, TelegramChannel, run_telegram_loop


class FakeTransport:
    """Records API calls; returns scripted getUpdates batches."""

    def __init__(self, update_batches=None):
        self.batches = list(update_batches or [])
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, method, params, timeout):
        self.calls.append((method, dict(params)))
        if method == "getUpdates":
            result = self.batches.pop(0) if self.batches else []
            return {"ok": True, "result": result}
        if method == "getMe":
            return {"ok": True, "result": {"username": "mayya_bot"}}
        return {"ok": True, "result": {}}


def _update(update_id, user_id, text, chat_id=100):
    return {
        "update_id": update_id,
        "message": {
            "text": text,
            "chat": {"id": chat_id},
            "from": {"id": user_id, "username": f"u{user_id}"},
        },
    }


def test_requires_token():
    with pytest.raises(ValueError):
        TelegramChannel("")


def test_poll_filters_by_allowed_users_and_advances_offset():
    transport = FakeTransport([
        [_update(10, 1, "привет от своего"), _update(11, 999, "чужой")],
    ])
    ch = TelegramChannel("tok", allowed_users={"1"}, transport=transport)

    messages = ch.poll_messages()

    assert [m["text"] for m in messages] == ["привет от своего"]
    assert ch.offset == 12  # both updates acknowledged, чужое не переигрывается
    assert ch.last_chat_id == 100


def test_poll_allows_everyone_when_no_allowlist():
    transport = FakeTransport([[_update(1, 555, "hi")]])
    ch = TelegramChannel("tok", transport=transport)
    assert len(ch.poll_messages()) == 1


def test_send_message_splits_long_text():
    transport = FakeTransport()
    ch = TelegramChannel("tok", transport=transport)

    ch.send_message(1, "x" * (MAX_MESSAGE_LEN + 10))

    sends = [(m, p) for m, p in transport.calls if m == "sendMessage"]
    assert len(sends) == 2
    assert len(sends[0][1]["text"]) == MAX_MESSAGE_LEN
    assert len(sends[1][1]["text"]) == 10


def test_loop_routes_message_through_agent_and_replies():
    transport = FakeTransport([[_update(1, 7, "как дела?")]])
    ch = TelegramChannel("tok", allowed_users={"7"}, transport=transport)

    class FakeAgent:
        def chat(self, text):
            return f"ответ на: {text}"

    stop = threading.Event()

    original_poll = ch.poll_messages

    def poll_then_stop():
        msgs = original_poll()
        stop.set()  # one cycle only
        return msgs

    ch.poll_messages = poll_then_stop
    run_telegram_loop(ch, FakeAgent(), stop=stop)

    sends = [(m, p) for m, p in transport.calls if m == "sendMessage"]
    assert len(sends) == 1
    assert sends[0][1]["chat_id"] == 100
    assert sends[0][1]["text"] == "ответ на: как дела?"


def test_agent_error_reported_to_chat():
    transport = FakeTransport([[_update(1, 7, "сломайся")]])
    ch = TelegramChannel("tok", transport=transport)

    class BrokenAgent:
        def chat(self, text):
            raise RuntimeError("boom")

    stop = threading.Event()
    original_poll = ch.poll_messages

    def poll_then_stop():
        msgs = original_poll()
        stop.set()
        return msgs

    ch.poll_messages = poll_then_stop
    run_telegram_loop(ch, BrokenAgent(), stop=stop)

    sends = [(m, p) for m, p in transport.calls if m == "sendMessage"]
    assert sends and "boom" in sends[0][1]["text"]
