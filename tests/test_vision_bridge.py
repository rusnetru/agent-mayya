"""
Тесты MCP-сервера компьютерного зрения (Vision-bridge).
Проверяет три бэкенда: UIA, OCR, Browser.

Запуск: pytest tests/test_vision_bridge.py -v
Требования: Tesseract OCR, Chrome (для браузерных тестов).
"""

import json
import os
import sys

import pytest
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.mcp.client import MCPManager


@pytest.fixture(scope="module")
def vision_bridge():
    """Подключаемся к vision-bridge MCP-серверу (один раз на модуль)."""
    manager = MCPManager("mcp.json")
    manager.connect()
    if "vision-bridge" not in manager.servers:
        pytest.skip("vision-bridge MCP-сервер не найден в mcp.json")
    vb = manager.servers["vision-bridge"]
    yield vb
    manager.close()


def _call(vb, tool: str, **kwargs) -> dict:
    """Вызвать инструмент и распарсить JSON-ответ."""
    raw = vb.call_tool(tool, kwargs)
    return json.loads(raw)


# ── UIA ────────────────────────────────────────────────────

def test_capture_active_window(vision_bridge):
    """capture() активного окна через UIA."""
    data = _call(vision_bridge, "capture", target="", mode="auto")
    assert data["ok"] is True
    assert data.get("method_used") in ("uia", "ocr")
    assert isinstance(data.get("elements"), list)
    assert len(data["elements"]) > 0


def test_find_element(vision_bridge):
    """find() ищет элемент по подстроке."""
    data = _call(vision_bridge, "find", query=" ", mode="auto")
    assert data["ok"] is True


def test_wait_for_timeout(vision_bridge):
    """wait_for() для гарантированно отсутствующего элемента."""
    data = _call(
        vision_bridge,
        "wait_for",
        query="zzz_no_such_element_abc123",
        timeout_s=2.0,
    )
    assert data["ok"] is True
    assert data.get("found") is None or data.get("found") is False


# ── OCR ────────────────────────────────────────────────────

def test_capture_ocr_mode(vision_bridge):
    """capture() в принудительном OCR-режиме."""
    data = _call(vision_bridge, "capture", target="", mode="ocr")
    assert data["ok"] is True
    assert data.get("method_used") == "ocr"
    assert isinstance(data.get("text"), str)


# ── Browser ────────────────────────────────────────────────

def test_browser_stealth_lifecycle(vision_bridge):
    """Открытие stealth-браузера, capture, закрытие."""
    data = _call(vision_bridge, "browser_open", mode="stealth")
    assert data["ok"] is True
    assert data.get("mode") == "stealth"

    data = _call(vision_bridge, "capture", target="browser", mode="browser")
    assert data["ok"] is True
    assert isinstance(data.get("elements"), list)

    data = _call(vision_bridge, "browser_close")
    assert data["ok"] is True
