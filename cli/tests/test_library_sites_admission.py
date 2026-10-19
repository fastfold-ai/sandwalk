"""Edge branches for library sync, sites admission, run capacity, and DDI.

No live model calls and no network. HTTP-backed site clients stay mocked.
"""

from __future__ import annotations

import asyncio
import base64
import io
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from langgraph.errors import GraphInterrupt
from langgraph.types import Command

import agent_server.run_admission as admission
import agent_server.sites_service.core as sites_core
from agent.runner.deepagents_run import DeepAgentsRunMixin
from agent.runner.multimodal_user_message import MultimodalInjectionError
from agent_server.library.blobs import LibraryBlobStore
from agent_server.library.service import _BACKFILL_META_KEY, LibraryService
from agent_server.service import AgentService
from agent_server.sites_service.cloud import PublishedSite
from agent_server.sites_service.core import SitesService
from agent_server.store import AgentStore
from tools.safety_ddi import ddi_predict

_AZOLE = "CCCCCCCCCCCCn1ccnc1CCN(C)C"


def _library(tmp_path: Path) -> tuple[AgentStore, LibraryService]:
    store = AgentStore(tmp_path / "agent.db", exclusive=True)
    service = AgentService(store)
    library = LibraryService(
        store,
        service,
        blobs=LibraryBlobStore(tmp_path / "library"),
    )
    return store, library


def _html_tree(root: Path, body: str = "<h1>Site</h1>") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.html").write_text(body, encoding="utf-8")
    (root / "app.js").write_text("console.log('site')", encoding="utf-8")
    return root


def _sites(tmp_path: Path) -> tuple[AgentStore, SitesService, Path, Path]:
    workspace = tmp_path / "workspace"
    source = _html_tree(workspace / "dist")
    store = AgentStore(tmp_path / "agent.db", exclusive=True)
    service = SitesService(store, root=tmp_path / "managed")
    return store, service, workspace, source


class _Cfg:
    def __init__(self, values: dict | None = None) -> None:
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)


class _Agent:
    def __init__(self) -> None:
        self.calls: list[tuple[object, dict]] = []

    def astream_events(self, stream_input, version="v2", config=None):
        self.calls.append((stream_input, config or {}))
        return object()


class _Spin:
    def __init__(self, console, phase="planning") -> None:
        self.console = console
        self.phase = phase
        self.entered = False
        self.refreshed = False
        self.stopped = 0

    def __enter__(self):
        self.entered = True
        return self

    def start_async_refresh(self) -> None:
        self.refreshed = True

    def stop(self) -> None:
        self.stopped += 1


class _Handle:
    def __init__(self, *, kind: str = "modal", fail: bool = False) -> None:
        self.kind = kind
        self.fail = fail
        self.pulled = False

    def pull(self) -> None:
        self.pulled = True
        if self.fail:
            raise RuntimeError("pull failed")


class _DeepRunner(DeepAgentsRunMixin):
    def __init__(self, provider: str = "openai", *, headless: bool = True) -> None:
        self.session = SimpleNamespace(
            config=_Cfg(
                {
                    "llm.provider": provider,
                    "agent.group_tool_traces": False,
                    "agent.tool_trace_detail_limit": 4,
                }
            ),
            console=SimpleNamespace(name="console"),
            transcript=None,
            tool_expand_store={"expanded": False},
        )
        self._headless = headless
        self.trace_store = None
        self.trajectory = SimpleNamespace(session_id="")
        self.agent = _Agent()
        self.sandbox_handle = None
        self.tool_sandbox = SimpleNamespace(kind="local")
        self.built = None

    def _make_error_result(self, query, message, elapsed, prefix_sdk=True):
        return {"error": message, "elapsed": elapsed, "prefix": prefix_sdk}

    def _print_friendly_error(self, title, body) -> None:
        return None

    async def _build_deepagents_tools(self, *args):
        return ([], self.tool_sandbox, ["buf"], {"bash": "shell"}, "all", {"net"}, {"hidden"})

    def _build_deepagents_system_prompt(self, *args) -> str:
        return "SYSTEM"

    def _build_deepagents_user_prompt(self, query, ctx):
        return f"user:{query}", ctx

    async def _build_deepagents_agent(self, *args):
        return self.agent, self.sandbox_handle

    def _build_deepagents_exec_result(
        self, query, result, t0, model_name, sandbox, trace_events, pricing
    ):
        self.built = {
            "query": query,
            "result": result,
            "model_name": model_name,
            "sandbox": sandbox,
            "trace_events": trace_events,
            "pricing": pricing,
        }
        return {"ok": True, "model": model_name}


