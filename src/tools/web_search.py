# Next Gen Agent — Web Search tool: multi-provider chain (подход перенесён из Hermes web-search-plus)
#
# Chain: Serper (Google API, ключ) → Yandex Search API (ключ, силён в русском)
#        → DuckDuckGo html (бесплатный) → DuckDuckGo lite (бесплатный fallback)
# Providers without an API key in the environment are skipped silently.
#
# DDG note: result links are redirects (//duckduckgo.com/l/?uddg=<url>) and must
# be decoded, otherwise everything gets filtered out and the search looks empty.

import base64
import urllib.parse
import urllib.request
import json
import os
import re

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


def web_search(query: str, max_results: int = 5) -> str:
    """Search the web across providers (Serper → Yandex → DuckDuckGo). Returns JSON."""
    try:
        max_results = int(max_results)
    except (TypeError, ValueError):
        max_results = 5

    errors: list[str] = []
    for name, fetch in _provider_chain():
        try:
            results = fetch(query, max_results)
            if results:
                return json.dumps(
                    {"success": True, "provider": name, "results": results, "query": query},
                    ensure_ascii=False,
                )
        except Exception as e:
            errors.append(f"{name}: {e}")

    return json.dumps(
        {
            "success": False,
            "error": "; ".join(errors) or "no results from any provider",
            "results": [],
            "query": query,
        },
        ensure_ascii=False,
    )


def _provider_chain() -> list[tuple[str, callable]]:
    chain: list[tuple[str, callable]] = []
    if os.environ.get("SERPER_API_KEY"):
        chain.append(("serper", _search_serper))
    if os.environ.get("YANDEX_SEARCH_API_KEY"):
        chain.append(("yandex", _search_yandex))
    chain.append(("ddg_html", _search_html))
    chain.append(("ddg_lite", _search_lite))
    return chain


def _post_json(url: str, headers: dict, body: dict, timeout: int = 15) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


# ── Serper (Google Search API) ────────────────────────────────


def _search_serper(query: str, max_results: int) -> list[dict]:
    has_cyrillic = bool(re.search(r"[а-яА-ЯёЁ]", query))
    data = _post_json(
        "https://google.serper.dev/search",
        {"X-API-KEY": os.environ["SERPER_API_KEY"]},
        {
            "q": query,
            "num": max_results,
            "hl": "ru" if has_cyrillic else "en",
            "gl": "ru" if has_cyrillic else "us",
            "autocorrect": True,
        },
    )
    results = []
    # answerBox/knowledgeGraph carry a direct answer — surface it first
    answer = (
        data.get("answerBox", {}).get("answer")
        or data.get("answerBox", {}).get("snippet")
        or data.get("knowledgeGraph", {}).get("description")
    )
    if answer:
        results.append({"title": "Прямой ответ Google", "url": "", "snippet": answer})
    for item in data.get("organic", [])[:max_results]:
        if item.get("link"):
            results.append({
                "title": item.get("title", ""),
                "url": item["link"],
                "snippet": item.get("snippet", ""),
            })
    return results


# ── Yandex Search API (AI Studio) ─────────────────────────────


def _search_yandex(query: str, max_results: int) -> list[dict]:
    data = _post_json(
        "https://searchapi.api.cloud.yandex.net/v2/web/search",
        {"Authorization": f"Api-Key {os.environ['YANDEX_SEARCH_API_KEY']}"},
        {
            "query": {"searchType": "SEARCH_TYPE_RU", "queryText": query},
            "responseFormat": "FORMAT_XML",
        },
        timeout=20,
    )
    raw_xml = base64.b64decode(data["rawData"]).decode("utf-8", errors="replace")
    return _parse_yandex_xml(raw_xml, max_results)


def _parse_yandex_xml(raw_xml: str, max_results: int) -> list[dict]:
    matches = re.findall(
        r"<doc[^>]*?>.*?<url>(.*?)</url>.*?<title>(.*?)</title>(?:.*?<headline>(.*?)</headline>)?",
        raw_xml,
        re.DOTALL,
    )
    results = []
    for url, title, headline in matches[:max_results]:
        title = _clean(title)
        if title and url.startswith("http"):
            results.append({"title": title, "url": url.strip(), "snippet": _clean(headline or "")})
    return results


# ── DuckDuckGo (без ключа) ────────────────────────────────────


def _resolve_url(href: str) -> str:
    """Decode DDG redirect links (//duckduckgo.com/l/?uddg=<url>) to the real URL."""
    href = href.strip()
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        qs = urllib.parse.parse_qs(parsed.query)
        target = qs.get("uddg", [""])[0]
        if target:
            return urllib.parse.unquote(target)
    return href


def _clean(text: str) -> str:
    text = re.sub(r"<.*?>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _search_html(query: str, max_results: int) -> list[dict]:
    """POST to html.duckduckgo.com — richer markup with snippets."""
    data = urllib.parse.urlencode({"q": query, "kl": ""}).encode()
    req = urllib.request.Request("https://html.duckduckgo.com/html/", data=data, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    return _parse_ddg_html(html, max_results)


def _search_lite(query: str, max_results: int) -> list[dict]:
    """GET lite.duckduckgo.com — plain table markup, useful fallback."""
    url = "https://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote_plus(query)
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    links = re.findall(r'<a[^>]*rel="nofollow"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL)
    snippets = re.findall(r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>', html, re.DOTALL)

    results = []
    for i, (href, title) in enumerate(links[:max_results]):
        url_ = _resolve_url(href)
        title_ = _clean(title)
        if not (title_ and url_.startswith("http")):
            continue
        snippet = _clean(snippets[i]) if i < len(snippets) else ""
        results.append({"title": title_, "url": url_, "snippet": snippet})
    return results


def _parse_ddg_html(html: str, max_results: int) -> list[dict]:
    """Extract title, snippet, url from DuckDuckGo HTML results."""
    results = []
    blocks = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    )

    for href, title, snippet in blocks:
        url = _resolve_url(href)
        title = _clean(title)
        snippet = _clean(snippet)
        if title and url.startswith("http"):
            results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= max_results:
            break

    return results
