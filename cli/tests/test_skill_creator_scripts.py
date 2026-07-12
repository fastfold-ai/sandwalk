"""Tests for skill creator helper scripts."""

from pathlib import Path

from skills.skill_creator.scripts import init_skill, package_skill, quick_validate


def test_init_skill_title_and_invalid_name(tmp_path):
    assert init_skill._title_from_name("my-new_skill") == "My New Skill"
    code = init_skill.main(["Bad Name", "--path", str(tmp_path)])
    assert code == 2


def test_init_skill_existing_and_success(tmp_path):
    existing = tmp_path / "my-skill"
    existing.mkdir()
    assert init_skill.main(["my-skill", "--path", str(tmp_path)]) == 1

    out_code = init_skill.main(["new-skill", "--path", str(tmp_path), "--with-scripts"])
    assert out_code == 0
    skill_dir = tmp_path / "new-skill"
    assert (skill_dir / "SKILL.md").exists()
    assert (skill_dir / "references").exists()
    assert (skill_dir / "scripts").exists()


def test_package_skill_should_include_filters():
    assert package_skill._should_include(Path("files/a.txt")) is True
    assert package_skill._should_include(Path("__pycache__/x.pyc")) is False
    assert package_skill._should_include(Path("evals/run.txt")) is False


def test_package_skill_invalid_and_success(tmp_path):
    invalid = tmp_path / "not-a-skill"
    invalid.mkdir()
    assert package_skill.main([str(invalid), str(tmp_path)]) == 2

    skill = tmp_path / "fold"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nname: fold\ndescription: x\n---\n", encoding="utf-8")
    (skill / "notes.pyc").write_bytes(b"x")
    (skill / "good.txt").write_text("ok", encoding="utf-8")
    (skill / "__pycache__").mkdir()
    (skill / "__pycache__" / "x.txt").write_text("skip", encoding="utf-8")

    out_dir = tmp_path / "out"
    code = package_skill.main([str(skill), str(out_dir)])
    assert code == 0
    assert (out_dir / "fold.skill").exists()


def test_quick_validate_frontmatter_parser():
    text = """---
name: fold
description: Run fold jobs
metadata:
  x: y
---
Body
"""
    fields = quick_validate._parse_frontmatter(text)
    assert fields["name"] == "fold"
    assert fields["description"] == "Run fold jobs"


def test_quick_validate_missing_and_strict_paths(tmp_path):
    assert quick_validate.main([str(tmp_path / "missing")]) == 2

    skill = tmp_path / "skill-a"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: bad name\ndescription: TODO desc\nextra: x\n---\nTODO\n",
        encoding="utf-8",
    )
    assert quick_validate.main([str(skill)]) == 1


def test_quick_validate_success_and_strict_warning(tmp_path):
    skill = tmp_path / "skill-b"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: skill-b\ndescription: Useful helper\n---\nBody without todos.\n",
        encoding="utf-8",
    )
    assert quick_validate.main([str(skill)]) == 0

    warn_skill = tmp_path / "skill-c"
    warn_skill.mkdir()
    (warn_skill / "SKILL.md").write_text(
        "---\nname: skill-c\ndescription: TODO text\n---\nBody\n",
        encoding="utf-8",
    )
    assert quick_validate.main([str(warn_skill), "--strict"]) == 1
