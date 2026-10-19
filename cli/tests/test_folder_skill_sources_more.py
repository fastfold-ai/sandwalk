"""Coverage for project-folder files and staged skill source directories."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.deepagents_runtime import skills_sources
from agent_server.project_folder_listing import (
    delete_project_folder_file,
    list_project_folder_files,
    read_project_folder_file,
    rename_project_folder_file,
    use_project_folder_in_chat,
)


def test_project_folder_list_read_and_mutate(tmp_path) -> None:
    with pytest.raises(ValueError, match="not a directory"):
        list_project_folder_files(str(tmp_path / "missing"))

    root = tmp_path / "proj"
    nested = root / "notes"
    skipped = root / ".git"
    nested.mkdir(parents=True)
    skipped.mkdir()
    (nested / "a.txt").write_text("hello", encoding="utf-8")
    (nested / ".hidden").write_text("no", encoding="utf-8")
    (root / "pic.bin").write_bytes(b"\xff\xfe binary")
    (skipped / "secret.txt").write_text("nope", encoding="utf-8")

    listing = list_project_folder_files(str(root))
    names = {item.name for item in listing.data}
    assert names == {"a.txt", "pic.bin"}

    text = read_project_folder_file(str(root), "./notes/a.txt")
    assert text.encoding == "text"
    assert text.content == "hello"
    binary = read_project_folder_file(str(root), "pic.bin")
    assert binary.encoding == "base64"

    with pytest.raises(ValueError, match="Invalid project folder path"):
        read_project_folder_file(str(root), "../etc/passwd")
    with pytest.raises(FileNotFoundError):
        read_project_folder_file(str(root), "missing.txt")

    renamed = rename_project_folder_file(str(root), "notes/a.txt", "b.txt")
    assert renamed.name == "b.txt"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "agent_server.project_folder_listing.sanitize_upload_filename",
        lambda _name: "",
    )
    try:
        with pytest.raises(ValueError, match="Invalid file name"):
            rename_project_folder_file(str(root), "notes/b.txt", "nope")
    finally:
        monkeypatch.undo()
    (nested / "taken.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="already exists"):
        rename_project_folder_file(str(root), "notes/b.txt", "taken.txt")

    delete_project_folder_file(str(root), "notes/b.txt")
    assert not (nested / "b.txt").exists()

    class Service:
        def create_session(self, **kwargs):
            return SimpleNamespace(id="sess")

        def ensure_workspace(self, session_id):
            assert session_id == "sess"

    with pytest.raises(ValueError, match="At least one path"):
        use_project_folder_in_chat(
            agent_service=Service(),
            project_id="p",
            paths=[],
            folder_path=str(root),
        )
    started = use_project_folder_in_chat(
        agent_service=Service(),
        project_id="p",
        paths=["notes/taken.txt"],
        folder_path=str(root),
        title=None,
    )
    assert started.session_id == "sess"
    assert any(path.endswith("taken.txt") for path in started.paths)


def test_skill_source_staging(tmp_path, monkeypatch) -> None:
    skills_sources.invalidate_skill_sources_cache()
    assert skills_sources.skill_source_dirs_for_names([" ", ""]) == []

    missing = tmp_path / "nope"
    present = tmp_path / "bundled"
    present.mkdir()
    monkeypatch.setattr(
        "agent.skills.BUNDLED_SKILLS_DIR",
        missing,
    )
    monkeypatch.setattr("agent.skills.NPX_SKILLS_DIR", present)
    monkeypatch.setattr("agent.skills.GLOBAL_SKILLS_DIR", tmp_path / "also-missing")
    found = skills_sources.skill_source_dirs()
    assert str(present) in found

    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\n", encoding="utf-8")

    def info(name):
        if name != "demo":
            return None
        return SimpleNamespace(directory=skill_dir)

    monkeypatch.setattr("agent.skills.skill_info", info)
    staged = skills_sources.skill_source_dirs_for_names(["demo", "missing"])
    assert staged and Path(staged[0], "demo").exists()
    again = skills_sources.skill_source_dirs_for_names(["demo"])
    assert again == staged

    monkeypatch.setattr("agent.skills.list_skills", lambda enabled_only=True: [])
    assert skills_sources.resolve_skill_source_dirs([]) == []
    assert skills_sources.resolve_skill_source_dirs(None) == []

    link = tmp_path / "link"
    link.symlink_to(skill_dir, target_is_directory=True)
    skills_sources._link_or_copy(skill_dir, link)
    assert link.is_symlink()
