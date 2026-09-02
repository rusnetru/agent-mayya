"""Tests for the cortex affective layer (v1)."""

import pytest

from src.cortex.cortex import Cortex, _classify


@pytest.fixture
def cortex(tmp_path):
    return Cortex(path=str(tmp_path / "cortex_state.json"))


# ── classification ───────────────────────────────────────────

def test_classify_praise():
    assert _classify("Спасибо, отлично сработано!") == "praise"


def test_classify_frustration():
    assert _classify("У тебя ошибка, не работает") == "frustration"


def test_classify_correction():
    assert _classify("Нет, это неправильно, исправь") == "correction"


def test_classify_neutral():
    assert _classify("Расскажи про PEPA") == "neutral"


# ── transition ──────────────────────────────────────────────

def test_praise_raises_valence_and_affinity(cortex):
    cortex.update("Спасибо, молодец!")
    assert cortex.state["affect"]["valence"] > 0
    assert cortex.state["relationship"]["affinity"] > 0
    assert cortex.state["turn_count"] == 1


def test_frustration_lowers_valence(cortex):
    cortex.update("Это бред, всё сломалось")
    assert cortex.state["affect"]["valence"] < 0
    assert cortex.state["affect"]["arousal"] > 0


def test_values_clamped(cortex):
    for _ in range(50):
        cortex.update("Спасибо, круто!")  # keep praising
    assert cortex.state["relationship"]["affinity"] <= 1.0
    assert cortex.state["relationship"]["trust"] <= 1.0


# ── persistence & output ────────────────────────────────────

def test_state_persists(tmp_path):
    path = str(tmp_path / "c.json")
    a = Cortex(path=path)
    a.update("Спасибо, круто!")
    b = Cortex(path=path)  # reload from disk
    assert b.state["turn_count"] == 1
    assert b.state["affect"]["valence"] > 0


def test_control_signal_renders(cortex):
    cortex.update("Привет, как дела?")
    sig = cortex.control_signal()
    assert "ВНУТРЕННЕЕ СОСТОЯНИЕ" in sig
    assert "Настроение" in sig
    assert "Тон ответа" in sig


def test_reset(cortex):
    cortex.update("Спасибо, отлично!")
    cortex.reset()
    assert cortex.state["turn_count"] == 0
    assert cortex.state["affect"]["valence"] == 0.0
