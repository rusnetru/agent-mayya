import pytest

from src.llm.client import LLMClient


def test_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("src.llm.client.load_dotenv", lambda: None)
    with pytest.raises(RuntimeError):
        LLMClient(api_key=None)


def test_accepts_explicit_api_key(monkeypatch):
    from src.llm.client import DEFAULT_MODEL

    monkeypatch.setattr("src.llm.client.load_dotenv", lambda: None)
    client = LLMClient(api_key="sk-test-key")
    assert client.model == DEFAULT_MODEL
    assert client.model.startswith("deepseek-")
