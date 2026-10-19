"""Extra unit coverage for PTY agent probes, service logs, code graders, and sandbox control.

PTY fds, ``ps``/``lsof``, Modal, and ``python3`` graders are mocked. Sleeps are patched.
"""

from __future__ import annotations

import asyncio
import builtins
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.sandbox_control_tools.context import SandboxControlContext
from agent_server import services_report as report
from agent_server.bench_service import code_exec
from agent_server.pty_manager import agent_mixin
from agent_server.pty_manager.agent_mixin import PtyAgentMixin
from agent_server.pty_manager.types import PtyInfo, PtySession
from agent_server.session_sandbox_service import service as sandbox_svc

# ---------------------------------------------------------------------------
# PTY agent mixin
# ---------------------------------------------------------------------------


class _Clock:
    def __init__(self, now: float = 1_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class _Host(PtyAgentMixin):
    def __init__(self) -> None:
        self._sessions: dict[str, PtySession] = {}


class _WS:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[str] = []

    async def send_text(self, frame: str) -> None:
        if self.fail:
            raise ConnectionError("closed")
        self.sent.append(frame)


def _refuse_ps(*_args, **_kwargs):
    raise AssertionError("foreground_agent must be patched")


def _pty(
    *,
    pid: int = 100,
    status: str = "running",
    agent: str | None = None,
    agent_cwd: str | None = None,
    session_id: str = "sess",
    probed_at: float = 0.0,
    pgid: int = -1,
    resolving: bool = False,
    hook_at: float = 0.0,
) -> PtySession:
    info = PtyInfo(
        id="pty-1",
        session_id=session_id,
        title="shell",
        cwd="/work",
        cols=80,
        rows=24,
        pid=pid,
        status=status,
        agent=agent,
        agent_cwd=agent_cwd,
    )
    return PtySession(
        info=info,
        master_fd=7,
        agent_probed_at=probed_at,
        agent_pgid=pgid,
        agent_resolving=resolving,
        agent_from_hook_at=hook_at,
    )


@pytest.fixture(autouse=True, name="clock")
def _safe_pty(monkeypatch):
    """Keep every test off real process groups, shells, and blocking sleeps."""
    clock = _Clock()
    sleeps = {"n": 0}

    async def _sleep(_delay: float = 0) -> None:
        sleeps["n"] += 1
        if sleeps["n"] > 30:
            raise asyncio.CancelledError()

    async def _inline(fn, /, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(agent_mixin.time, "monotonic", clock)
    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", lambda _fd: -1)
    monkeypatch.setattr(agent_mixin.os, "write", lambda _fd, _data: 0)
    monkeypatch.setattr(agent_mixin.asyncio, "sleep", _sleep)
    monkeypatch.setattr(agent_mixin.asyncio, "to_thread", _inline)
    monkeypatch.setattr("agent.external_agents.foreground_agent", _refuse_ps)
    return clock


def test_foreground_pgid_success_and_oserror(monkeypatch):
    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", lambda _fd: 42)
    assert agent_mixin._foreground_pgid(3) == 42

    def _boom(_fd: int) -> int:
        raise OSError("bad fd")

    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", _boom)
    assert agent_mixin._foreground_pgid(3) == -1


def test_apply_agent_hook_grace_and_cwd(clock: _Clock):
    host = _Host()
    session = _pty(agent="claude", agent_cwd="/old")

    assert host._apply_agent(session, "opencode", "/repo", from_hook=True) is True
    assert session.agent_from_hook_at == clock.now
    assert session.info.agent == "opencode"
    assert session.info.agent_cwd == "/repo"

    clock.now += 1
    assert host._apply_agent(session, None, None) is False
    assert session.info.agent == "opencode"

    clock.now = session.agent_from_hook_at + agent_mixin.HOOK_GRACE_S
    assert host._apply_agent(session, None, None) is True
    assert session.info.agent is None
    assert session.info.agent_cwd is None

    assert host._apply_agent(session, None, "/ignored", from_hook=True) is False
    assert session.agent_from_hook_at == 0.0

    session.info.agent = "claude"
    session.info.agent_cwd = "/old"
    assert host._apply_agent(session, "claude", "/new") is True
    assert session.info.agent_cwd == "/new"
    assert host._apply_agent(session, "claude", "/new") is False


def test_refresh_agent_interval_stopped_shell_and_force(clock: _Clock, monkeypatch):
    host = _Host()
    recent = _pty(agent="claude", agent_cwd="/repo", probed_at=clock.now)
    assert host.refresh_agent(recent) is False
    assert recent.agent_probed_at == clock.now

    clock.now += 0.2
    assert host.refresh_agent(recent, force=True) is True
    assert recent.info.agent is None

    stopped = _pty(agent="fx", status="exited", probed_at=0.0)
    clock.now += 5
    assert host.refresh_agent(stopped) is True
    assert stopped.info.agent is None

    shell = _pty(pid=100, agent="codex", agent_cwd="/repo")
    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", lambda _fd: 100)
    assert host.refresh_agent(shell) is True
    assert shell.info.agent is None
    assert shell.agent_pgid == 100

    same = _pty(pgid=55)
    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", lambda _fd: 55)
    assert host.refresh_agent(same) is False

    changed = _pty(pgid=1, agent="claude")
    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", lambda _fd: 77)
    assert host.refresh_agent(changed) is False
    assert changed.agent_pgid == 77
    assert changed.info.agent == "claude"

    seen: list[tuple[int, int]] = []

    def _agent(fd: int, pid: int):
        seen.append((fd, pid))
        return "codex", "/work"

    monkeypatch.setattr("agent.external_agents.foreground_agent", _agent)
    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", lambda _fd: 77)
    forced = _pty(agent="codex", agent_cwd="/old")
    assert host.refresh_agent(forced, force=True) is True
    assert forced.info.agent == "codex"
    assert forced.info.agent_cwd == "/work"
    assert seen == [(7, 100)]
    assert host.refresh_agent(forced, force=True) is False


def test_refresh_agent_async_paths(clock: _Clock, monkeypatch):
    host = _Host()
    recent = _pty(probed_at=clock.now)
    assert asyncio.run(host.refresh_agent_async(recent)) is False

    stopped = _pty(agent="claude", status="dead")
    clock.now += 5
    assert asyncio.run(host.refresh_agent_async(stopped)) is True
    assert stopped.info.agent is None

    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", lambda _fd: 9)
    same = _pty(pgid=9)
    assert asyncio.run(host.refresh_agent_async(same)) is False

    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", lambda _fd: 100)
    shell = _pty(pid=100, agent="fx")
    assert asyncio.run(host.refresh_agent_async(shell)) is True
    assert shell.info.agent is None

    busy = _pty(resolving=True, pgid=1)
    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", lambda _fd: 40)
    assert asyncio.run(host.refresh_agent_async(busy)) is False
    assert busy.agent_resolving is True

    def _agent(_fd: int, _pid: int):
        return "claude", "/repo"

    monkeypatch.setattr("agent.external_agents.foreground_agent", _agent)
    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", lambda _fd: 40)
    found = _pty()
    assert asyncio.run(host.refresh_agent_async(found)) is True
    assert found.info.agent == "claude"
    assert found.agent_resolving is False

    def _boom(_fd: int, _pid: int):
        raise RuntimeError("ps failed")

    monkeypatch.setattr("agent.external_agents.foreground_agent", _boom)
    broken = _pty(pgid=1)
    with pytest.raises(RuntimeError, match="ps failed"):
        asyncio.run(host.refresh_agent_async(broken))
    assert broken.agent_resolving is False

    calls = {"n": 0}

    def _flip(_fd: int) -> int:
        calls["n"] += 1
        return 40 if calls["n"] == 1 else 41

    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", _flip)
    monkeypatch.setattr("agent.external_agents.foreground_agent", _agent)
    stale = _pty(agent="fx", pgid=1)
    assert asyncio.run(host.refresh_agent_async(stale)) is False
    assert stale.info.agent == "fx"


def test_refresh_agents_for_filters_session(monkeypatch):
    host = _Host()
    mine = _pty(session_id="keep", agent="claude", pgid=5)
    other = _pty(session_id="skip", agent="codex")
    host._sessions = {"a": mine, "b": other}
    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", lambda _fd: -1)
    host.refresh_agents_for("keep")
    assert mine.info.agent is None
    assert other.info.agent == "codex"


def test_broadcast_agent_drops_dead_sockets():
    host = _Host()
    session = _pty(agent="claude", agent_cwd="/repo")
    ok = _WS()
    dead = _WS(fail=True)
    session.subscribers.update({ok, dead})
    asyncio.run(host._broadcast_agent(session))
    assert dead not in session.subscribers
    assert ok in session.subscribers
    payload = json.loads(ok.sent[0])
    assert payload["type"] == "pty.event"
    assert payload["event"]["agent"] == "claude"
    assert payload["event"]["agentCwd"] == "/repo"
    assert host._agent_frame(session) == ok.sent[0]

    empty = _pty()
    asyncio.run(host._broadcast_agent(empty))


def test_maybe_announce_only_on_change(monkeypatch):
    host = _Host()
    ws = _WS()
    quiet = _pty(pgid=4)
    quiet.subscribers.add(ws)
    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", lambda _fd: 4)
    asyncio.run(host._maybe_announce_agent(quiet))
    assert ws.sent == []

    def _agent(_fd: int, _pid: int):
        return "fx", "/tmp"

    monkeypatch.setattr("agent.external_agents.foreground_agent", _agent)
    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", lambda _fd: 80)
    changed = _pty()
    changed.subscribers.add(ws)
    asyncio.run(host._maybe_announce_agent(changed, force=True))
    assert changed.info.agent == "fx"
    assert len(ws.sent) == 1


def test_watch_agent_while_attached(monkeypatch):
    host = _Host()
    ws = _WS()

    idle = _pty(status="exited")
    idle.subscribers.add(ws)
    asyncio.run(host.watch_agent_while_attached(idle, ws))

    missing = _pty()
    asyncio.run(host.watch_agent_while_attached(missing, ws))

    left = _pty()
    left.subscribers.add(ws)

    async def _drop(_delay: float = 0) -> None:
        left.subscribers.discard(ws)

    monkeypatch.setattr(agent_mixin.asyncio, "sleep", _drop)
    asyncio.run(host.watch_agent_while_attached(left, ws))

    exited = _pty()
    exited.subscribers.add(ws)

    async def _exit(_delay: float = 0) -> None:
        exited.info.status = "exited"

    monkeypatch.setattr(agent_mixin.asyncio, "sleep", _exit)
    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", lambda _fd: -1)
    asyncio.run(host.watch_agent_while_attached(exited, ws))

    cancelled = _pty()
    cancelled.subscribers.add(ws)

    async def _cancel(_delay: float = 0) -> None:
        raise asyncio.CancelledError()

    monkeypatch.setattr(agent_mixin.asyncio, "sleep", _cancel)
    asyncio.run(host.watch_agent_while_attached(cancelled, ws))

    broken = _pty()
    broken.subscribers.add(ws)

    async def _explode(_delay: float = 0) -> None:
        raise RuntimeError("probe")

    monkeypatch.setattr(agent_mixin.asyncio, "sleep", _explode)
    asyncio.run(host.watch_agent_while_attached(broken, ws))


def test_type_startup(monkeypatch):
    host = _Host()
    delays: list[float] = []
    written: list[tuple[int, bytes]] = []

    async def _sleep(delay: float = 0) -> None:
        delays.append(delay)

    def _write(fd: int, data: bytes) -> int:
        written.append((fd, data))
        return len(data)

    monkeypatch.setattr(agent_mixin.asyncio, "sleep", _sleep)
    monkeypatch.setattr(agent_mixin.os, "write", _write)

    empty = _pty()
    asyncio.run(host.type_startup(empty, "   "))
    assert delays == []
    assert written == []

    dead = _pty(status="exited")
    asyncio.run(host.type_startup(dead, "claude", delay_s=0.1))
    assert delays == [0.1]
    assert written == []

    def _oserror(_fd: int, _data: bytes) -> int:
        raise OSError("closed")

    monkeypatch.setattr(agent_mixin.os, "write", _oserror)
    running = _pty()
    asyncio.run(host.type_startup(running, "  claude  "))
    assert delays == [0.1, 0.35]

    def _agent(_fd: int, _pid: int):
        return "claude", "/work"

    monkeypatch.setattr("agent.external_agents.foreground_agent", _agent)
    monkeypatch.setattr(agent_mixin.os, "tcgetpgrp", lambda _fd: 50)
    monkeypatch.setattr(agent_mixin.os, "write", _write)
    ws = _WS()
    started = _pty()
    started.subscribers.add(ws)
    asyncio.run(host.type_startup(started, "codex", delay_s=0.2))
    assert written == [(7, b"codex\r")]
    assert started.info.agent == "claude"
    assert delays[-2:] == [0.2, 0.8]
    assert ws.sent


# ---------------------------------------------------------------------------
# Services report
# ---------------------------------------------------------------------------


def _completed(args, stdout, code: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(args=args, returncode=code, stdout=stdout, stderr=stderr)


def test_process_stats_parses_and_fails(monkeypatch):
    def _run(args, **_kwargs):
        return _completed(args, "4096 1.5 /usr/bin/sandwalk serve --port 1\n")

    monkeypatch.setattr(report.subprocess, "run", _run)
    rss, cpu, command = report._process_stats(9)
    assert rss == 4096 * 1024
    assert cpu == 1.5
    assert command == "/usr/bin/sandwalk serve --port 1"

    monkeypatch.setattr(report.subprocess, "run", lambda args, **_k: _completed(args, "100 nope\n"))
    rss, cpu, command = report._process_stats(9)
    assert rss == 100 * 1024
    assert cpu is None
    assert command == "nope"

    monkeypatch.setattr(
        report.subprocess, "run", lambda args, **_k: _completed(args, "100 2.0   \n")
    )
    assert report._process_stats(9) == (100 * 1024, 2.0, None)

    monkeypatch.setattr(report.subprocess, "run", lambda args, **_k: _completed(args, "\n"))
    assert report._process_stats(9) == (None, None, None)

    monkeypatch.setattr(report.subprocess, "run", lambda args, **_k: _completed(args, None))
    assert report._process_stats(9) == (None, None, None)

    def _timeout(args, **_kwargs):
        raise subprocess.TimeoutExpired(args, 2)

    monkeypatch.setattr(report.subprocess, "run", _timeout)
    assert report._process_stats(9) == (None, None, None)

    def _oserror(_args, **_kwargs):
        raise OSError("ps missing")

    monkeypatch.setattr(report.subprocess, "run", _oserror)
    assert report._process_stats(9) == (None, None, None)


def test_listen_port_and_pid_on_port(monkeypatch):
    def _listen(args, **_kwargs):
        return _completed(args, "python 1 127.0.0.1:8787 (LISTEN)\nnode 2\n")

    monkeypatch.setattr(report.subprocess, "run", _listen)
    assert report._listen_port(1) == 8787

    monkeypatch.setattr(
        report.subprocess, "run", lambda args, **_k: _completed(args, "no listen here\n")
    )
    assert report._listen_port(1) is None

    monkeypatch.setattr(report.subprocess, "run", lambda args, **_k: _completed(args, None))
    assert report._listen_port(1) is None

    def _pid(args, **_kwargs):
        return _completed(args, "abc\n\n4242\n")

    monkeypatch.setattr(report.subprocess, "run", _pid)
    assert report._pid_on_port(9931) == 4242

    monkeypatch.setattr(report.subprocess, "run", lambda args, **_k: _completed(args, "nope\n"))
    assert report._pid_on_port(9931) is None

    def _timeout(args, **_kwargs):
        raise subprocess.TimeoutExpired(args, 2)

    monkeypatch.setattr(report.subprocess, "run", _timeout)
    assert report._listen_port(1) is None
    assert report._pid_on_port(1) is None

    def _oserror(_args, **_kwargs):
        raise OSError("lsof missing")

    monkeypatch.setattr(report.subprocess, "run", _oserror)
    assert report._listen_port(1) is None
    assert report._pid_on_port(1) is None


def test_sandwalk_port_env_fallback(monkeypatch):
    monkeypatch.setattr(report, "_listen_port", lambda _pid: 8787)
    monkeypatch.setenv("SANDWALK_PORT", "1")
    assert report._sandwalk_port(4) == 8787

    monkeypatch.setattr(report, "_listen_port", lambda _pid: None)
    monkeypatch.setenv("FASTFOLD_SERVE_PORT", "8791")
    assert report._sandwalk_port(4) == 8791

    monkeypatch.delenv("FASTFOLD_SERVE_PORT")
    monkeypatch.setenv("SANDWALK_PORT", "8792")
    assert report._sandwalk_port(4) == 8792

    monkeypatch.setenv("FASTFOLD_SERVE_PORT", "nope")
    monkeypatch.setenv("SANDWALK_PORT", "8792")
    assert report._sandwalk_port(4) is None

    monkeypatch.setenv("FASTFOLD_SERVE_PORT", "")
    assert report._sandwalk_port(4) == 8792

    monkeypatch.delenv("FASTFOLD_SERVE_PORT")
    monkeypatch.delenv("SANDWALK_PORT")
    assert report._sandwalk_port(4) is None


def test_llama_process_stopped_and_running(monkeypatch):
    monkeypatch.setattr("agent_server.llama_runtime.serve_pid", lambda: None)
    monkeypatch.setattr("agent_server.llama_runtime.llama_binary", lambda: None)
    monkeypatch.setattr(report, "_pid_on_port", lambda _port: None)
    stopped = report._llama_process()
    assert stopped.status == "stopped"
    assert stopped.pid is None
    assert stopped.command is None
    assert stopped.detail == "llama CLI is not installed"
    assert stopped.port == report._LLAMA_PORT

    monkeypatch.setattr("agent_server.llama_runtime.llama_binary", lambda: "/opt/llama")
    named = report._llama_process()
    assert named.command == f"/opt/llama serve --host 127.0.0.1 --port {report._LLAMA_PORT}"
    assert named.detail == "/opt/llama"

    monkeypatch.setattr("agent_server.llama_runtime.serve_pid", lambda: 77)
    monkeypatch.setattr(report, "_process_stats", lambda _pid: (2048, 3.25, "llama serve"))
    running = report._llama_process()
    assert running.status == "running"
    assert running.pid == 77
    assert running.rss_bytes == 2048
    assert running.cpu_percent == 3.25
    assert running.command == "llama serve"
    assert running.detail == f"127.0.0.1:{report._LLAMA_PORT}"

    monkeypatch.setattr("agent_server.llama_runtime.serve_pid", lambda: None)
    monkeypatch.setattr(report, "_pid_on_port", lambda _port: 88)
    monkeypatch.setattr(report, "_process_stats", lambda _pid: (None, None, None))
    via_port = report._llama_process()
    assert via_port.pid == 88
    assert via_port.command == "/opt/llama serve"

    monkeypatch.setattr("agent_server.llama_runtime.llama_binary", lambda: None)
    bare = report._llama_process()
    assert bare.command is None


def test_log_tails_orders_preferred_and_extras(tmp_path, monkeypatch):
    missing = tmp_path / "absent"
    monkeypatch.setattr(report, "LOGS_DIR", missing)
    assert report._log_tails() == []

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setattr(report, "LOGS_DIR", log_dir)
    (log_dir / "agent-server.log").write_text("api-line\n")
    (log_dir / "llama.log").write_text("llama-line\n")
    (log_dir / "cli.log").write_text("cli-line\n")
    (log_dir / "notes.txt").write_text("skip\n")
    (log_dir / "subdir").mkdir()
    extras = {
        "e1.log": 10,
        "e2.log": 40,
        "e3.log": 30,
        "e4.log": 20,
        "agent-server.log.1": 50,
    }
    for name, mtime in extras.items():
        path = log_dir / name
        path.write_text(name + "\n")
        os.utime(path, (mtime, mtime))

    tails = report._log_tails()
    assert [item.name for item in tails] == [
        "agent-server.log",
        "llama.log",
        "cli.log",
        "agent-server.log.1",
        "e2.log",
        "e3.log",
    ]
    assert tails[0].tail == "api-line"


def test_tail_truncates_redacts_and_reports_oserror(tmp_path, monkeypatch):
    path = tmp_path / "agent-server.log"
    lines = [f"line-{i}" for i in range(150)]
    path.write_text("\n".join(lines) + "\n")
    tail = report._tail(path)
    kept = tail.splitlines()
    assert kept[0] == "line-30"
    assert kept[-1] == "line-149"
    assert len(kept) == report._LOG_LINES

    path.write_bytes(b"ok\xff\nnext")
    text = report._tail(path)
    assert "ok" in text
    assert "next" in text

    def _boom(self, *args, **kwargs):
        raise OSError("denied")

    monkeypatch.setattr(Path, "read_bytes", _boom)
    assert "unable to read" in report._tail(path)
    assert path.name in report._tail(path)


def test_build_services_report_with_and_without_port(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "LOGS_DIR", tmp_path / "no-logs")
    monkeypatch.setattr("agent_server.llama_runtime.serve_pid", lambda: None)
    monkeypatch.setattr("agent_server.llama_runtime.llama_binary", lambda: None)

    def _run(args, **_kwargs):
        if args[0] == "ps":
            return _completed(args, "1024 0.5 sandwalk\n")
        if "-t" in args:
            return _completed(args, "")
        return _completed(args, "python 1 127.0.0.1:8787 (LISTEN)\n")

    monkeypatch.setattr(report.subprocess, "run", _run)
    monkeypatch.delenv("FASTFOLD_SERVE_PORT", raising=False)
    monkeypatch.delenv("SANDWALK_PORT", raising=False)
    snapshot = report.build_services_report(version="9.9.9")
    api = snapshot.processes[0]
    assert api.status == "running"
    assert api.port == 8787
    assert api.rss_bytes == 1024 * 1024
    assert "v9.9.9" in api.detail
    assert "127.0.0.1:8787" in api.detail
    assert snapshot.processes[1].status == "stopped"
    assert snapshot.logs == []
    assert "T" in snapshot.checked_at

    monkeypatch.setattr(report.subprocess, "run", lambda args, **_k: _completed(args, ""))
    quiet = report.build_services_report(version="0.0.1")
    assert quiet.processes[0].port is None
    assert quiet.processes[0].detail == "v0.0.1"


# ---------------------------------------------------------------------------
# Code execution grader
# ---------------------------------------------------------------------------


def _py(stdout="", stderr="", code: int = 0):
    return subprocess.CompletedProcess(
        args=["python3"], returncode=code, stdout=stdout, stderr=stderr
    )


def test_extract_python_code_fences_and_heuristic():
    assert code_exec.extract_python_code("") == ""
    text = "```python\nfirst\n```\nnoise\n```Python\nsecond\n```"
    assert code_exec.extract_python_code(text) == "second"
    prose = "hello\ndef add(a, b):\n    return a + b\n"
    assert code_exec.extract_python_code(prose) == "def add(a, b):\n    return a + b"
    assert code_exec.extract_python_code("no code at all") == "no code at all"
    for starter in ("class A:", "import os", "from os import path", "# comment"):
        assert code_exec.extract_python_code(f"note\n{starter}\nrest").startswith(starter)


def test_grade_code_exec_rejects_empty_and_unknown_suite(monkeypatch):
    def _unexpected(*_args, **_kwargs):
        raise AssertionError("subprocess should not run")

    monkeypatch.setattr(code_exec.subprocess, "run", _unexpected)
    assert code_exec.grade_code_exec(suite_id="mbpp", source={}, predicted="") is False
    assert (
        code_exec.grade_code_exec(suite_id="mbpp", source={}, predicted="```python\n   \n```")
        is False
    )
    assert code_exec.grade_code_exec(suite_id="other", source={}, predicted="x = 1") is False
    assert (
        code_exec.grade_code_exec(suite_id="mbpp", source={"test_list": []}, predicted="x=1")
        is False
    )
    assert (
        code_exec.grade_code_exec(
            suite_id="livecodebench", source={"inputs": [], "outputs": ["1"]}, predicted="print(1)"
        )
        is False
    )
    assert (
        code_exec.grade_code_exec(
            suite_id="livecodebench", source={"inputs": ["1"], "outputs": []}, predicted="print(1)"
        )
        is False
    )


def test_mbpp_and_execute_capture(monkeypatch):
    scripts: list[str] = []

    def _run(args, **kwargs):
        scripts.append(Path(args[1]).read_text())
        assert kwargs["timeout"] == code_exec.EXEC_TIMEOUT_MBPP
        assert "PATH" in kwargs["env"]
        assert kwargs["preexec_fn"] is code_exec._set_resource_limits
        assert kwargs["input"] == ""
        return _py(stdout="ok\n", stderr="")

    monkeypatch.setattr(code_exec.subprocess, "run", _run)
    ok = code_exec.grade_code_exec(
        suite_id="mbpp",
        source={"test_list": ["assert add(1, 1) == 2"], "test_setup_code": "SETUP"},
        predicted="def add(a, b):\n    return a + b",
    )
    assert ok is True
    assert "SETUP" in scripts[0]
    assert "assert add(1, 1) == 2" in scripts[0]

    monkeypatch.setattr(
        code_exec.subprocess, "run", lambda *a, **k: _py(stdout="out", stderr="bad", code=1)
    )
    assert code_exec._execute("x", stdin="", timeout=3) == (False, "bad")

    monkeypatch.setattr(
        code_exec.subprocess, "run", lambda *a, **k: _py(stdout="out", stderr="", code=1)
    )
    assert code_exec._execute("x", stdin="", timeout=3) == (False, "out")

    monkeypatch.setattr(code_exec.subprocess, "run", lambda *a, **k: _py(stdout="out", stderr=""))
    assert code_exec._execute("x", stdin="in", timeout=3) == (True, "out")

    def _timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["python3"], 3)

    monkeypatch.setattr(code_exec.subprocess, "run", _timeout)
    assert code_exec._execute_capture("x", stdin="", timeout=3) == (
        "",
        False,
        "Execution timed out",
    )

    def _boom(*_args, **_kwargs):
        raise RuntimeError("x" * 600)

    monkeypatch.setattr(code_exec.subprocess, "run", _boom)
    stdout, ok_flag, err = code_exec._execute_capture("x", stdin="", timeout=3)
    assert stdout == ""
    assert ok_flag is False
    assert len(err) == 500

    leaked: list[str] = []
    real_unlink = code_exec.os.unlink

    def _unlink(path):
        leaked.append(path)
        raise OSError("busy")

    monkeypatch.setattr(code_exec.os, "unlink", _unlink)
    monkeypatch.setattr(code_exec.subprocess, "run", lambda *a, **k: _py(stdout="ok"))
    try:
        stdout, ok_flag, err = code_exec._execute_capture("print(1)", stdin="", timeout=1)
        assert (stdout, ok_flag, err) == ("ok", True, "")
    finally:
        for path in leaked:
            real_unlink(path)

    monkeypatch.setattr(code_exec.os, "name", "nt")
    seen: dict = {}

    def _run_nt(*_args, **kwargs):
        seen.update(kwargs)
        return _py(stdout="win")

    monkeypatch.setattr(code_exec.subprocess, "run", _run_nt)
    assert code_exec._execute_capture("x", stdin="", timeout=1)[1] is True
    assert "preexec_fn" not in seen


def test_livecodebench_compares_stdout(monkeypatch):
    calls = {"n": 0}

    def _run(*_args, **kwargs):
        calls["n"] += 1
        stdin = kwargs["input"]
        assert kwargs["timeout"] == code_exec.EXEC_TIMEOUT_LCB
        if stdin == "a\n":
            return _py(stdout="A\n")
        if stdin == "2":
            return _py(stdout="4")
        return _py(code=1, stderr="no")

    monkeypatch.setattr(code_exec.subprocess, "run", _run)
    assert (
        code_exec.grade_code_exec(
            suite_id="livecodebench",
            source={"inputs": ["a\n", 2], "outputs": [" A\n", 4]},
            predicted="print('ok')",
        )
        is True
    )
    assert calls["n"] == 2

    counted = {"n": 0}

    def _mismatch(*_args, **_kwargs):
        counted["n"] += 1
        return _py(stdout="nope")

    monkeypatch.setattr(code_exec.subprocess, "run", _mismatch)
    assert (
        code_exec._run_livecodebench("print(1)", {"inputs": ["a", "b"], "outputs": ["z", "b"]})
        is False
    )
    assert counted["n"] == 1

    counted["n"] = 0

    def _fail(*_args, **_kwargs):
        counted["n"] += 1
        return _py(code=1, stderr="traceback")

    monkeypatch.setattr(code_exec.subprocess, "run", _fail)
    assert (
        code_exec._run_livecodebench("print(1)", {"inputs": ["a", "b"], "outputs": ["a", "b"]})
        is False
    )
    assert counted["n"] == 1


def test_set_resource_limits(monkeypatch):
    import resource

    calls: list[tuple] = []

    def _ok(res, limits):
        calls.append((res, limits))

    monkeypatch.setattr(resource, "setrlimit", _ok)
    code_exec._set_resource_limits()
    assert calls[0][0] == resource.RLIMIT_AS
    assert calls[0][1] == (code_exec.EXEC_MEMORY_LIMIT_BYTES, code_exec.EXEC_MEMORY_LIMIT_BYTES)
    assert calls[1][0] == resource.RLIMIT_CPU

    def _fail(*_args, **_kwargs):
        raise OSError("no limit")

    monkeypatch.setattr(resource, "setrlimit", _fail)
    code_exec._set_resource_limits()

    real_import = builtins.__import__

    def _block(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "resource":
            raise ImportError("blocked")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _block)
    code_exec._set_resource_limits()


def test_parse_lcb_public_tests(monkeypatch):
    raw = json.dumps([{"input": "1\n", "output": "2\n"}, "skip", {}])
    inputs, outputs = code_exec.parse_lcb_public_tests(raw)
    assert inputs == ["1\n", ""]
    assert outputs == ["2\n", ""]
    assert code_exec.parse_lcb_public_tests("{") == ([], [])
    assert code_exec.parse_lcb_public_tests("null") == ([], [])
    assert code_exec.parse_lcb_public_tests({"input": "a"}) == ([], [])
    assert code_exec.parse_lcb_public_tests(None) == ([], [])

    def _type_error(_raw):
        raise TypeError("bad")

    monkeypatch.setattr(code_exec.json, "loads", _type_error)
    assert code_exec.parse_lcb_public_tests("[]") == ([], [])


# ---------------------------------------------------------------------------
# Sandbox control context
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


def _snap(**overrides):
    data = {
        "status": "running",
        "backend": "modal",
        "compute_type": "cpu",
        "gpu_class": "T4",
        "base_image": "python:3.12-slim",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_sandbox_context_init_and_missing_session():
    store = SimpleNamespace()
    ctx = SandboxControlContext("  sess  ", store=store)
    assert ctx.sid == "sess"
    assert ctx.agent_store is store
    blank = SandboxControlContext("   ", store=store)
    message = blank._missing_session()
    assert "session_id is missing" in message
    assert _run(blank.status_coro()) == message
    assert _run(blank.start_coro()) == message
    assert _run(blank.stop_coro()) == message


def test_status_coro_modal_states_and_errors():
    store = SimpleNamespace()
    ctx = SandboxControlContext("sess", store=store)

    def _status(state: str):
        ctx.service = SimpleNamespace(status=lambda _sid: _snap(status=state, backend="modal"))
        return _run(ctx.status_coro())

    assert "running and attached" in _status("running")
    assert "is starting" in _status("starting")
    assert "not configured" in _status("unavailable")
    assert "sandbox is stopped" in _status("stopped")

    ctx.service = SimpleNamespace(status=lambda _sid: _snap(backend="builtin", status="ready"))
    assert "Built-in host sandbox" in _run(ctx.status_coro())

    ctx.service = SimpleNamespace(status=lambda _sid: object())
    assert "Built-in host sandbox" in _run(ctx.status_coro())

    def _missing(_sid):
        raise KeyError(_sid)

    ctx.service = SimpleNamespace(status=_missing)
    assert "was not found" in _run(ctx.status_coro())

    def _boom(_sid):
        raise RuntimeError("down")

    ctx.service = SimpleNamespace(status=_boom)
    assert "Failed to check sandbox status: down" in _run(ctx.status_coro())


def test_start_coro_switches_applies_compute_and_reports(monkeypatch):
    store = SimpleNamespace(update_session=lambda *_a, **_k: None)
    ctx = SandboxControlContext("sess", store=store)

    def _blocked_start(_sid):
        raise AssertionError("start")

    ctx.service = SimpleNamespace(
        status=lambda _sid: _snap(backend="builtin", status="ready"),
        start=_blocked_start,
    )
    text = _run(ctx.start_coro(enable_modal=False))
    assert "enable_modal=true" in text

    def _locked(*_args, **_kwargs):
        raise RuntimeError("locked")

    store = SimpleNamespace(update_session=_locked)
    ctx = SandboxControlContext("sess", store=store)
    ctx.service = SimpleNamespace(
        status=lambda _sid: _snap(backend="builtin"),
        start=_blocked_start,
    )
    assert "Failed to switch chat to Modal" in _run(ctx.start_coro(enable_modal=True))

    updated: list[tuple] = []

    def _update_session(*args, **kwargs):
        updated.append((args, kwargs))

    captured: dict = {}

    def _settings_update(payload):
        captured["payload"] = payload

    monkeypatch.setattr(
        "agent_server.sandbox_settings_service.SandboxSettingsService.update",
        _settings_update,
    )
    store = SimpleNamespace(update_session=_update_session)
    ctx = SandboxControlContext("sess", store=store)
    ctx.service = SimpleNamespace(
        status=lambda _sid: _snap(backend="builtin", status="stopped"),
        start=lambda _sid: _snap(
            status="running", compute_type="GPU", gpu_class="A10", base_image="cuda-img"
        ),
    )
    text = _run(ctx.start_coro(enable_modal=True, compute_type="gpu", gpu_class="A10"))
    assert updated[0][1]["sandbox_backend"] == "modal"
    assert captured["payload"].compute_type == "gpu"
    assert "GPU=A10" in text
    assert "cuda-img" in text

    ctx.service = SimpleNamespace(
        status=lambda _sid: _snap(backend="modal", status="stopped"),
        start=lambda _sid: _snap(status="starting"),
    )
    assert "start requested" in _run(ctx.start_coro(enable_modal=False))

    ctx.service = SimpleNamespace(
        status=lambda _sid: _snap(backend="modal"),
        start=lambda _sid: _snap(status="paused"),
    )
    assert "finished with status `paused`" in _run(ctx.start_coro())

    def _inspect_missing(_sid):
        raise KeyError("sess")

    ctx.service = SimpleNamespace(status=_inspect_missing, start=_blocked_start)
    assert "was not found" in _run(ctx.start_coro())

    def _inspect_boom(_sid):
        raise RuntimeError("inspect")

    ctx.service = SimpleNamespace(status=_inspect_boom, start=_blocked_start)
    assert "Failed to inspect sandbox before start: inspect" in _run(ctx.start_coro())

    def _start_value(_sid):
        raise ValueError("no workspace")

    ctx.service = SimpleNamespace(
        status=lambda _sid: _snap(backend="modal"),
        start=_start_value,
    )
    assert "Failed to start sandbox: no workspace" in _run(ctx.start_coro())

    def _start_missing(_sid):
        raise KeyError("sess")

    ctx.service = SimpleNamespace(
        status=lambda _sid: _snap(backend="modal"),
        start=_start_missing,
    )
    assert "was not found" in _run(ctx.start_coro())

    def _start_boom(_sid):
        raise RuntimeError("modal down")

    ctx.service = SimpleNamespace(
        status=lambda _sid: _snap(backend="modal"),
        start=_start_boom,
    )
    assert "Failed to start sandbox: modal down" in _run(ctx.start_coro())

    ctx.service = SimpleNamespace(
        status=lambda _sid: _snap(backend="modal"),
        start=_blocked_start,
    )
    assert "compute_type must be" in _run(ctx.start_coro(compute_type="tpu"))


def test_apply_compute_request(monkeypatch):
    ctx = SandboxControlContext("sess", store=SimpleNamespace())
    assert ctx._apply_compute_request(compute_type=None, gpu_class=None) is None
    assert ctx._apply_compute_request(compute_type="  ", gpu_class="  ") is None
    assert "must be" in (ctx._apply_compute_request(compute_type="tpu", gpu_class=None) or "")

    captured: dict = {}

    def _update(payload):
        captured["payload"] = payload

    monkeypatch.setattr(
        "agent_server.sandbox_settings_service.SandboxSettingsService.update",
        _update,
    )
    assert ctx._apply_compute_request(compute_type=None, gpu_class="A100") is None
    assert captured["payload"].compute_type == "gpu"
    assert captured["payload"].gpu_class == "A100"

    assert ctx._apply_compute_request(compute_type=" CPU ", gpu_class="  ") is None
    assert captured["payload"].compute_type == "cpu"
    assert captured["payload"].gpu_class is None

    def _fail(_payload):
        raise ValueError("bad compute")

    monkeypatch.setattr(
        "agent_server.sandbox_settings_service.SandboxSettingsService.update",
        _fail,
    )
    message = ctx._apply_compute_request(compute_type="cpu", gpu_class="T4")
    assert message is not None
    assert "bad compute" in message


def test_stop_coro_errors_and_success():
    ctx = SandboxControlContext("sess", store=SimpleNamespace())

    def _missing(_sid):
        raise KeyError("sess")

    ctx.service = SimpleNamespace(stop=_missing)
    assert "was not found" in _run(ctx.stop_coro())

    def _boom(_sid):
        raise RuntimeError("stop failed")

    ctx.service = SimpleNamespace(stop=_boom)
    assert "Failed to stop sandbox: stop failed" in _run(ctx.stop_coro())

    ctx.service = SimpleNamespace(stop=lambda _sid: _snap(status="stopped", backend="modal"))
    assert "Sandbox stop completed" in _run(ctx.stop_coro())


# ---------------------------------------------------------------------------
# Session sandbox service
# ---------------------------------------------------------------------------


def _settings(**overrides):
    data = {
        "backend": "builtin",
        "modal_configured": True,
        "compute_type": "cpu",
        "gpu_class": "T4",
        "cpu_cores": 2.0,
        "ram_gb": 8.0,
        "cpu_image": "python:3.12-slim",
        "gpu_image": "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _service(session, monkeypatch, **setting_overrides):
    monkeypatch.setattr(
        sandbox_svc.SandboxSettingsService, "get", lambda: _settings(**setting_overrides)
    )
    store = SimpleNamespace(get_session=lambda _sid: session)
    return sandbox_svc.SessionSandboxService(store)


def test_session_sandbox_status_matrix(monkeypatch):
    missing = sandbox_svc.SessionSandboxService(SimpleNamespace(get_session=lambda _sid: None))
    with pytest.raises(KeyError):
        missing.status("gone")

    session = SimpleNamespace(sandbox_backend=None, workspace_path="/ws")
    monkeypatch.setattr(sandbox_svc, "get_active_handle", lambda _sid: None)
    builtin = _service(session, monkeypatch, backend="other")
    status = builtin.status("s1")
    assert status.backend == "builtin"
    assert status.global_backend == "builtin"
    assert status.status == "ready"
    assert status.session_backend is None

    handle = SimpleNamespace(kind="builtin", provider_sandbox_name="ignored")
    monkeypatch.setattr(sandbox_svc, "get_active_handle", lambda _sid: handle)
    ready = _service(
        SimpleNamespace(sandbox_backend="builtin", workspace_path="/ws"),
        monkeypatch,
        backend="modal",
    ).status("s1")
    assert ready.status == "ready"
    assert ready.global_backend == "modal"
    assert ready.provider_sandbox_name is None

    bare = SimpleNamespace(
        backend="builtin",
        modal_configured=False,
        compute_type="",
        gpu_class="L4",
        cpu_cores=1.0,
        ram_gb=1.0,
    )
    monkeypatch.setattr(sandbox_svc.SandboxSettingsService, "get", lambda: bare)
    monkeypatch.setattr(sandbox_svc, "get_active_handle", lambda _sid: None)
    defaults = sandbox_svc.SessionSandboxService(
        SimpleNamespace(get_session=lambda _sid: session)
    ).status("s1")
    assert defaults.compute_type == "cpu"
    assert defaults.cpu_image == "python:3.12-slim"
    assert defaults.gpu_image.startswith("pytorch/")
    assert defaults.base_image == defaults.cpu_image

    gpu_settings_session = SimpleNamespace(sandbox_backend="modal", workspace_path="/ws")
    monkeypatch.setattr(
        sandbox_svc.SandboxSettingsService,
        "get",
        lambda: _settings(backend="modal", compute_type=" GPU ", modal_configured=False),
    )
    unavailable = sandbox_svc.SessionSandboxService(
        SimpleNamespace(get_session=lambda _sid: gpu_settings_session)
    ).status("s1")
    assert unavailable.status == "unavailable"
    assert unavailable.compute_type == "gpu"
    assert unavailable.base_image == unavailable.gpu_image
    assert "not configured" in (unavailable.detail or "")

    modal_handle = SimpleNamespace(kind="modal", provider_sandbox_name="sbx-9")
    monkeypatch.setattr(sandbox_svc, "get_active_handle", lambda _sid: modal_handle)
    monkeypatch.setattr(
        sandbox_svc.SandboxSettingsService,
        "get",
        lambda: _settings(backend="modal", modal_configured=True, compute_type="cpu"),
    )
    running = sandbox_svc.SessionSandboxService(
        SimpleNamespace(get_session=lambda _sid: gpu_settings_session)
    ).status("s1")
    assert running.status == "running"
    assert running.provider_sandbox_name == "sbx-9"

    monkeypatch.setattr(
        sandbox_svc,
        "get_active_handle",
        lambda _sid: SimpleNamespace(kind="builtin", provider_sandbox_name="no"),
    )
    stopped = sandbox_svc.SessionSandboxService(
        SimpleNamespace(get_session=lambda _sid: gpu_settings_session)
    ).status("s1")
    assert stopped.status == "stopped"
    assert "not running" in (stopped.detail or "")

    monkeypatch.setattr(sandbox_svc, "get_active_handle", lambda _sid: None)
    also_stopped = sandbox_svc.SessionSandboxService(
        SimpleNamespace(get_session=lambda _sid: gpu_settings_session)
    ).status("s1")
    assert also_stopped.status == "stopped"


def test_session_sandbox_start_stop_restart(tmp_path, monkeypatch):
    workspace = tmp_path / "nested" / "ws"
    session = SimpleNamespace(sandbox_backend="modal", workspace_path=str(workspace))
    published: list = []
    box: dict = {
        "handle": SimpleNamespace(kind="modal", provider_sandbox_name="old", terminate=lambda: None)
    }
    terminated: list = []

    def _terminate() -> None:
        terminated.append("yes")

    box["handle"] = SimpleNamespace(kind="modal", provider_sandbox_name="old", terminate=_terminate)

    def _get(_sid):
        return box["handle"]

    def _unregister(sid):
        box["handle"] = None
        box["unregistered"] = sid

    def _resolve(*_args, **kwargs):
        box["resolve"] = kwargs
        box["handle"] = SimpleNamespace(
            kind="modal", provider_sandbox_name="sbx-new", terminate=_terminate
        )

    monkeypatch.setattr(sandbox_svc, "get_active_handle", _get)
    monkeypatch.setattr(sandbox_svc, "unregister_handle", _unregister)
    monkeypatch.setattr(sandbox_svc, "resolve_deepagents_backend", _resolve)
    monkeypatch.setattr(sandbox_svc.Config, "load", lambda: SimpleNamespace())
    monkeypatch.setattr("agent.deepagents_runtime.skill_source_dirs", lambda: ["/skills"])
    monkeypatch.setattr(
        sandbox_svc.sandbox_event_bus, "publish", lambda status: published.append(status.status)
    )
    monkeypatch.setattr(
        sandbox_svc.SandboxSettingsService,
        "get",
        lambda: _settings(backend="modal", modal_configured=True),
    )
    svc = sandbox_svc.SessionSandboxService(SimpleNamespace(get_session=lambda _sid: session))
    started = svc.start("s1")
    assert workspace.is_dir()
    assert started.status == "running"
    assert started.provider_sandbox_name == "sbx-new"
    assert box["resolve"]["backend_override"] == "modal"
    assert box["resolve"]["background_sync"] is True
    assert box["resolve"]["sync_workspace"] is True
    assert published[0] == "starting"

    box["handle"] = SimpleNamespace(
        kind="modal", provider_sandbox_name="sbx-new", terminate=_terminate
    )
    stopped = svc.stop("s1")
    assert terminated == ["yes"]
    assert box["unregistered"] == "s1"
    assert stopped.status == "stopped"
    assert "stopping" in published

    result = svc.restart("s1")
    assert result.status == "running"

    monkeypatch.setattr(sandbox_svc, "get_active_handle", lambda _sid: None)
    quiet = svc.stop("s1")
    assert quiet.status == "stopped"

    def _boom(_status):
        raise RuntimeError("bus down")

    monkeypatch.setattr(sandbox_svc.sandbox_event_bus, "publish", _boom)
    swallowed = svc.stop("s1")
    assert swallowed.session_id == "s1"


def test_session_sandbox_start_stop_errors(monkeypatch):
    monkeypatch.setattr(sandbox_svc.SandboxSettingsService, "get", lambda: _settings())
    monkeypatch.setattr(sandbox_svc, "get_active_handle", lambda _sid: None)
    empty = sandbox_svc.SessionSandboxService(SimpleNamespace(get_session=lambda _sid: None))
    with pytest.raises(KeyError):
        empty.start("missing")
    with pytest.raises(KeyError):
        empty.stop("missing")
    with pytest.raises(KeyError):
        empty.restart("missing")

    builtin = SimpleNamespace(sandbox_backend="builtin", workspace_path="/ws")
    svc = sandbox_svc.SessionSandboxService(SimpleNamespace(get_session=lambda _sid: builtin))
    with pytest.raises(ValueError, match="only available when Modal"):
        svc.start("s1")

    modal = SimpleNamespace(sandbox_backend="modal", workspace_path="/ws")
    monkeypatch.setattr(
        sandbox_svc.SandboxSettingsService,
        "get",
        lambda: _settings(modal_configured=False, backend="modal"),
    )
    svc = sandbox_svc.SessionSandboxService(SimpleNamespace(get_session=lambda _sid: modal))
    with pytest.raises(ValueError, match="modal_token_id"):
        svc.start("s1")

    monkeypatch.setattr(
        sandbox_svc.SandboxSettingsService,
        "get",
        lambda: _settings(modal_configured=True, backend="modal"),
    )
    nowork = SimpleNamespace(sandbox_backend="modal", workspace_path="")
    svc = sandbox_svc.SessionSandboxService(SimpleNamespace(get_session=lambda _sid: nowork))
    with pytest.raises(ValueError, match="workspace is not ready"):
        svc.start("s1")
