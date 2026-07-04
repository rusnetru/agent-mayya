import json
import os

from src.tools.file_tools import edit_file, search_files
from src.tools.shell import run_command
from src.skills.loader import list_skills, skills_prompt


def test_edit_file_replaces_unique_fragment(tmp_path):
    p = tmp_path / "a.py"
    p.write_text("x = 1\ny = 2\n", encoding="utf-8")

    result = json.loads(edit_file(str(p), find="y = 2", replace="y = 42"))

    assert result["success"] is True
    assert p.read_text(encoding="utf-8") == "x = 1\ny = 42\n"


def test_edit_file_rejects_missing_and_ambiguous(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("dup\ndup\n", encoding="utf-8")

    missing = json.loads(edit_file(str(p), find="nope", replace="x"))
    assert missing["success"] is False and "не найден" in missing["error"]

    ambiguous = json.loads(edit_file(str(p), find="dup", replace="x"))
    assert ambiguous["success"] is False and "2 раз" in ambiguous["error"]
    assert p.read_text(encoding="utf-8") == "dup\ndup\n"  # untouched


def test_search_files_finds_matches_and_skips_venv(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("needle_here = 1\n", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "b.py").write_text("needle_here = 2\n", encoding="utf-8")

    result = json.loads(search_files("needle_here", path=str(tmp_path)))

    assert result["success"] is True
    assert result["count"] == 1
    assert result["matches"][0]["line"] == 1


def test_search_files_respects_max_results(tmp_path):
    (tmp_path / "a.txt").write_text("hit\n" * 10, encoding="utf-8")
    result = json.loads(search_files("hit", path=str(tmp_path), max_results=3))
    assert result["count"] == 3
    assert result.get("truncated") is True


def test_run_command_captures_output():
    result = json.loads(run_command("echo hello"))
    assert result["success"] is True
    assert "hello" in result["stdout"]
    assert result["returncode"] == 0


def test_run_command_reports_failure():
    result = json.loads(run_command("exit 3"))
    assert result["success"] is False
    assert result["returncode"] == 3


def test_skills_loader_lists_and_prompts(tmp_path):
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo\ndescription: тестовый навык\n---\n\n# Demo\n",
        encoding="utf-8",
    )

    skills = list_skills(str(tmp_path / "skills"))
    assert skills == [{
        "name": "demo",
        "description": "тестовый навык",
        "path": str(tmp_path / "skills" / "demo" / "SKILL.md").replace("\\", "/"),
    }]

    prompt = skills_prompt(str(tmp_path / "skills"))
    assert "demo" in prompt and "тестовый навык" in prompt
    assert skills_prompt(str(tmp_path / "empty")) == ""


def test_project_skills_are_discoverable():
    # the repo ships skills/ — the loader must see them from the project root
    if not os.path.isdir("skills"):
        return  # running from another cwd
    names = [s["name"] for s in list_skills()]
    assert "web-research" in names
    assert "self-development" in names
