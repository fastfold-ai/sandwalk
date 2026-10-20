"""Coverage for run cancellation helpers, background task watch, and env snapshots."""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace

from agent.runner.background_watch import BackgroundWatchMixin
from agent_server.bench_service.environment import (
    _core_packages,
    _mcp_snapshot,
    _runtime_settings,
    _sandbox_settings,
    _skills_snapshot,
)
from agent_server.service.lifecycle import (
    _cancel_task,
    _loop_for_session,
    _task_belongs_to,
    _task_loop,
)


def test_lifecycle_task_helpers(monkeypatch) -> None:
    assert _loop_for_session(SimpleNamespace(source="cli")) is None
    assert _task_loop(object()) is None

    class Broken:
        def get_loop(self):
            raise RuntimeError("loop")

    assert _task_loop(Broken()) is None
    assert _task_loop(SimpleNamespace(get_loop=lambda: "nope")) is None
    loop = asyncio.new_event_loop()
    try:
        task = SimpleNamespace(get_loop=lambda: loop, cancelled=False)

        def cancel():
            task.cancelled = True

        task.cancel = cancel
        assert _cancel_task(object()) is False
        assert _cancel_task(task) is True
        assert task.cancelled is True
        assert _task_belongs_to(task, None) is True
        assert _task_belongs_to(Broken(), loop) is True
        assert _task_belongs_to(task, loop) is True
    finally:
        loop.close()

    def hide_bench():
        raise ImportError("bench")

    monkeypatch.setattr(
        "agent_server.bench_service.runtime.bench_loop",
        hide_bench,
    )
    # Import happens inside the helper; force the import itself to fail.
    import sys

    monkeypatch.setitem(sys.modules, "agent_server.bench_service.runtime", None)
    assert _loop_for_session(SimpleNamespace(source="bench")) is None


def test_background_watch_notifies_and_probes(tmp_path, monkeypatch, capsys) -> None:
    watcher = BackgroundWatchMixin()
    watcher._headless = True
    watcher._notify_terminal_task_completion("t", "completed", "done", "out")
    watcher._headless = False
    monkeypatch.setattr("agent.runner._is_warp_terminal_env", lambda: False)
    watcher._notify_terminal_task_completion("t", "nope")
    monkeypatch.setattr("agent.runner._is_warp_terminal_env", lambda: True)
    monkeypatch.setattr("agent.runner._sanitize_notification_text", lambda text: text)
    watcher._notify_terminal_task_completion("task-1", "failed", "boom", "out.txt")
    captured = capsys.readouterr().out
    assert "777;notify" in captured

    watcher._bg_watch_lock = threading.Lock()
    watcher._bg_watch_state = {}
    watcher._bg_watchers = {}
    watcher.refresh_background_watch_status()
    assert watcher.get_background_watch_status() == []

    output = tmp_path / "task.txt"
    output.write_text("exit_code: 0\n", encoding="utf-8")
    watcher._bg_watch_state = {
        "s1": {"pending_task_ids": ["task-1", " "], "output_files": {"task-1": str(output)}}
    }
    watcher.session = SimpleNamespace(console=None, config=None, tool_expand_store=None, transcript=None)

    class Renderer:
        def __init__(self, *args, **kwargs) -> None:
            self.notes = []

        def render_task_notification(self, *args):
            self.notes.append(args)

    monkeypatch.setattr("ui.traces.TraceRenderer", Renderer)
    watcher._headless = True
    watcher.refresh_background_watch_status(force=True)
    assert watcher._bg_watch_state["s1"]["completed_task_ids"] == ["task-1"]
    status = watcher.get_background_watch_status(include_inactive=False)
    assert status == []
    alive = watcher.get_background_watch_status()
    assert alive[0]["watcher_alive"] is False


def test_bench_environment_helpers(monkeypatch) -> None:
    assert isinstance(_core_packages(), dict)

    def boom():
        raise RuntimeError("settings")

    monkeypatch.setattr("agent_server.settings_service.SettingsService.get", boom)
    assert _runtime_settings() == {}
    monkeypatch.setattr("agent_server.sandbox_settings_service.SandboxSettingsService.get", boom)
    assert _sandbox_settings() == {}
    monkeypatch.setattr("agent.skills.list_skills", boom)
    assert _skills_snapshot() == []
    assert _mcp_snapshot(None) == []
    deps = SimpleNamespace(store=SimpleNamespace(list_mcp_servers=boom))
    assert _mcp_snapshot(deps) == []
    deps.store.list_mcp_servers = lambda enabled_only=False: [
        SimpleNamespace(id="1", name="PyMOL", transport="stdio", catalog_id="pymol", enabled=True)
    ]
    rows = _mcp_snapshot(deps)
    assert rows[0]["name"] == "PyMOL"