def _install_deep_runtime(monkeypatch: pytest.MonkeyPatch, state: dict) -> None:
    monkeypatch.setattr("ui.status.ThinkingStatus", _Spin)
    monkeypatch.setattr("ui.traces.TraceRenderer", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(
        "ui.terminal.transcript.sink.TranscriptSink",
        lambda transcript: SimpleNamespace(transcript=transcript),
    )
    monkeypatch.setattr(
        "agent.deepagents_runtime.build_chat_model",
        lambda config: SimpleNamespace(profile={"vision": True}),
    )

    async def process_events(events, **kwargs):
        state["process"].append(kwargs)
        activity = kwargs.get("on_activity")
        if activity is not None:
            activity("status", phase="planning")
            activity("stream", delta="a")
            activity("stream", delta="b")
        if state.get("boom"):
            state["boom"] = False
            raise RuntimeError("stream broke")
        if state.get("graph"):
            state["graph"] = False
            raise GraphInterrupt()
        return {
            "full_text": ["part"],
            "tool_calls": [{"name": "read"}],
            "token_usage": {"input_tokens": 2},
            "model_call_count": 1,
            "empty_model_turns": [],
        }

    def extract(agent, config):
        pending = state["interrupts"]
        if not pending:
            return None
        return pending.pop(0)

    def collect(**kwargs):
        state["collected"] = kwargs
        return [{"type": "approve"}]

    def apply(decisions, requests, session_id=None):
        state["applied"] = (decisions, requests, session_id)

    def clear(session_id):
        state["cleared"].append(session_id)

    def set_hitl(**kwargs):
        state["hitl"] = kwargs
        return "hitl-token"

    def reset_hitl(token):
        state["reset"] = token

    def build_mm(prompt, **kwargs):
        state["mm"].append(kwargs)
        if state.get("mm_fail"):
            raise MultimodalInjectionError("pixels missing")
        return [{"type": "text", "text": prompt}]

    monkeypatch.setattr("agent.deepagents_runtime.process_events", process_events)
    monkeypatch.setattr("agent.hitl.extract_interrupt_payload", extract)
    monkeypatch.setattr("agent.hitl.collect_decisions_for_interrupt", collect)
    monkeypatch.setattr("agent.hitl.apply_grants_from_decisions", apply)
    monkeypatch.setattr("agent.hitl.clear_session_grants", clear)
    monkeypatch.setattr("agent.hitl.set_hitl_context", set_hitl)
    monkeypatch.setattr("agent.hitl.reset_hitl_context", reset_hitl)
    monkeypatch.setattr(
        "agent.runner.multimodal_user_message.build_multimodal_user_content",
        build_mm,
    )


def _deep_state() -> dict:
    return {
        "process": [],
        "interrupts": [],
        "cleared": [],
        "mm": [],
        "graph": False,
        "mm_fail": False,
    }


def test_library_sync_skips_and_fallback_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, library = _library(tmp_path)
    try:
        real = tmp_path / "real"
        (real / "uploads" / "subdir").mkdir(parents=True)
        (real / "outputs").mkdir()
        (real / "uploads" / "keep.txt").write_text("hello", encoding="utf-8")
        (real / "uploads" / "empty.txt").write_text("", encoding="utf-8")
        (real / "uploads" / "bad.txt").write_text("bad", encoding="utf-8")
        (real / "uploads" / "boom.txt").write_text("boom", encoding="utf-8")
        (real / "uploads" / "odd.txt").write_text("odd", encoding="utf-8")
        (real / "uploads" / "Thumbs.db").write_text("x", encoding="utf-8")
        (real / "uploads" / ".secret").write_text("x", encoding="utf-8")
        (real / "uploads" / "mod.pyc").write_bytes(b"pyc")
        (real / "uploads" / "node_modules").mkdir()
        (real / "uploads" / "node_modules" / "pkg.py").write_text("x", encoding="utf-8")
        (real / "uploads" / "subdir" / "nested.txt").write_text("nested", encoding="utf-8")
        (real / "outputs" / "copy.txt").write_text("hello", encoding="utf-8")
        fallback = tmp_path / "fallback"
        (fallback / "uploads").mkdir(parents=True)
        (fallback / "uploads" / "fb.txt").write_text("fallback", encoding="utf-8")
        marker = tmp_path / "not-a-dir.txt"
        marker.write_text("x", encoding="utf-8")

        real_session = store.create_session(title="real", workspace_path=str(real))
        file_session = store.create_session(title="file", workspace_path=str(marker))
        raise_session = store.create_session(title="raise", workspace_path=None)
        missing_session = store.create_session(title="missing", workspace_path=None)

        def default_workspace_path(session_id: str) -> Path:
            if session_id == raise_session.id:
                raise RuntimeError("no workspace")
            if session_id == missing_session.id:
                return tmp_path / "does-not-exist"
            if session_id == file_session.id:
                return fallback
            return tmp_path / "unused"

        monkeypatch.setattr(
            "agent_server.service.default_workspace_path",
            default_workspace_path,
        )
        real_put = library.blobs.put_file

        def put_file(path: Path):
            if path.name == "bad.txt":
                raise RuntimeError("unreadable")
            return real_put(path)

        library.blobs.put_file = put_file  # type: ignore[method-assign]
        real_stat = Path.stat
        seen: dict[str, int] = {}

        def stat(self, *args, **kwargs):
            if self.name == "boom.txt":
                seen["boom"] = seen.get("boom", 0) + 1
                if seen["boom"] > 1:
                    raise OSError("gone")
            return real_stat(self, *args, **kwargs)

        real_relative = Path.relative_to

        def relative_to(self, other, *args, **kwargs):
            if self.name == "odd.txt":
                raise ValueError("outside")
            return real_relative(self, other, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", stat)
        monkeypatch.setattr(Path, "relative_to", relative_to)

        result = library.sync_from_workspaces()
        assert result.scanned_sessions == 2
        assert result.ingested == 3
        assert result.linked == 1
        assert result.skipped == 3
        names = {item.original_name for item in store.list_library_items()}
        assert names == {"keep.txt", "nested.txt", "fb.txt"}
        assert real_session.id
        direct = tmp_path / "direct.txt"
        direct.write_text("", encoding="utf-8")
        assert library._ingest_workspace_file(direct, origin_session_id=real_session.id) == "skipped"

        def always_stat(self, *args, **kwargs):
            raise OSError("missing")

        monkeypatch.setattr(Path, "stat", always_stat)
        missing = tmp_path / "missing-stat.txt"
        assert library._ingest_workspace_file(missing, origin_session_id="s") == "skipped"
        monkeypatch.setattr(Path, "stat", real_stat)
    finally:
        store.close()


def test_library_backfill_race_and_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, library = _library(tmp_path)
    try:
        calls = {"n": 0}
        real_get = store.get_meta

        def get_meta(key: str):
            if key == _BACKFILL_META_KEY:
                calls["n"] += 1
                return None if calls["n"] == 1 else "1"
            return real_get(key)

        def unexpected():
            raise AssertionError("sync should not run once meta is set")

        monkeypatch.setattr(store, "get_meta", get_meta)
        library.sync_from_workspaces = unexpected  # type: ignore[method-assign]
        library.ensure_workspace_backfill()
        assert calls["n"] >= 2
        assert real_get(_BACKFILL_META_KEY) != "1"

        def boom():
            raise RuntimeError("scan failed")

        library.sync_from_workspaces = boom  # type: ignore[method-assign]
        monkeypatch.setattr(store, "get_meta", real_get)
        library.ensure_workspace_backfill()
        assert store.get_meta(_BACKFILL_META_KEY) != "1"
    finally:
        store.close()


def test_library_content_and_chat_edges(tmp_path: Path) -> None:
    store, library = _library(tmp_path)
    try:
        with pytest.raises(KeyError, match="missing"):
            library.write_content("missing", b"x")

        item = library.ingest_bytes(b"alpha", filename="notes.txt", mime="text/plain")
        binary = library.ingest_bytes(b"\x00\x01\xff", filename="blob.zzz")
        garbled = library.ingest_bytes(b"\xff\xfe not utf8", filename="garbled.txt")
        assert library.content_path("missing") is None
        blob = library.blobs.path_for(item.sha256)
        blob.unlink()
        assert library.content_path(item.id) is None
        assert library.read_file_content("missing") is None
        assert library.read_file_content(item.id) is None

        binary_payload = library.read_file_content(binary.id)
        assert binary_payload is not None
        assert binary_payload.encoding == "base64"
        assert binary_payload.mime_type == "application/octet-stream"
        assert binary_payload.content == base64.b64encode(b"\x00\x01\xff").decode("ascii")

        garbled_payload = library.read_file_content(garbled.id)
        assert garbled_payload is not None
        assert garbled_payload.encoding == "base64"

        def update_missing(*args, **kwargs):
            return None

        store.update_library_item_content = update_missing  # type: ignore[method-assign]
        with pytest.raises(KeyError):
            library.write_content(binary.id, b"next")

        with pytest.raises(KeyError):
            library.use_in_chat(["missing-id"])

        def ensure_workspace(session_id: str):
            return SimpleNamespace(id=session_id, workspace_path="")

        library.agent_service.ensure_workspace = ensure_workspace  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="no workspace"):
            library.use_in_chat([binary.id], title="Library")

        def ingest_bytes(*args, **kwargs):
            raise RuntimeError("db down")

        library.ingest_bytes = ingest_bytes  # type: ignore[method-assign]
        library.try_ingest_upload(
            b"abc",
            filename="a.txt",
            mime="text/plain",
            session_id="sess",
        )
    finally:
        store.close()


def test_sites_name_roots_and_validation(tmp_path: Path) -> None:
    saved = dict(SitesService._tokens)
    store, service, workspace, source = _sites(tmp_path)
    try:
        with pytest.raises(ValueError, match="cannot be empty"):
            service._name("  ")
        with pytest.raises(ValueError, match="100"):
            service._name("n" * 101)

        with pytest.raises(ValueError, match="Session not found"):
            service._allowed_roots(session_id="missing", project_id=None, workspace_root=None)
        bare = store.create_session(title="bare", workspace_path=None)
        with pytest.raises(ValueError, match="no workspace"):
            service._allowed_roots(session_id=bare.id, project_id=None, workspace_root=None)
        with pytest.raises(ValueError, match="Project not found"):
            service._allowed_roots(session_id=None, project_id="missing", workspace_root=None)
        empty_project = store.create_project(name="Empty")
        with pytest.raises(ValueError, match="no folder"):
            service._allowed_roots(
                session_id=None,
                project_id=empty_project.id,
                workspace_root=None,
            )
        folder_a = tmp_path / "proj-a"
        folder_b = tmp_path / "proj-b"
        folder_a.mkdir()
        folder_b.mkdir()
        project_a = store.create_project(name="A", folder_path=str(folder_a))
        project_b = store.create_project(name="B", folder_path=str(folder_b))
        owned = store.create_session(
            title="owned",
            workspace_path=str(workspace),
            project_id=project_a.id,
        )
        with pytest.raises(ValueError, match="does not belong"):
            service._allowed_roots(
                session_id=owned.id,
                project_id=project_b.id,
                workspace_root=None,
            )
        with pytest.raises(ValueError, match="required"):
            service._allowed_roots(session_id=None, project_id=None, workspace_root=None)

        outside = tmp_path / "outside"
        outside.mkdir()
        with pytest.raises(ValueError, match="must stay within"):
            service.resolve_source(outside, workspace_root=workspace)
        with pytest.raises(ValueError, match="managed site"):
            service.resolve_source(service.root, workspace_root=service.root)

        loose = tmp_path / "file.txt"
        loose.write_text("x", encoding="utf-8")
        with pytest.raises(ValueError, match="must be a directory"):
            SitesService.validate(loose)
        empty = tmp_path / "empty-site"
        empty.mkdir()
        with pytest.raises(ValueError, match="index.html"):
            SitesService.validate(empty)
        linked = tmp_path / "linked-index"
        linked.mkdir()
        (linked / "index.html").symlink_to(source / "index.html")
        with pytest.raises(ValueError, match="regular index.html"):
            SitesService.validate(linked)
        (source / "alias.js").symlink_to(source / "app.js")
        with pytest.raises(ValueError, match="symlinks"):
            SitesService.validate(source)
        (source / "alias.js").unlink()

        original_files = sites_core.MAX_SITE_FILES
        original_bytes = sites_core.MAX_SITE_BYTES
        try:
            sites_core.MAX_SITE_FILES = 1
            with pytest.raises(ValueError, match="cannot contain more than"):
                SitesService.validate(source)
            sites_core.MAX_SITE_FILES = original_files
            sites_core.MAX_SITE_BYTES = 1
            with pytest.raises(ValueError, match="100 MB"):
                SitesService.validate(source)
        finally:
            sites_core.MAX_SITE_FILES = original_files
            sites_core.MAX_SITE_BYTES = original_bytes
    finally:
        SitesService._tokens = saved
        store.close()


def test_sites_register_publish_and_delete_edges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    saved = dict(SitesService._tokens)
    store, service, workspace, source = _sites(tmp_path)
    try:
        with pytest.raises(KeyError, match="Site not found"):
            service.register(
                name="Example",
                source=source,
                workspace_root=workspace,
                site_id="missing",
            )
        site = service.register(name="Example", source=source, workspace_root=workspace)
        renamed = service.rename(site.id, "Renamed")
        assert renamed.name == "Renamed"
        with pytest.raises(KeyError, match="Site not found"):
            service.rename("missing", "Other")
        updated = service.register(
            name="Renamed again",
            source=source,
            workspace_root=workspace,
            site_id=site.id,
        )
        assert updated.name == "Renamed again"
        original = (Path(site.storage_path) / "index.html").read_text(encoding="utf-8")

        real_replace = os.replace

        def replace(src, dst):
            if Path(src).name.startswith(".staging-"):
                raise OSError("stage replace failed")
            return real_replace(src, dst)

        monkeypatch.setattr(sites_core.os, "replace", replace)
        with pytest.raises(OSError, match="stage replace failed"):
            service.register(
                name=updated.name,
                source=source,
                workspace_root=workspace,
                site_id=site.id,
            )
        monkeypatch.setattr(sites_core.os, "replace", real_replace)
        assert (Path(site.storage_path) / "index.html").read_text(encoding="utf-8") == original
        assert not any(path.name.startswith(".staging-") for path in service.root.iterdir())
        assert not any(path.name.startswith(".backup-") for path in service.root.iterdir())

        (source / "index.html").write_text("<h1>Edited</h1>", encoding="utf-8")

        def update_missing(*args, **kwargs):
            return None

        monkeypatch.setattr(store, "update_site_content", update_missing)
        with pytest.raises(RuntimeError, match="Failed to update site"):
            service.register(
                name=updated.name,
                source=source,
                workspace_root=workspace,
                site_id=site.id,
            )
        assert (Path(site.storage_path) / "index.html").read_text(encoding="utf-8") == original

        with pytest.raises(KeyError, match="Site not found"):
            service.create_preview("missing")
        url, _expires = service.create_preview(site.id)
        token = url.rstrip("/").rsplit("/", 1)[-1]
        assert service.preview_site("other-site", token) is None
        with SitesService._token_lock:
            stored_id, _expiry = SitesService._tokens[token]
            SitesService._tokens[token] = (stored_id, datetime.now(UTC) - timedelta(seconds=5))
        assert service.preview_site(site.id, token) is None

        with pytest.raises(KeyError, match="Site not found"):
            service.publish("missing")
        (Path(site.storage_path) / "index.html").write_text("tampered", encoding="utf-8")
        with pytest.raises(ValueError, match="content changed"):
            service.publish(site.id)
        (Path(site.storage_path) / "index.html").write_text(original, encoding="utf-8")

        def mark_missing(*args, **kwargs):
            return None

        monkeypatch.setattr(store, "mark_site_published", mark_missing)

        class Publisher:
            def publish(self, **kwargs):
                assert kwargs["slug"] == "custom"
                return PublishedSite(url="https://example.sandwalk.site", site_id="cloud-1")

        service.publisher = Publisher()
        with pytest.raises(RuntimeError, match="local metadata"):
            service.publish(site.id, slug="custom")

        with pytest.raises(KeyError, match="Site not found"):
            service.delete("missing")
        monkeypatch.setattr(store, "delete_site", lambda site_id: False)
        with pytest.raises(KeyError, match="Site not found"):
            service.delete(site.id)
        assert Path(site.storage_path).is_dir()
    finally:
        SitesService._tokens = saved
        store.close()


def test_run_admission_invalid_env_and_waiter_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SANDWALK_MAX_CONCURRENT_RUNS", "nope")
    monkeypatch.setenv("SANDWALK_MIN_FREE_MEMORY_MB", "also-nope")
    gate = admission.RunAdmission(max_runs=7, min_free_mb=10, memory_probe=lambda: None)
    assert gate.max_runs() == 7
    assert gate.min_free_mb() == 10

    monkeypatch.delenv("SANDWALK_MAX_CONCURRENT_RUNS", raising=False)
    monkeypatch.delenv("SANDWALK_MIN_FREE_MEMORY_MB", raising=False)
    busy = admission.RunAdmission(max_runs=1, min_free_mb=0, memory_probe=lambda: None)
    busy.acquire()
    entered = threading.Event()

    def waiter() -> None:
        def on_wait(message: str) -> None:
            raise RuntimeError(message)

        busy.acquire(on_wait=on_wait, timeout_s=5)
        entered.set()

    thread = threading.Thread(target=waiter)
    thread.start()
    time.sleep(0.2)
    busy.release()
    assert entered.wait(2)
    busy.release()
    thread.join(1)


def test_run_admission_refresh_and_memory_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert admission.run_admission() is admission._admission

    class Boom:
        def get(self, key: str):
            raise RuntimeError("cfg")

    admission.refresh_from_config(Boom())

    class Cfg:
        def __init__(self, data: dict) -> None:
            self.data = data

        def get(self, key: str):
            return self.data[key]

    monkeypatch.delenv(admission.ENV_MAX_RUNS, raising=False)
    monkeypatch.delenv(admission.ENV_MIN_FREE_MB, raising=False)
    saved = (admission._admission._max_runs, admission._admission._min_free_mb)
    try:
        admission.refresh_from_config(
            Cfg({"agent.max_concurrent_runs": 0, "agent.min_free_memory_mb": ""})
        )
        assert admission._admission._max_runs is None
        assert admission._admission._min_free_mb is None
        admission.refresh_from_config(
            Cfg({"agent.max_concurrent_runs": "0", "agent.min_free_memory_mb": None})
        )
        assert admission._admission._max_runs is None
        admission.refresh_from_config(
            Cfg({"agent.max_concurrent_runs": "", "agent.min_free_memory_mb": 0})
        )
        assert admission._admission._max_runs is None
        assert admission._admission._min_free_mb == 0
        admission.refresh_from_config(
            Cfg({"agent.max_concurrent_runs": 6, "agent.min_free_memory_mb": 128})
        )
        assert admission._admission.max_runs() == 6
        assert admission._admission.min_free_mb() == 128
    finally:
        admission._admission.configure(max_runs=saved[0], min_free_mb=saved[1])

    def timeout_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="sysctl", timeout=2)

    monkeypatch.setattr(admission.subprocess, "run", timeout_run)
    assert admission._sysctl_int("hw.memsize") is None

    def os_error(*args, **kwargs):
        raise OSError("sysctl")

    monkeypatch.setattr(admission.subprocess, "run", os_error)
    assert admission._sysctl_int("hw.memsize") is None

    class Completed:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    monkeypatch.setattr(admission.subprocess, "run", lambda *args, **kwargs: Completed("  "))
    assert admission._sysctl_int("hw.memsize") is None
    monkeypatch.setattr(admission.subprocess, "run", lambda *args, **kwargs: Completed("nope"))
    assert admission._sysctl_int("hw.memsize") is None

    fake_psutil = ModuleType("psutil")

    class _VM:
        available = 512 * 1024 * 1024

    def virtual_memory():
        if getattr(fake_psutil, "fail", False):
            raise RuntimeError("psutil")
        return _VM()

    fake_psutil.virtual_memory = virtual_memory
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
    monkeypatch.setattr(admission.sys, "platform", "darwin")
    assert admission.available_memory_mb() == 512
    fake_psutil.fail = True
    monkeypatch.setattr(admission.subprocess, "run", os_error)
    assert admission.available_memory_mb() is None
    assert admission.total_memory_mb() is None

    page_stat = (
        "Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
        "Pages free: 100.\n"
        "Pages inactive: 50.\n"
        "Pages speculative: 25.\n"
    )
    monkeypatch.setattr(
        admission.subprocess,
        "run",
        lambda *args, **kwargs: Completed(page_stat),
    )
    assert admission.available_memory_mb() == (175 * 16384) // (1024 * 1024)
    blank_page = (
        "Mach Virtual Memory Statistics: (page size of bytes)\n"
        "Pages free: 1.\nPages inactive: 1.\nPages speculative: 1.\n"
    )
    monkeypatch.setattr(
        admission.subprocess,
        "run",
        lambda *args, **kwargs: Completed(blank_page),
    )
    assert admission.available_memory_mb() == 0

    monkeypatch.setattr(admission.sys, "platform", "linux")
    monkeypatch.setattr(admission.platform, "system", lambda: "Linux")
    meminfo = {"mode": "raise", "text": ""}
    real_open = open

    def fake_open(file, *args, **kwargs):
        if file == "/proc/meminfo":
            if meminfo["mode"] == "raise":
                raise OSError("no proc")
            return io.StringIO(meminfo["text"])
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fake_open)
    assert admission.available_memory_mb() is None
    meminfo["mode"] = "text"
    meminfo["text"] = "MemFree: 1 kB\nMemAvailable: 4096 kB\n"
    assert admission.available_memory_mb() == 4
    meminfo["text"] = "MemFree: 1 kB\n"
    assert admission.available_memory_mb() is None

    def sysconf(name: str) -> int:
        return {"SC_PHYS_PAGES": 512, "SC_PAGE_SIZE": 4096}[name]

    monkeypatch.setattr(admission.os, "sysconf", sysconf)
    assert admission.total_memory_mb() == 512 * 4096 // (1024 * 1024)

    def sysconf_bad(name: str) -> int:
        raise ValueError(name)

    monkeypatch.setattr(admission.os, "sysconf", sysconf_bad)
    assert admission.total_memory_mb() is None

    monkeypatch.setattr(admission.sys, "platform", "win32")
    monkeypatch.setattr(admission.platform, "system", lambda: "Windows")
    assert admission.available_memory_mb() is None


