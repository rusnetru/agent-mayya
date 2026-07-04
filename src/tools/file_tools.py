# Next Gen Agent — File Read/Write/Edit/Search tools

import json
import os
import re


def read_file(path: str) -> str:
    """Read text from a file. Returns JSON with content or error."""
    try:
        if not os.path.isfile(path):
            return json.dumps({"success": False, "error": f"File not found: {path}"})
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return json.dumps({"success": True, "content": content, "path": path, "size": len(content)})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "path": path})


def write_file(path: str, content: str) -> str:
    """Write text to a file (overwrites). Returns JSON with result."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return json.dumps({"success": True, "path": path, "written": len(content)})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "path": path})


def edit_file(path: str, find: str, replace: str) -> str:
    """Точечная правка (аналог patch из Hermes): заменить find на replace.
    find должен встречаться в файле ровно один раз — иначе ошибка с подсказкой."""
    try:
        if not os.path.isfile(path):
            return json.dumps({"success": False, "error": f"File not found: {path}"})
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        count = content.count(find)
        if count == 0:
            return json.dumps(
                {"success": False, "error": "find-фрагмент не найден в файле — проверь точное совпадение (пробелы, отступы)", "path": path},
                ensure_ascii=False,
            )
        if count > 1:
            return json.dumps(
                {"success": False, "error": f"find-фрагмент встречается {count} раз — добавь контекст, чтобы он был уникален", "path": path},
                ensure_ascii=False,
            )
        with open(path, "w", encoding="utf-8") as f:
            f.write(content.replace(find, replace))
        return json.dumps({"success": True, "path": path, "replaced": 1}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "path": path})


_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}
_TEXT_EXT = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env",
    ".html", ".css", ".js", ".ts", ".ps1", ".bat", ".sh", ".csv", ".xml", ".sql",
}


def search_files(pattern: str, path: str = ".", max_results: int = 50) -> str:
    """Поиск по содержимому файлов (аналог search_files/ripgrep из Hermes).
    Возвращает совпадения: файл, номер строки, строка."""
    try:
        max_results = int(max_results)
    except (TypeError, ValueError):
        max_results = 50
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return json.dumps({"success": False, "error": f"Bad regex: {e}"}, ensure_ascii=False)

    matches: list[dict] = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for fname in files:
            if os.path.splitext(fname)[1].lower() not in _TEXT_EXT:
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, 1):
                        if rx.search(line):
                            matches.append({"file": fpath, "line": lineno, "text": line.strip()[:200]})
                            if len(matches) >= max_results:
                                return json.dumps(
                                    {"success": True, "matches": matches, "count": len(matches), "truncated": True},
                                    ensure_ascii=False,
                                )
            except OSError:
                continue
    return json.dumps({"success": True, "matches": matches, "count": len(matches)}, ensure_ascii=False)


def list_dir(path: str = ".") -> str:
    """List files and dirs in a directory. Returns JSON."""
    try:
        entries = []
        with os.scandir(path) as it:
            for entry in it:
                entries.append(
                    {"name": entry.name, "type": "dir" if entry.is_dir() else "file", "path": entry.path}
                )
        return json.dumps({"success": True, "path": path, "entries": entries})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e), "path": path})
