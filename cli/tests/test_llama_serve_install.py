"""llama.cpp binary lookup, serve process, and installer without a real CLI."""

from __future__ import annotations

import io
import subprocess
from pathlib import Path

from agent_server import llama_runtime as bridge


class _Proc:
    def __init__(self, lines=b"ready\n\n", code=None):
        self.pid = 42
        self.stderr = io.BytesIO(lines)
        self.code = code
        self.args = None

    def poll(self):
        return self.code


class _InlineThread:
    def __init__(self, target=None, args=(), **kwargs):
        self.target = target
        self.args = args

    def start(self):
        if self.target is not None:
            self.target(*self.args)


def test_binary_serve_and_memory(tmp_path, monkeypatch):
    missing = tmp_path / "missing"
    monkeypatch.setattr(bridge, "_binary_candidates", lambda: [str(missing)])
    monkeypatch.setattr(bridge.shutil, "which", lambda name: None)
    assert bridge.llama_binary() is None

    exe = tmp_path / "llama"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    monkeypatch.setattr(bridge, "_binary_candidates", lambda: [str(exe)])
    assert bridge.llama_binary() == str(exe)

    proc = _Proc()
    monkeypatch.setattr(bridge.subprocess, "Popen", lambda *args, **kwargs: proc)
    monkeypatch.setattr(bridge.threading, "Thread", _InlineThread)
    monkeypatch.setattr(bridge, "list_models", lambda: [{"id": "gemma"}])
    bridge._serve_proc = None
    bridge._start_serve(str(exe))
    assert bridge.serve_pid() == 42
    bridge._start_serve(str(exe))
    proc.code = 0
    assert bridge.serve_pid() is None

    failed = _Proc(lines=b"boom\n", code=2)
    monkeypatch.setattr(bridge, "list_models", lambda: None)
    bridge._capture_serve(failed, [str(exe), "serve"])
    assert bridge.status()["phase"] == "error"

    def _no_sysconf(key):
        raise OSError("no")

    monkeypatch.setattr(bridge.os, "sysconf", _no_sysconf)
    assert bridge._memory_bytes() == 16 * 1000**3
    assert bridge._fits(0, 100) is True
    assert bridge._fits(10, 10) is False
    assert bridge._fits(5, 10) is True

    monkeypatch.setattr(bridge, "list_models", lambda: None)
    bridge.publish_profile()
    monkeypatch.setattr(bridge, "list_models", lambda: [{"id": "gemma"}])
    monkeypatch.setattr("agent.config.Config.load", staticmethod(lambda: object()))
    monkeypatch.setattr(
        "agent_server.models_service.profiles.upsert_profile",
        lambda config, request: SimpleProfile(),
    )
    bridge.publish_profile()


class SimpleProfile:
    pass


def test_install_cli_then_serve(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge.shutil, "which", lambda name: None)
    bridge._install_cli_then_serve()
    assert "curl" in bridge.status()["detail"]

    monkeypatch.setattr(bridge.shutil, "which", lambda name: "/usr/bin/curl" if name == "curl" else None)
    monkeypatch.setattr(
        bridge.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", "network down"),
    )
    bridge._install_cli_then_serve()
    assert bridge.status()["phase"] == "error"

    def _timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="curl", timeout=1)

    monkeypatch.setattr(bridge.subprocess, "run", _timeout)
    bridge._install_cli_then_serve()
    assert "Could not install" in bridge.status()["detail"]

    calls = {"n": 0}

    def _run(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return subprocess.CompletedProcess(args[0], 0, "", "")
        return subprocess.CompletedProcess(args[0], 7, "", "installer failed\nlast line")

    monkeypatch.setattr(bridge.subprocess, "run", _run)
    monkeypatch.setattr(bridge, "llama_binary", lambda: None)
    bridge._install_cli_then_serve()
    assert "last line" in bridge.status()["detail"]

    calls["n"] = 0

    def _ok(*args, **kwargs):
        calls["n"] += 1
        return subprocess.CompletedProcess(args[0], 0, "installed", "")

    started = {}
    monkeypatch.setattr(bridge.subprocess, "run", _ok)
    monkeypatch.setattr(bridge, "llama_binary", lambda: str(tmp_path / "llama"))
    monkeypatch.setattr(bridge, "_start_serve", lambda binary: started.setdefault("bin", binary))
    bridge._install_cli_then_serve()
    assert started["bin"].endswith("llama")

    def _unlink_fails(self, missing_ok=False):
        raise OSError("busy")

    monkeypatch.setattr(Path, "unlink", _unlink_fails)
    bridge._install_cli_then_serve()
    assert started["bin"]
