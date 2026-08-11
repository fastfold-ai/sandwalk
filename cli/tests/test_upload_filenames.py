"""Server-side upload filename sanitization."""

from pathlib import Path

from agent_server.workspace.filenames import (
    sanitize_upload_filename,
    unique_upload_relative_path,
)


def test_sanitize_strips_dirs_and_spaces():
    assert (
        sanitize_upload_filename("Screenshot 2026-07-16 at 1.18.36 PM.png")
        == "Screenshot_2026-07-16_at_1.18.36_PM.png"
    )
    assert sanitize_upload_filename("../../etc/passwd") == "passwd"
    assert sanitize_upload_filename("foo/bar/baz.pdf") == "baz.pdf"


def test_sanitize_fallback_and_empty():
    assert sanitize_upload_filename("") == "upload.bin"
    assert sanitize_upload_filename("...") == "upload"
    assert sanitize_upload_filename(None) == "upload.bin"


def test_unique_upload_relative_path(tmp_path: Path):
    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads" / "shot.png").write_bytes(b"x")
    first = unique_upload_relative_path(tmp_path, "uploads", "shot.png")
    assert first == "uploads/shot-1.png"
    clean = unique_upload_relative_path(tmp_path, "uploads", "other.png")
    assert clean == "uploads/other.png"


def test_rejects_parent_dir_in_relative_dir(tmp_path: Path):
    path = unique_upload_relative_path(tmp_path, "../escape", "a.png")
    assert path == "escape/a.png" or path == "uploads/a.png" or ".." not in path
