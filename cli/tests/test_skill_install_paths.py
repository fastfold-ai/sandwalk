"""Skill source parsing and local install without cloning a repository."""

from __future__ import annotations

import subprocess
from pathlib import Path

from agent.skills import install as skills


def test_detect_and_parse(tmp_path):
    assert skills.detect_source_type("") == "name"
    assert skills.detect_source_type("fold") == "name"
    local = tmp_path / "skill"
    local.mkdir()
    assert skills.detect_source_type(str(local)) == "local"
    assert skills.detect_source_type("https://github.com/acme/fold.git") == "github"
    assert skills.detect_source_type("acme/fold@skills/binder") == "shorthand"
    url, ref, sub = skills._parse_github("acme/fold.git@skills/binder")
    assert url.endswith("/fold.git") and ref is None and sub == "skills/binder"
    url, ref, sub = skills._parse_github("https://github.com/acme/fold/tree/v1/skills/binder")
    assert ref == "v1" and sub == "skills/binder"
    assert skills._parse_github("git@github.com:acme/fold.git")[0].endswith("fold.git")
    assert skills._owner_repo_from_clone_url("https://github.com/acme/fold.git") == "acme/fold"
    assert skills._owner_repo_from_clone_url("https://example.com/nope") is None
    err = subprocess.CalledProcessError(1, ["git"], output=b"", stderr="x" * 250)
    assert skills._format_git_error(err).endswith("...")
    blank = subprocess.CalledProcessError(1, ["git"], stderr="   ")
    assert skills._format_git_error(blank) == "git clone failed"
    target, names, whole = skills._npx_target("acme/fold@binder")
    assert "acme/fold" in target
    assert skills._noninteractive_git_env()["GIT_TERMINAL_PROMPT"] == "0"


def test_resolve_copy_and_local_install(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "skills" / "binder").mkdir(parents=True)
    (root / "skills" / "binder" / "SKILL.md").write_text("# binder\n")
    assert skills._resolve_skill_dirs(root, "missing")[0].name == "binder"
    direct = tmp_path / "one"
    direct.mkdir()
    (direct / "SKILL.md").write_text("# one\n")
    assert skills._resolve_skill_dirs(direct, None) == [direct]

    dest = tmp_path / "installed"
    names = skills._copy_skill_dirs([direct], dest, "local", "abc", "v1")
    assert names == ["one"]
    assert (dest / "one" / "SKILL.md").is_file()
    names = skills._copy_skill_dirs([direct], dest, "local", None)
    assert names == ["one"]

    missing = skills._install_local(str(tmp_path / "gone"), dest)
    assert missing["ok"] is False
    empty = tmp_path / "empty"
    empty.mkdir()
    assert skills._install_local(str(empty), dest)["ok"] is False
    installed = skills._install_local(str(direct), dest)
    assert installed["ok"] is True and installed["via"] == "local"

    archive = tmp_path / "pack.zip"
    import zipfile

    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("binder/SKILL.md", "# binder\n")
    packed = skills._install_local(str(archive), dest)
    assert packed["via"] == "local-archive"

    assert skills.install_skill("", dest=dest)["ok"] is False
    monkeypatch.setattr(skills._skills, "_resolve_name_to_source", lambda name: None)
    missing_name = skills.install_skill("not-a-catalog-skill", dest=dest)
    assert missing_name["ok"] is False
