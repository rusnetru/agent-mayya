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

    monkeypatch.setattr(m, "_search_html", boom)
    monkeypatch.setattr(m, "_search_lite", boom)
    data = json.loads(m.web_search("query"))
    assert data["success"] is False
    assert data["results"] == []
