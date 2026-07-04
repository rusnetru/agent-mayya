import json

from src.tools.registry import REGISTRY
from src.tools.web_search import _parse_ddg_html, _resolve_url

DDG_REDIRECT = (
    "//duckduckgo.com/l/?uddg=https%3A%2F%2Fmodelcontextprotocol.io%2F&rut=abc123"
)

SAMPLE_HTML = f"""
<div class="result">
  <a class="result__a" href="{DDG_REDIRECT}">Model Context <b>Protocol</b></a>
  <a class="result__snippet" href="#">MCP is an <b>open protocol</b> for LLM tools.</a>
</div>
<div class="result">
  <a class="result__a" href="https://example.com/direct">Direct link</a>
  <a class="result__snippet" href="#">Plain result.</a>
</div>
"""


def test_resolve_url_decodes_ddg_redirect():
    assert _resolve_url(DDG_REDIRECT) == "https://modelcontextprotocol.io/"


def test_resolve_url_keeps_direct_urls():
    assert _resolve_url("https://example.com/x") == "https://example.com/x"


def test_parse_ddg_html_returns_decoded_results():
    results = _parse_ddg_html(SAMPLE_HTML, max_results=5)
    assert len(results) == 2
    assert results[0]["url"] == "https://modelcontextprotocol.io/"
    assert results[0]["title"] == "Model Context Protocol"
    assert "open protocol" in results[0]["snippet"]
    assert results[1]["url"] == "https://example.com/direct"


def test_parse_ddg_html_respects_max_results():
    assert len(_parse_ddg_html(SAMPLE_HTML, max_results=1)) == 1


def test_tool_coerces_string_max_results():
    # LLMs pass integers as strings; the registry must coerce, not crash
    tool = REGISTRY["web_search"]
    coerced = tool._coerce({"query": "x", "max_results": "3", "bogus": "y"})
    assert coerced == {"query": "x", "max_results": 3}


def test_tool_schemas_have_types_and_optional_params():
    from src.tools.registry import get_tool_schemas

    schemas = {s["function"]["name"]: s["function"] for s in get_tool_schemas()}
    ws = schemas["web_search"]
    assert ws["parameters"]["properties"]["max_results"]["type"] == "integer"
    assert ws["parameters"]["required"] == ["query"]


def test_web_search_returns_json_even_offline(monkeypatch):
    import src.tools.web_search as m

    def boom(*a, **k):
        raise OSError("no network")

    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("YANDEX_SEARCH_API_KEY", raising=False)
    monkeypatch.setattr(m, "_search_html", boom)
    monkeypatch.setattr(m, "_search_lite", boom)
    data = json.loads(m.web_search("query"))
    assert data["success"] is False
    assert data["results"] == []


def test_provider_chain_order_with_keys(monkeypatch):
    import src.tools.web_search as m

    monkeypatch.setenv("SERPER_API_KEY", "k1")
    monkeypatch.setenv("YANDEX_SEARCH_API_KEY", "k2")
    names = [name for name, _ in m._provider_chain()]
    assert names == ["serper", "yandex", "ddg_html", "ddg_lite"]

    monkeypatch.delenv("SERPER_API_KEY")
    monkeypatch.delenv("YANDEX_SEARCH_API_KEY")
    names = [name for name, _ in m._provider_chain()]
    assert names == ["ddg_html", "ddg_lite"]


def test_chain_falls_through_to_next_provider(monkeypatch):
    import src.tools.web_search as m

    monkeypatch.setenv("SERPER_API_KEY", "k1")
    monkeypatch.delenv("YANDEX_SEARCH_API_KEY", raising=False)

    def serper_fails(q, n):
        raise OSError("serper down")

    def ddg_works(q, n):
        return [{"title": "t", "url": "https://x", "snippet": "s"}]

    monkeypatch.setattr(m, "_search_serper", serper_fails)
    monkeypatch.setattr(m, "_search_html", ddg_works)
    data = json.loads(m.web_search("q"))
    assert data["success"] is True
    assert data["provider"] == "ddg_html"


def test_serper_parses_organic_and_answerbox(monkeypatch):
    import src.tools.web_search as m

    monkeypatch.setenv("SERPER_API_KEY", "k1")
    payload = {
        "answerBox": {"answer": "42"},
        "organic": [
            {"title": "A", "link": "https://a", "snippet": "sa"},
            {"title": "B", "link": "https://b", "snippet": "sb"},
        ],
    }
    monkeypatch.setattr(m, "_post_json", lambda url, headers, body, timeout=15: payload)

    results = m._search_serper("вопрос", 5)
    assert results[0]["snippet"] == "42"  # direct answer surfaced first
    assert results[1]["url"] == "https://a"
    assert len(results) == 3


def test_yandex_xml_parsing():
    from src.tools.web_search import _parse_yandex_xml

    xml = """
    <doc id="1"><url>https://ya.example/one</url><title>Первый <hlword>результат</hlword></title>
    <headline>Описание <hlword>один</hlword></headline></doc>
    <doc id="2"><url>https://ya.example/two</url><title>Второй</title></doc>
    """
    results = _parse_yandex_xml(xml, max_results=5)
    assert results[0] == {
        "title": "Первый результат",
        "url": "https://ya.example/one",
        "snippet": "Описание один",
    }
    assert results[1]["url"] == "https://ya.example/two"
