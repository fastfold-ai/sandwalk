"""Detect which coding-agent CLI is in the foreground of a PTY."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

from agent.external_agents import detect


def test_binary_lookup_and_installed_rows(monkeypatch):
    monkeypatch.setattr(detect.shutil, "which", lambda name: f"/bin/{name}" if name == "claude" else None)
    assert detect.binary_for("claude") == "/bin/claude"
    assert detect.binary_for("not-an-agent") is None
    rows = {row["kind"]: row for row in detect.installed_agents()}
    assert rows["claude"]["installed"] is True
    assert rows["codex"]["installed"] is False


def test_proc_and_ps_group_scans(monkeypatch, tmp_path):
    proc = tmp_path / "proc"
    (proc / "12").mkdir(parents=True)
    (proc / "12" / "stat").write_text("12 (claude) S 1 99 9 0 0\n", encoding="utf-8")
    (proc / "12" / "cmdline").write_bytes(b"claude\x00--print")
    (proc / "nope").mkdir()
    (proc / "7").mkdir()
    (proc / "7" / "stat").write_text("bad", encoding="utf-8")
    monkeypatch.setattr(detect, "Path", lambda p="/proc": proc if str(p) == "/proc" else detect.Path)
    # The function constructs Path("/proc") via the imported Path. Patch the name in the module.
    import pathlib

    real = pathlib.Path

    def fake_path(value, *args, **kwargs):
        if value == "/proc":
            return proc
        return real(value, *args, **kwargs)

    monkeypatch.setattr(detect, "Path", fake_path)
    text = detect._proc_in_group(99)
    assert text is not None and "claude" in text
    assert detect._proc_in_group(1) is None

    monkeypatch.setattr(detect, "_proc_in_group", lambda pgid: None)

    def ps(cmd, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout="10 9 codex codex exec\n11 3 zsh -l\nbad row\n",
        )

    monkeypatch.setattr(detect.subprocess, "run", ps)
    assert "codex" in (detect._ps_in_group(9) or "")
    monkeypatch.setattr(
        detect.subprocess,
        "run",
        lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired("ps", 1)),
    )
    assert detect._ps_in_group(9) is None


def test_argv_kind_and_foreground(monkeypatch, tmp_path):
    assert detect._argv_kind("") is None
    assert detect._argv_kind("/usr/bin/node /opt/opencode/bin/opencode") == "opencode"
    assert detect._argv_kind("python3 -I -c 'hermes-agent'") == "hermes"
    assert detect._argv_kind("python3 -c 'print(1)'") is None

    monkeypatch.setattr(detect.os, "tcgetpgrp", lambda fd: (_ for _ in ()).throw(OSError("bad")))
    assert detect.foreground_agent(1, 10) == (None, None)
    monkeypatch.setattr(detect.os, "tcgetpgrp", lambda fd: 0)
    assert detect.foreground_agent(1, 10) == (None, None)
    monkeypatch.setattr(detect.os, "tcgetpgrp", lambda fd: 9)
    monkeypatch.setattr(detect, "_ps_in_group", lambda pgid: None)
    assert detect.foreground_agent(1, 10) == (None, None)
    monkeypatch.setattr(detect, "_ps_in_group", lambda pgid: "10 zsh -l")
    assert detect.foreground_agent(1, 10) == (None, None)
    assert detect._cwd_of(None) is None
    monkeypatch.setattr(detect, "_ps_in_group", lambda pgid: "44 claude claude --print")
    monkeypatch.setattr(detect, "_cwd_of", lambda pid: "/work")
    assert detect.foreground_agent(1, 10) == ("claude", "/work")

    monkeypatch.undo()
    monkeypatch.setattr(detect.os, "readlink", lambda path: "/tmp/proj")
    monkeypatch.setattr(detect.Path, "exists", lambda self: True)
    # _cwd_of builds Path(f"/proc/{pid}/cwd")
    assert detect._cwd_of(44) == "/tmp/proj"
