"""Skills loader — система навыков, перенесённая из Hermes Agent.

Навык = папка `skills/<name>/` с файлом SKILL.md (front matter: name, description
+ тело с инструкциями). В system prompt попадает только список имён и описаний;
полный текст навыка агент читает сам через read_file, когда навык подходит к задаче.
"""

from __future__ import annotations

import os
import re

DEFAULT_SKILLS_DIR = "skills"


def list_skills(base_dir: str = DEFAULT_SKILLS_DIR) -> list[dict]:
    """Return [{name, description, path}] for every skills/<name>/SKILL.md."""
    skills: list[dict] = []
    if not os.path.isdir(base_dir):
        return skills
    for name in sorted(os.listdir(base_dir)):
        skill_md = os.path.join(base_dir, name, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue
        skills.append({
            "name": name,
            "description": _parse_description(skill_md),
            "path": skill_md.replace("\\", "/"),
        })
    return skills


def skills_prompt(base_dir: str = DEFAULT_SKILLS_DIR) -> str:
    """System-prompt block listing available skills (empty string if none)."""
    skills = list_skills(base_dir)
    if not skills:
        return ""
    lines = [
        "НАВЫКИ: у тебя есть папка навыков. Если задача подходит под навык — "
        "СНАЧАЛА прочитай его файл через read_file и следуй инструкциям из него:",
    ]
    for s in skills:
        desc = f" — {s['description']}" if s["description"] else ""
        lines.append(f"- {s['name']}{desc} (файл: {s['path']})")
    return "\n".join(lines)


def _parse_description(path: str) -> str:
    """Pull `description:` out of the SKILL.md front matter."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            head = f.read(2000)
    except OSError:
        return ""
    m = re.search(r"^description:\s*[\"']?(.+?)[\"']?\s*$", head, re.MULTILINE)
    return m.group(1).strip() if m else ""
