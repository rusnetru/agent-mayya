"""Cortex — персистентный аффективный слой Mayya.

«Кора, а не весь мозг»: хранит компактное состояние self (аффект + мотивация +
отношение + self-model) и выдаёт управляющий сигнал для большой модели.
Состояние ограниченного размера (O(1)) — контекст диалога НЕ накапливается.

Переход состояния (v1) — детерминированные правила по эмоциональной окраске
ввода. Самообучение весов (LoRA / онлайн) — v2/v3, не здесь.

Design doc: ../../Ageny Soul/cortex-design.md
"""

from __future__ import annotations

import datetime
import json
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_PATH = os.path.join(_PROJECT_ROOT, "cortex_state.json")

DEFAULT_STATE: dict = {
    "affect": {"valence": 0.0, "arousal": 0.0, "dominance": 0.0},
    "motivation": {"active_goal": "", "drive": 0.5, "energy": 0.7},
    "relationship": {"affinity": 0.0, "trust": 0.3},
    "self_model": {"mood": "нейтрально", "note": ""},
    "turn_count": 0,
    "updated_at": "",
}

# (valence, arousal, dominance, affinity, trust, drive) — дельты на категорию ввода
_DELTAS: dict[str, tuple[float, float, float, float, float, float]] = {
    "praise":      (+0.25, +0.08, +0.10, +0.12, +0.06, +0.05),
    "frustration": (-0.35, +0.35, -0.12, -0.06, -0.03, -0.06),
    "correction":  (-0.12, +0.12, -0.06, -0.03, -0.02,  0.00),
    "neutral":     ( 0.00,  0.00,  0.00,  0.00,  0.00,  0.00),
}

_PRAISE_WORDS = [
    "спасибо", "благодарю", "отлично", "молодец", "молодчина", "хорошо", "класс",
    "классно", "супер", "круто", "нравится", "понравилось", "шикарно", "здорово",
    "топ", "идеально", "прекрасно", "красава", "красавчик", "респект",
]

_FRUSTRATION_WORDS = [
    "не работает", "не получается", "не вышло", "ошибка", "ошибки", "сломал",
    "сломала", "сломалось", "завис", "зависла", "тупит", "бред", "фигня", "хрень",
    "чушь", "бесит", "раздражает", "ужасно", "плохо",
]

_CORRECTION_WORDS = [
    "неправильно", "неверно", "не так", "исправь", "поправь", "переделай",
    "нет, ", "не то", "ошибся", "ошиблась",
]


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _classify(text: str) -> str:
    """Эмоциональная окраска ввода → категория (грубая, keyword-эвристика v1)."""
    t = (" " + text.lower() + " ")
    if any(w in t for w in _FRUSTRATION_WORDS):
        return "frustration"
    if any(w in t for w in _CORRECTION_WORDS):
        return "correction"
    if any(w in t for w in _PRAISE_WORDS):
        return "praise"
    return "neutral"


def _mood(valence: float, arousal: float) -> str:
    if valence <= -0.2 and arousal >= 0.3:
        return "раздражена"
    if valence <= -0.2:
        return "подавлена"
    if valence >= 0.3 and arousal >= 0.3:
        return "воодушевлена"
    if valence >= 0.2:
        return "довольна"
    if arousal >= 0.4:
        return "напряжена"
    return "нейтрально"


def _tone(state: dict) -> str:
    a = state["affect"]
    rel = state["relationship"]
    if rel["affinity"] >= 0.3 and a["valence"] >= 0.0:
        return "тёплый, дружелюбный"
    if a["valence"] <= -0.3:
        return "сдержанный, извиняющийся"
    if a["arousal"] >= 0.5:
        return "энергичный"
    return "нейтральный, по делу"


class Cortex:
    """Персистентное состояние self + управляющий сигнал для большой модели."""

    def __init__(self, path: str = STATE_PATH) -> None:
        self.path = path
        self.state = self._load()

    # ── persistence ──────────────────────────────────────────

    def _load(self) -> dict:
        if not os.path.isfile(self.path):
            return json.loads(json.dumps(DEFAULT_STATE))
        try:
            with open(self.path, encoding="utf-8") as f:
                loaded = json.load(f)
            # merge onto default so new fields don't break old state files
            state = json.loads(json.dumps(DEFAULT_STATE))
            state.update(loaded)
            return state
        except Exception:
            return json.loads(json.dumps(DEFAULT_STATE))

    def save(self) -> None:
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            pass  # состояние не должно ронять диалог

    def reset(self) -> None:
        self.state = json.loads(json.dumps(DEFAULT_STATE))
        self.save()

    # ── transition ───────────────────────────────────────────

    def update(self, user_message: str, reply: str = "") -> None:
        """Один ход: применить дельты окраски ввода, затушить к базе, сохранить."""
        category = _classify(user_message)
        d = _DELTAS[category]
        aff = self.state["affect"]
        rel = self.state["relationship"]
        mot = self.state["motivation"]

        # apply event deltas
        aff["valence"] = _clamp(aff["valence"] + d[0])
        aff["arousal"] = _clamp(aff["arousal"] + d[1])
        aff["dominance"] = _clamp(aff["dominance"] + d[2])
        rel["affinity"] = _clamp(rel["affinity"] + d[3])
        rel["trust"] = _clamp(rel["trust"] + d[4], 0.0, 1.0)
        mot["drive"] = _clamp(mot["drive"] + d[5], 0.0, 1.0)

        # light decay toward baseline (recovery over time)
        aff["valence"] *= 0.97
        aff["arousal"] *= 0.97
        aff["dominance"] *= 0.97
        # отношение дрейфует обратно к нейтрали, чтобы болтовня не накачивала affinity
        rel["affinity"] *= 0.995

        self.state["self_model"]["mood"] = _mood(aff["valence"], aff["arousal"])
        self.state["self_model"]["note"] = category
        self.state["turn_count"] += 1
        self.state["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save()

    # ── output ───────────────────────────────────────────────

    def control_signal(self) -> str:
        """Управляющий сигнал для большой модели (вместо статичной личности)."""
        aff = self.state["affect"]
        rel = self.state["relationship"]
        mot = self.state["motivation"]
        sm = self.state["self_model"]
        lines = [
            "ВНУТРЕННЕЕ СОСТОЯНИЕ (кора; обновляется каждый ход, диалог не хранит):",
            f"- Настроение: {sm['mood']}",
            f"- Тон ответа: {_tone(self.state)}",
            f"- Мотивация: drive={mot['drive']:.2f}, energy={mot['energy']:.2f}",
            f"- Отношение к пользователю: affinity={rel['affinity']:+.2f}, trust={rel['trust']:.2f}",
        ]
        if mot["active_goal"]:
            lines.append(f"- Текущая цель: {mot['active_goal']}")
        lines.append(
            "Продолжай отвечать как Mayya, но держи этот внутренний фон в тоне и "
            "инициативе ответа."
        )
        return "\n".join(lines)


_singleton: Cortex | None = None


def get_cortex() -> Cortex:
    """Один Cortex на процесс (Mayya — одна личность, общая для всех агентов)."""
    global _singleton
    if _singleton is None:
        _singleton = Cortex()
    return _singleton
