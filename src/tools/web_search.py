# Next Gen Agent — Web Search tool via DuckDuckGo HTML (no API key required)

import urllib.parse
import urllib.request
import json
import re


def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo HTML (no API key). Returns JSON."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"

        req = urllib.request.Request(url, headers={"User-Agent": "NextGenAgent/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        results = _parse_ddg_html(html, max_results)
        return json.dumps({"success": True, "results": results, "query": query})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "query": query})


def _parse_ddg_html(html: str, max_results: int) -> list[dict]:
    """Extract title, snippet, url from DuckDuckGo HTML results."""
    results = []
    # Match result blocks: <a class="result__a" href="URL">TITLE</a> ... <a class="result__snippet">SNIPPET</a>
    blocks = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    )

    for url, title, snippet in blocks[:max_results]:
        title = re.sub(r"<.*?>", "", title).strip()
        snippet = re.sub(r"<.*?>", "", snippet).strip()
        if title and url.startswith("http"):
            results.append({"title": title, "url": url, "snippet": snippet})

    return results
