# Next Gen Agent — Web Extract tool (fetch page content)
# Использует urllib для загрузки страниц + html2text для конвертации в Markdown
# Если html2text нет — отдаёт plain text через regex

import json
import re
import urllib.request
import urllib.error


def _html_to_text(html: str, max_chars: int = 8000) -> str:
    """Convert HTML to readable text. Falls back to regex if html2text unavailable."""
    try:
        import html2text  # type: ignore[import-untyped]
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0
        text = h.handle(html)
    except ImportError:
        # Fallback: strip tags
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)

    return text.strip()[:max_chars]


def web_extract(url: str, max_chars: int = 8000) -> str:
    """Fetch a web page and return its text content. Returns JSON."""
    if not url.startswith(("http://", "https://")):
        return json.dumps({"success": False, "error": "URL must start with http:// or https://", "url": url})

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 NextGenAgent/1.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            # Handle encoding
            content_type = resp.headers.get("Content-Type", "")
            charset = "utf-8"
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].split(";")[0].strip()

            html = resp.read()
            # Try declared charset first, fall back to utf-8
            for enc in [charset, "utf-8", "windows-1251", "latin-1"]:
                try:
                    html = html.decode(enc)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue

            text = _html_to_text(html, max_chars)
            return json.dumps({
                "success": True,
                "url": url,
                "content": text,
                "length": len(text),
                "content_type": content_type,
            }, ensure_ascii=False)
    except urllib.error.HTTPError as e:
        return json.dumps({"success": False, "error": f"HTTP {e.code}: {e.reason}", "url": url})
    except urllib.error.URLError as e:
        return json.dumps({"success": False, "error": f"Connection error: {e.reason}", "url": url})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "url": url})
