"""Tests for CLI image attach helpers and mention path preservation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ui.terminal.attachments import (
    attach_from_pasted_text,
    attach_image_file,
    expand_image_chips,
    parse_pasted_filepath,
    rewrite_loose_image_paths,
    save_image_bytes,
    split_pasted_image_path,
)
from ui.terminal.clipboard_image import read_clipboard_image
from ui.terminal.key_bindings import _build_key_bindings
from ui.terminal.mentions import extract_mentions


def test_save_image_bytes_writes_uploads(tmp_path: Path):
    rel = save_image_bytes(tmp_path, b"\x89PNG\r\n", mime="image/png", stem="clipboard")
    assert rel.startswith("uploads/")
    assert rel.endswith(".png")
    assert (tmp_path / rel).read_bytes() == b"\x89PNG\r\n"


def test_attach_image_file_copies_into_uploads(tmp_path: Path):
    src = tmp_path / "shot.png"
    src.write_bytes(b"png-bytes")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    rel = attach_image_file(workspace, src)
    assert rel.startswith("uploads/")
    assert (workspace / rel).read_bytes() == b"png-bytes"


def test_parse_pasted_filepath_accepts_image(tmp_path: Path):
    img = tmp_path / "a.png"
    img.write_bytes(b"x")
    assert parse_pasted_filepath(str(img)) == img.resolve()
    assert parse_pasted_filepath(f"file://{img}") == img.resolve()
    assert parse_pasted_filepath("not a path") is None
    assert parse_pasted_filepath("hello\nworld") is None


def test_split_pasted_image_path_with_trailing_text(tmp_path: Path):
    img = tmp_path / "mmm.png"
    img.write_bytes(b"x")
    path, rest = split_pasted_image_path(f"{img} what's this?")
    assert path == img.resolve()
    assert rest == "what's this?"


def test_attach_from_pasted_text(tmp_path: Path):
    img = tmp_path / "drop.jpg"
    img.write_bytes(b"jpeg")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    result = attach_from_pasted_text(workspace, f"{img} describe please")
    assert result is not None
    rel, rest = result
    assert rel.endswith(".jpg")
    assert rest == "describe please"
    assert (workspace / rel).is_file()


def test_expand_image_chips():
    assert expand_image_chips("[Image 1] what?", {1: "uploads/a.png"}) == "@uploads/a.png what?"


def test_rewrite_loose_image_paths(tmp_path: Path):
    img = tmp_path / "loose.png"
    img.write_bytes(b"x")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    text, mapping = rewrite_loose_image_paths(f"{img} hi", workspace, {})
    assert "[Image 1]" in text
    assert 1 in mapping
    assert mapping[1].startswith("uploads/")


def test_read_clipboard_image_macos_mocked(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("ui.terminal.clipboard_image.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        "ui.terminal.clipboard_image.tempfile.gettempdir",
        lambda: str(tmp_path),
    )
    monkeypatch.setattr("ui.terminal.clipboard_image.os.getpid", lambda: 42)

    dest = tmp_path / "sandwalk-clipboard-42.png"

    def run_and_write(cmd, **kwargs):
        dest.write_bytes(b"clipboard-png")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr("ui.terminal.clipboard_image.subprocess.run", run_and_write)
    result = read_clipboard_image()
    assert result == (b"clipboard-png", "image/png")
    assert not dest.exists()  # cleaned up


def test_extract_mentions_preserves_upload_paths():
    query, tools, datasets, workflows = extract_mentions(
        "describe @uploads/20260101-clip.png with @target.coessentiality @depmap"
    )
    assert "@uploads/20260101-clip.png" in query
    assert "target.coessentiality" in tools
    assert "depmap" in datasets
    assert "target.coessentiality" not in query
    assert "@depmap" not in query


def test_extract_mentions_keeps_path_when_only_media():
    query, tools, datasets, workflows = extract_mentions(
        "what is in @uploads/foo.png?"
    )
    assert query == "what is in @uploads/foo.png?"
    assert tools == []
    assert datasets == []


def test_bracketed_paste_attaches_image_path(tmp_path: Path):
    img = tmp_path / "paste.png"
    img.write_bytes(b"png")
    workspace = tmp_path / "ws"
    workspace.mkdir()

    terminal = SimpleNamespace(
        _attach_count=0,
        _attach_map={},
        console=SimpleNamespace(print=MagicMock()),
        agent=SimpleNamespace(ensure_workspace_path=lambda: str(workspace)),
    )
    kb = _build_key_bindings(terminal)

    class Buf:
        def __init__(self):
            self.text = "look at"
            self.inserted = []

        @property
        def document(self):
            return SimpleNamespace(text_before_cursor=self.text)

        def insert_text(self, text):
            self.inserted.append(text)
            self.text += text

    buf = Buf()
    event = SimpleNamespace(
        data=f"{img} what's this?",
        app=SimpleNamespace(current_buffer=buf, invalidate=MagicMock()),
    )
    handler = next(b.handler for b in kb.bindings if b.handler.__name__ == "_bracketed_paste")
    handler(event)
    assert any("[Image 1]" in t for t in buf.inserted)
    assert any("what's this?" in t for t in buf.inserted)
    assert terminal._attach_count == 1
    assert terminal._attach_map[1].startswith("uploads/")


def test_ctrl_v_falls_back_to_clipboard_text_paste(tmp_path: Path):
    terminal = SimpleNamespace(
        _attach_count=0,
        _attach_map={},
        console=SimpleNamespace(print=MagicMock()),
        agent=SimpleNamespace(ensure_workspace_path=lambda: str(tmp_path)),
    )
    kb = _build_key_bindings(terminal)
    clip_data = SimpleNamespace(text="hello from clipboard")

    class Buf:
        def __init__(self):
            self.text = ""
            self.pasted = None

        @property
        def document(self):
            return SimpleNamespace(text_before_cursor=self.text)

        def insert_text(self, text):
            self.text += text

        def paste_clipboard_data(self, data):
            self.pasted = data

    buf = Buf()
    event = SimpleNamespace(
        app=SimpleNamespace(
            current_buffer=buf,
            clipboard=SimpleNamespace(get_data=lambda: clip_data),
            invalidate=MagicMock(),
        )
    )
    with patch("ui.terminal.attachments.attach_from_clipboard", return_value=None):
        handler = next(b.handler for b in kb.bindings if b.handler.__name__ == "_paste_or_attach_image")
        handler(event)
    assert buf.pasted is clip_data