def test_deepagents_interrupt_modal_and_spinner(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _deep_state()
    _install_deep_runtime(monkeypatch, state)
    events: list[str] = []

    def progress(event, **payload):
        events.append(event)
        if event == "approval_resolved":
            raise RuntimeError("ui")
        return "ack"

    runner = _DeepRunner("openai")
    runner.trace_store = SimpleNamespace(name="traces")
    runner.session.transcript = SimpleNamespace(name="transcript")
    runner.sandbox_handle = _Handle()
    state["interrupts"] = [
        {"action_requests": [{"name": "bash"}], "review_configs": [{"action_name": "bash"}]}
    ]
    result = asyncio.run(
        runner._run_async_deepagents(
            "fold",
            {"session_id": "sess-123", "workspace_path": "/ws"},
            progress,
        )
    )
    assert result["ok"] is True
    assert result["model"] == "gpt-5.6-sol"
    assert runner.built["trace_events"] == []
    assert runner.built["result"]["full_text"] == ["part", "part"]
    assert runner.sandbox_handle.pulled is True
    assert events[0] == "status"
    assert events.count("stream") == 4
    assert "approval_resolved" in events
    assert isinstance(runner.agent.calls[1][0], Command)
    assert runner.agent.calls[0][1]["configurable"]["thread_id"] == "sess-123"
    assert state["process"][0]["group_tools"] is False
    assert state["process"][0]["tool_detail_limit"] == 4
    assert state["applied"][2] == "sess-123"
    assert state["cleared"] == ["sess-123"]
    assert state["reset"] == "hitl-token"
    assert state["mm"][0]["workspace_root"] == "/ws"
    assert state["mm"][0]["model_id"] == "gpt-5.6-sol"

    runner.session.config.values["llm.provider"] = "anthropic"
    runner.session.transcript = None
    runner.trace_store = None
    runner.sandbox_handle = _Handle(fail=True)
    state["graph"] = True
    state["interrupts"] = []
    quiet = asyncio.run(runner._run_async_deepagents("again", {}))
    assert quiet["model"] == "claude-sonnet-4-5-20250929"
    assert runner.built["trace_events"] is None
    assert runner.sandbox_handle.pulled is True
    assert runner.agent.calls[-1][1]["configurable"]["thread_id"].startswith("cli-")
    assert state["hitl"]["session_id"] is None

    state["mm_fail"] = True
    runner.session.config.values["llm.model"] = "explode"
    failed = asyncio.run(runner._run_async_deepagents("pixels", {"workspace_path": "  "}))
    assert failed["error"] == "pixels missing"
    assert state["mm"][-1]["workspace_root"] is None

    state["mm_fail"] = False
    spins: list[_Spin] = []

    class RecordingSpin(_Spin):
        def __init__(self, console, phase="planning") -> None:
            super().__init__(console, phase)
            spins.append(self)

    monkeypatch.setattr("ui.status.ThinkingStatus", RecordingSpin)
    live = _DeepRunner("openai", headless=False)
    live.agent = runner.agent
    done = asyncio.run(live._run_async_deepagents("spin"))
    assert done["ok"] is True
    assert spins[-1].entered is True
    assert spins[-1].refreshed is True
    assert spins[-1].stopped == 0

    def bad_model(config):
        raise ValueError("bad provider config")

    monkeypatch.setattr("agent.deepagents_runtime.build_chat_model", bad_model)
    valued = asyncio.run(live._run_async_deepagents("spin"))
    assert "bad provider config" in valued["error"]
    assert spins[-1].stopped == 2

    def interrupt_model(config):
        raise InterruptedError("stop")

    monkeypatch.setattr("agent.deepagents_runtime.build_chat_model", interrupt_model)
    with pytest.raises(InterruptedError, match="stop"):
        asyncio.run(live._run_async_deepagents("spin"))
    assert spins[-1].stopped == 1

    monkeypatch.setattr(
        "agent.deepagents_runtime.build_chat_model",
        lambda config: SimpleNamespace(profile=None),
    )
    monkeypatch.setattr(
        "agent.runner.deepagents_run._is_transient_transport_error",
        lambda exc: False,
    )
    monkeypatch.setattr(
        "agent.model_catalog.param_heal.apply_param_heal_from_error",
        lambda config, exc: False,
    )
    monkeypatch.setattr("agent.runner.deepagents_run._classify_llm_error", lambda exc: None)
    state["boom"] = True
    streamed = asyncio.run(live._run_async_deepagents("spin"))
    assert streamed["error"] == "stream broke"
    assert spins[-1].stopped == 1


def test_ddi_invalid_inputs_and_missing_rdkit(monkeypatch: pytest.MonkeyPatch) -> None:
    invalid = ddi_predict("notasmiles")
    assert invalid["error"].startswith("Invalid SMILES")
    assert "notasmiles" in invalid["summary"]

    monkeypatch.setitem(sys.modules, "rdkit", None)
    missing = ddi_predict("CCO")
    assert "RDKit is required" in missing["error"]
    assert missing["summary"] == missing["error"]


def test_ddi_motif_risk_and_comedication(monkeypatch: pytest.MonkeyPatch) -> None:
    imidazole = ddi_predict("c1cnc[nH]1")
    assert imidazole["overall_risk"] == "HIGH"
    assert imidazole["motif_flags"]["has_imidazole"] is True
    assert imidazole["cyp_profile"]["CYP3A4"]["inhibition_risk"] == "high"
    assert imidazole["cyp_profile"]["CYP2C19"]["inhibition_risk"] == "high"
    assert "High CYP inhibition risk" in imidazole["summary"]
    assert "azole motif" in imidazole["summary"]

    triazole = ddi_predict("c1ncn[nH]1")
    assert triazole["motif_flags"]["has_triazole"] is True
    assert triazole["motif_flags"]["has_imidazole"] is False
    assert triazole["overall_risk"] == "HIGH"

    furan = ddi_predict("c1ccoc1")
    assert furan["motif_flags"]["has_furan"] is True
    assert furan["mechanism_based_inhibition"]["risk"] is True
    assert "Furan" in furan["summary"]

    alkyne = ddi_predict("CC#C")
    assert any("alkyne" in reason for reason in alkyne["mechanism_based_inhibition"]["reasons"])
    mdp = ddi_predict("c1ccc2OCOc2c1")
    assert any("Methylenedioxy" in reason for reason in mdp["mechanism_based_inhibition"]["reasons"])

    amine = ddi_predict("CN(C)Cc1ccc(-c2ccccc2)cc1")
    assert amine["cyp_profile"]["CYP2D6"]["inhibition_risk"] == "high"
    assert amine["cyp_profile"]["CYP2C9"]["inhibition_risk"] == "moderate"

    acid = ddi_predict("CC(=O)O")
    assert acid["overall_risk"] == "LOW-MODERATE"
    assert "Carboxylic acid" in acid["cyp_profile"]["CYP2C9"]["reasons"][0]

    both = ddi_predict("NCC(=O)O")
    assert both["overall_risk"] == "MODERATE"
    assert both["cyp_profile"]["CYP2D6"]["inhibition_risk"] == "moderate"

    rings = ddi_predict("c1ccc2cc3ccccc3cc2c1")
    assert rings["cyp_profile"]["CYP1A2"]["score"] == 2
    assert "aromatic rings" in rings["cyp_profile"]["CYP1A2"]["reasons"][0]
    assert "Polycyclic" in rings["cyp_profile"]["CYP1A2"]["reasons"][1]

    bulky = ddi_predict("CCCCCCCCCCCCCCCCCCc1ccc(-c2ccccc2)cc1")
    assert any("Large lipophilic" in reason for reason in bulky["cyp_profile"]["CYP3A4"]["reasons"])

    pair = ddi_predict(_AZOLE, _AZOLE, note="combo")
    analysis = pair["comedication_analysis"]
    assert analysis["interaction_risk"] == "high"
    assert len(analysis["shared_metabolic_pathways"]) == 3
    assert "Co-medication interaction" in pair["summary"]
    assert "Moderate CYP inhibition risk" in pair["summary"]

    overlap = ddi_predict("CCO", "CC(=O)O")
    assert overlap["comedication_analysis"]["interaction_risk"] == "low"
    assert "Low metabolic pathway overlap" in overlap["summary"]

    bad_pair = ddi_predict("CCO", "notasmiles")
    assert "Invalid co-medication" in bad_pair["comedication_analysis"]["error"]
    assert bad_pair["overall_risk"] == "LOW"

    import rdkit.Chem as chem

    def no_smarts(smarts: str):
        return None

    monkeypatch.setattr(chem, "MolFromSmarts", no_smarts)
    blinded = ddi_predict("CCO", "CC")
    assert blinded["overall_risk"] == "LOW"
    assert blinded["motif_flags"]["nitrogen_heterocycles"] == 0
    assert blinded["motif_flags"]["basic_amines"] == 0
    assert blinded["motif_flags"]["has_imidazole"] is False
    assert blinded["motif_flags"]["has_triazole"] is False
    assert blinded["motif_flags"]["has_furan"] is False
    assert blinded["mechanism_based_inhibition"]["risk"] is False
    assert blinded["comedication_analysis"]["shared_metabolic_pathways"] == []
