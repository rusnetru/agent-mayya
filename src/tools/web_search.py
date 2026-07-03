# Next Gen Agent — Web Search tool via DuckDuckGo (no API key required)
#
# DDG's HTML results wrap every link in a redirect: //duckduckgo.com/l/?uddg=<encoded-url>&rut=...
# Those must be decoded, otherwise every result gets filtered out and the search
# looks "empty". Two endpoints are tried: html.duckduckgo.com (POST, richer
# markup) and lite.duckduckgo.com (GET, simpler markup, rarely rate-limited).

import urllib.parse
import urllib.request
import json
import re

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo (no API key). Returns JSON."""
    try:
        max_results = int(max_results)
    except (TypeError, ValueError):
        max_results = 5

    errors: list[str] = []
    for fetch in (_search_html, _search_lite):
        try:
            results = fetch(query, max_results)
            if results:
                return json.dumps(
                    {"success": True, "results": results, "query": query},
                    ensure_ascii=False,
                )
        except Exception as e:
            errors.append(f"{fetch.__name__}: {e}")

    return json.dumps(
        {
            "success": False,
            "error": "; ".join(errors) or "no results from any endpoint",
            "results": [],
            "query": query,
        },
        ensure_ascii=False,
    )


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
