"""Bulk tests for agent/skills.py discovery, install, and prompt building."""

from pathlib import Path

import pytest

from agent import skills as skills_mod


@pytest.fixture(autouse=True)
def _isolate_skill_dirs(monkeypatch, tmp_path):
    root = tmp_path / "cfg"
    monkeypatch.setattr(skills_mod, "CONFIG_DIR", root)
    monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", root / "skills")
    monkeypatch.setattr(skills_mod, "NPX_INSTALL_ROOT", root)
    monkeypatch.setattr(skills_mod, "NPX_SKILLS_DIR", root / ".claude" / "skills")


def _write_skill(base: Path, name: str, description: str = "", body: str = "Body.", scripts: bool = False):
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    fm = [f"name: {name}"]
    if description:
        fm.append(f"description: {description}")
    (d / "SKILL.md").write_text(
        "---\n" + "\n".join(fm) + f"\n---\n\n{body}\n",
        encoding="utf-8",
    )
    if scripts:
        (d / "scripts").mkdir()
        (d / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
    return d


class TestListSkills:
    def test_list_skills_sorted(self, tmp_path, monkeypatch):
        bundled = tmp_path / "bundled"
        _write_skill(bundled, "zebra", "Z skill")
        _write_skill(bundled, "alpha", "A skill")
        monkeypatch.setattr(skills_mod, "BUNDLED_SKILLS_DIR", bundled)

        names = [s.name for s in skills_mod.list_skills(project_root=tmp_path / "proj")]
        assert names == ["alpha", "zebra"]

    def test_installed_skill_names_matches_iter(self, tmp_path, monkeypatch):
        bundled = tmp_path / "bundled"
        _write_skill(bundled, "fold", "Fold")
        monkeypatch.setattr(skills_mod, "BUNDLED_SKILLS_DIR", bundled)
        assert skills_mod.installed_skill_names(project_root=tmp_path) == ["fold"]


class TestProjectTier:
    def test_scan_project_lock_gated(self, tmp_path):
        proj = tmp_path / "proj"
        claude = proj / ".claude" / "skills"
        _write_skill(claude, "life", "Life sciences")
        (proj / "skills-lock.json").write_text(
            '{"version":1,"skills":{"life":{"source":"anthropics/life-sciences"}}}',
            encoding="utf-8",
        )
        merged = skills_mod.iter_skills(project_root=proj)
        assert "life" in merged
        assert merged["life"].source.startswith("project")


class TestInstallPaths:
    def test_install_local_pack_multiple(self, tmp_path):
        src = tmp_path / "pack"
        skills_root = src / "skills"
        _write_skill(skills_root, "one", "One")
        _write_skill(skills_root, "two", "Two")
        dest = tmp_path / "global"
        result = skills_mod.install_skill(str(skills_root), dest=dest)
        assert result["ok"] is True
        assert set(result["installed"]) == {"one", "two"}
        assert (dest / "one" / "SKILL.md").exists()

    def test_install_empty_source(self):
        result = skills_mod.install_skill("")
        assert result["ok"] is False

    def test_resolve_skill_dirs_single_at_root(self, tmp_path):
        base = _write_skill(tmp_path, "solo", "Solo")
        found = skills_mod._resolve_skill_dirs(base, None)
        assert found == [base]


class TestBuildSkillsPrompt:
    def test_build_skills_prompt_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(skills_mod, "BUNDLED_SKILLS_DIR", tmp_path / "empty")
        monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", tmp_path / "noglobal")
        assert skills_mod.build_skills_prompt(project_root=tmp_path) == ""

    def test_build_skills_prompt_no_scripts_message(self, tmp_path, monkeypatch):
        bundled = tmp_path / "bundled"
        _write_skill(bundled, "docs_only", "Docs only skill")
        monkeypatch.setattr(skills_mod, "BUNDLED_SKILLS_DIR", bundled)
        prompt = skills_mod.build_skills_prompt(
            project_root=tmp_path, user_request="docs only skill"
        )
        assert "no `scripts/` directory" in prompt

    def test_build_skills_prompt_with_scripts(self, tmp_path, monkeypatch):
        global_dir = tmp_path / "global"
        _write_skill(global_dir, "runner", "Runner", body="Use `python scripts/run.py`.", scripts=True)
        monkeypatch.setattr(skills_mod, "BUNDLED_SKILLS_DIR", tmp_path / "nobundled")
        monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", global_dir)
        prompt = skills_mod.build_skills_prompt(
            project_root=tmp_path, user_request="runner"
        )
        assert "runner" in prompt
        assert "/scripts/run.py" in prompt


class TestSkillInfoPaths:
    def test_skill_info_lookup(self, tmp_path, monkeypatch):
        bundled = tmp_path / "bundled"
        d = _write_skill(bundled, "fold", "Folding")
        monkeypatch.setattr(skills_mod, "BUNDLED_SKILLS_DIR", bundled)
        info = skills_mod.skill_info("fold", project_root=tmp_path)
        assert info is not None
        assert info.path == d / "SKILL.md"
        assert info.directory == d

    def test_user_installed_skill_names_excludes_bundled_only(self, tmp_path, monkeypatch):
        bundled = tmp_path / "bundled"
        global_dir = tmp_path / "global"
        _write_skill(bundled, "bundled_only", "Bundled")
        _write_skill(global_dir, "user_skill", "User")
        monkeypatch.setattr(skills_mod, "BUNDLED_SKILLS_DIR", bundled)
        monkeypatch.setattr(skills_mod, "GLOBAL_SKILLS_DIR", global_dir)
        names = skills_mod.user_installed_skill_names(project_root=tmp_path)
        assert names == ["user_skill"]
