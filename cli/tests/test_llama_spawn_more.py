"""Extra llama runtime and bench-spawn branches without a live llama CLI."""

from __future__ import annotations

import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from agent_server import llama_runtime as bridge
from agent_server.bench_service import spawn_core as spawn


@pytest.fixture(autouse=True)
def _reset_llama_state():
    bridge._set("idle")
    bridge._load_jobs.clear()
    bridge._install_job = None
    bridge._download_log.clear()
    bridge._serve_log.clear()
    bridge._mem_cache.clear()
    bridge._serve_proc = None
    yield
    bridge._set("idle")
    bridge._load_jobs.clear()
    bridge._install_job = None
    bridge._serve_proc = None


class _JsonResponse:
    def __init__(self, payload, status_code=200, error=None):
        self._payload = payload
        self.status_code = status_code
        self._error = error

    def json(self):
        if self._error:
            raise self._error
        return self._payload

    def raise_for_status(self):
        return None


class _HoldThread:
    """Record thread targets. start() must not run the real llama CLI."""

    def __init__(self, target=None, args=(), kwargs=None, **_extra):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}

    def start(self):
        return None


def test_models_payload_rejects_bad_responses(monkeypatch):
    monkeypatch.setattr(
        bridge.httpx,
        "get",
        lambda *_a, **_k: _JsonResponse({}, status_code=500),
    )
    assert bridge._models_payload() is None

    monkeypatch.setattr(
        bridge.httpx,
        "get",
        lambda *_a, **_k: _JsonResponse({}, error=ValueError("bad")),
    )
    assert bridge._models_payload() is None

    monkeypatch.setattr(
        bridge.httpx,
        "get",
        lambda *_a, **_k: _JsonResponse(["nope"]),
    )
    assert bridge._models_payload() == []


def test_catalog_filters_fit_query_and_bad_rows(monkeypatch):
    payload = [{"id": "org/fit:Q8", "status": {"value": "ready", "args": []}}]
    monkeypatch.setattr(bridge, "_models_payload", lambda: payload)
    monkeypatch.setattr(bridge, "_memory_bytes", lambda: 64_000_000_000)

    def _boom(*_a, **_k):
        raise bridge.httpx.HTTPError("down")

    monkeypatch.setattr(bridge.httpx, "get", _boom)
    offline = bridge.catalog("fit")
    assert offline["installed"][0]["id"] == "org/fit:Q8"
    assert offline["recommended"] == []

    monkeypatch.setattr(
        bridge.httpx,
        "get",
        lambda *_a, **_k: _JsonResponse({"not": "a list"}),
    )
    assert bridge.catalog()["recommended"] == []

    families = [
        "skip-me",
        {
            "featured": True,
            "brand": "Skip",
            "sizes": [
                "bad-size",
                {"name": "Empty", "builds": []},
                {"name": "NoRepo", "builds": [{"quant": "Q4"}]},
            ],
        },
        {
            "featured": True,
            "brand": "HugeBrand",
            "sizes": [
                {
                    "name": "Huge",
                    "builds": [
                        {
                            "repo": "org/huge",
                            "quant": "Q8",
                            "size": "9 GB",
                            "sizeBytes": 10**18,
                        }
                    ],
                }
            ],
        },
        {
            "featured": False,
            "brand": "SmallBrand",
            "sizes": [
                {
                    "name": "Tiny",
                    "vision": 0,
                    "builds": [
                        {"repo": "org/tiny", "quant": "Q8", "size": "1 MB", "sizeBytes": 10},
                        {"repo": "org/tiny-big", "quant": "", "size": "", "sizeBytes": 20},
                    ],
                }
            ],
        },
        {
            "featured": True,
            "brand": "FitBrand",
            "sizes": [
                {
                    "name": "Fit",
                    "vision": True,
                    "builds": [
                        {
                            "repo": "org/fit",
                            "quant": "Q8",
                            "size": "1 GB",
                            "sizeBytes": 100,
                        }
                    ],
                }
            ],
        },
    ]
    monkeypatch.setattr(
        bridge.httpx,
        "get",
        lambda *_a, **_k: _JsonResponse(families),
    )
    featured = bridge.catalog()
    assert [row["repo"] for row in featured["recommended"]] == ["org/fit"]
    assert featured["recommended"][0]["installed"] is True
    assert featured["recommended"][0]["vision"] is True

    queried = bridge.catalog("tiny")
    assert queried["recommended"][0]["repo"] == "org/tiny-big"
    assert queried["recommended"][0]["quant"] is None
    assert queried["recommended"][0]["size"] is None
    assert queried["recommended"][0]["installed"] is False
    assert bridge.catalog("no-such-model")["recommended"] == []


def test_download_errors_and_log_write_failure(monkeypatch):
    class _Logs:
        def mkdir(self, *_a, **_k):
            raise OSError("read-only")

    monkeypatch.setattr("agent.diagnostics.logging_setup.LOGS_DIR", _Logs())
    bridge._note_download("   ")
    bridge._note_download("fetched 1")
    assert bridge._state["detail"] == "fetched 1"

    def _popen_fail(*_a, **_k):
        raise OSError("no binary")

    monkeypatch.setattr(bridge.subprocess, "Popen", _popen_fail)
    bridge._install_job = {"spec": "org/m"}
    bridge._download("/bin/llama", "org/m")
    assert bridge._state["phase"] == "error"
    assert "Could not run llama download" in bridge._state["detail"]
    assert bridge._install_job is None

    class _Stdout:
        def __init__(self):
            self._sent = False

        def read(self, _count):
            if self._sent:
                return ""
            self._sent = True
            return "disk full\n"

    class _Proc:
        def __init__(self, *_a, **_k):
            self.stdout = _Stdout()

        def wait(self):
            return 3

    monkeypatch.setattr(bridge.subprocess, "Popen", lambda *_a, **_k: _Proc())
    bridge._install_job = {"spec": "org/m"}
    bridge._download("/bin/llama", "org/m")
    assert bridge._state["detail"] == "disk full"
    assert bridge._install_job is None

    class _Silent:
        stdout = None

        def wait(self):
            return 4

    monkeypatch.setattr(bridge.subprocess, "Popen", lambda *_a, **_k: _Silent())
    bridge._download_log.clear()
    monkeypatch.setattr(bridge, "_note_download", lambda line: None)
    bridge._download("/bin/llama", "org/m")
    assert "exited 4" in bridge._state["detail"]


def test_context_probe_and_set_context_edges(monkeypatch, tmp_path):
    assert bridge._parse_fitp("too short\n1 2 3 4\nGPU a b c\nGPU 1 2\n") is None

    monkeypatch.setattr(
        bridge,
        "_models_payload",
        lambda: [
            {"id": "other", "status": {"args": ["--model", "/nope.gguf"]}},
            {"id": "org/m", "status": {"args": ["--model", "/weights.gguf"]}},
            {"id": "bad", "status": None},
        ],
    )
    assert bridge._model_path("org/m") == "/weights.gguf"
    assert bridge._model_path("bad") is None
    assert bridge._model_path("missing") is None

    mode = {"name": "ok"}

    def _run(*_a, **_k):
        if mode["name"] == "os":
            raise OSError("no")
        if mode["name"] == "timeout":
            raise subprocess.TimeoutExpired(cmd="llama", timeout=1)
        if mode["name"] == "bad":
            return subprocess.CompletedProcess([], 1, "", "no")
        return subprocess.CompletedProcess([], 0, "MTL0 1 2 3\n", "")

    monkeypatch.setattr(bridge.subprocess, "run", _run)
    assert bridge._probe_mib("/bin/llama", "/weights.gguf", 4096) == 6
    mode["name"] = "bad"
    assert bridge._probe_mib("/bin/llama", "/weights.gguf", 4096) is None
    mode["name"] = "timeout"
    assert bridge._probe_mib("/bin/llama", "/weights.gguf", 4096) is None
    mode["name"] = "os"
    assert bridge._probe_mib("/bin/llama", "/weights.gguf", 4096) is None

    user = tmp_path / ".config" / "llama" / "models.user.ini"
    user.parent.mkdir(parents=True)
    user.write_text("[org/name:Q4]\nnote = hi\n")
    preset = tmp_path / "Library" / "Application Support" / "Llama" / "models.ini"
    preset.parent.mkdir(parents=True)
    preset.write_text("top = 1\n")
    monkeypatch.setattr(bridge.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(bridge.httpx, "get", lambda *_a, **_k: _JsonResponse({}))
    with pytest.raises(ValueError, match="Context must"):
        bridge.set_context("org/name:Q4", 100)
    saved = bridge.set_context("org/name:Q4", 8192)
    assert saved == {"ok": True, "model": "org/name:Q4", "context": 8192}
    assert "ctx-size = 8192" in user.read_text()
    assert "\n\n[org/name:Q4]" in preset.read_text()
    assert "ctx-size = 8192" in preset.read_text()


def test_update_load_unload_and_install_model(monkeypatch):
    monkeypatch.setattr(bridge, "llama_binary", lambda: "/bin/llama")
    monkeypatch.setattr(bridge, "list_models", lambda: None)

    class _Inline:
        def __init__(self, target=None, args=(), kwargs=None, **_extra):
            self.target = target

        def start(self):
            if self.target is not None:
                self.target()

    monkeypatch.setattr(bridge.threading, "Thread", _Inline)

    def _timeout(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="llama", timeout=1)

    monkeypatch.setattr(bridge.subprocess, "run", _timeout)
    bridge._set("idle")
    timed = bridge.update_engine()
    assert "Could not update" in timed["detail"]

    monkeypatch.setattr(
        bridge.subprocess,
        "run",
        lambda *_a, **_k: subprocess.CompletedProcess([], 2, "", "updater failed\n"),
    )
    failed = bridge.update_engine()
    assert failed["detail"] == "updater failed"

    monkeypatch.setattr(
        bridge.subprocess,
        "run",
        lambda *_a, **_k: subprocess.CompletedProcess([], 2, "", ""),
    )
    empty = bridge.update_engine()
    assert "exited 2" in empty["detail"]

    original_lock = bridge._lock
    # update_engine() calls status() while it still holds this lock.
    monkeypatch.setattr(bridge, "_lock", threading.RLock())
    bridge._set("updating", "Updating llama…")
    again = bridge.update_engine()
    bridge._lock = original_lock
    assert again["phase"] == "updating"

    monkeypatch.setattr(bridge.threading, "Thread", _HoldThread)
    with pytest.raises(ValueError, match="Model id"):
        bridge.load_model("  ")
    loaded = bridge.load_model("org/name:Q4")
    assert loaded == {"ok": True, "state": "loading"}

    posted = []

    class _Resp:
        def raise_for_status(self):
            return None

    def _post(url, json, timeout):
        posted.append((url, json, timeout))
        return _Resp()

    monkeypatch.setattr(bridge.httpx, "post", _post)
    bridge._load_jobs["org/name:Q4"] = "loading"
    with pytest.raises(ValueError, match="Model id"):
        bridge.unload_model(" ")
    unloaded = bridge.unload_model("org/name:Q4")
    assert unloaded["state"] == "unloaded"
    assert "org/name:Q4" not in bridge._load_jobs
    assert posted[0][0].endswith("/models/unload")

    with pytest.raises(ValueError, match="org/name"):
        bridge.install_model("not-a-repo")
    monkeypatch.setattr(bridge, "llama_binary", lambda: None)
    with pytest.raises(ValueError, match="not installed"):
        bridge.install_model("org/name")
    monkeypatch.setattr(bridge, "llama_binary", lambda: "/bin/llama")
    plain = bridge.install_model("org/name", "  ")
    assert plain["spec"] == "org/name"
    pinned = bridge.install_model("org/name", "Q4")
    assert pinned["spec"] == "org/name:Q4"
    assert bridge._install_job["quant"] == "Q4"


def test_remove_model_edges_and_weight_links(monkeypatch, tmp_path):
    monkeypatch.setattr(bridge.Path, "home", lambda: tmp_path)

    def _unload(_model_id):
        raise RuntimeError("not loaded")

    monkeypatch.setattr(bridge, "unload_model", _unload)
    with pytest.raises(ValueError, match="repo"):
        bridge.remove_model("noseparator")

    missing = tmp_path / "absent.ini"
    bridge._remove_ini_section(missing, "org/x")
    plain = tmp_path / "plain.ini"
    plain.write_text("[other]\nfoo = 1\n")
    bridge._remove_ini_section(plain, "org/missing")
    assert "[other]" in plain.read_text()
    only = tmp_path / "only.ini"
    only.write_text("[org/m]\nctx-size = 1\n")
    bridge._remove_ini_section(only, "org/m")
    assert only.read_text() == ""

    ini = tmp_path / ".config" / "llama" / "models.user.ini"
    ini.parent.mkdir(parents=True)
    ini.write_text("[org/missing:Q4]\nctx-size = 1\n[keep]\na = 1\n")
    bridge._mem_cache["org/missing:Q4"] = [{"context": 1}]
    with pytest.raises(ValueError, match="Could not find"):
        bridge.remove_model("org/missing:Q4")
    assert "org/missing:Q4" not in bridge._mem_cache
    assert "[org/missing:Q4]" not in ini.read_text()
    assert "[keep]" in ini.read_text()

    assert bridge._hf_hub_dir("nope") is None
    assert bridge._hf_hub_dir("org/../name") is None
    assert bridge._delete_downloaded_weights("nope", "Q4") is False

    outside = tmp_path / "outside"
    outside.mkdir()
    hub = tmp_path / ".cache" / "huggingface" / "hub"
    hub.mkdir(parents=True)
    (hub / "models--org--escape").symlink_to(outside, target_is_directory=True)
    assert bridge._hf_hub_dir("org/escape") is None

    repo = hub / "models--org--real"
    snap = repo / "snapshots" / "rev"
    snap.mkdir(parents=True)
    real = snap / "weights.gguf"
    real.write_bytes(b"abc")
    link = snap / "model-Q4.gguf"
    link.symlink_to(real)
    assert bridge._delete_downloaded_weights("org/real", "Q4") is True
    assert not real.exists()
    assert not repo.exists()

    snap.mkdir(parents=True)
    (snap / "model-Q8.gguf").write_bytes(b"zzz")
    ini.write_text("[org/real:Q8]\nctx-size = 4096\n")
    removed = bridge.remove_model("org/real:Q8")
    assert removed == {"ok": True}
    assert not repo.exists()


def test_wait_ensure_memory_and_empty_installer_log(monkeypatch):
    real_status = bridge.status
    real_ensure = bridge.ensure
    real_install = bridge._install_cli_then_serve
    monkeypatch.setattr(bridge, "status", lambda: {"running": True, "phase": "ready"})
    assert bridge.wait_until_serving() is True
    assert bridge.ensure()["phase"] == "ready"

    clock = {"t": 0.0}

    def _mono():
        clock["t"] += 0.2
        return clock["t"]

    monkeypatch.setattr(bridge, "status", lambda: {"running": False})
    monkeypatch.setattr(bridge, "llama_binary", lambda: "/bin/llama")
    monkeypatch.setattr(bridge, "ensure", lambda: {"phase": "opening"})
    monkeypatch.setattr(bridge.time, "monotonic", _mono)
    monkeypatch.setattr(bridge.time, "sleep", lambda _seconds: None)
    assert bridge.wait_until_serving(timeout=0.5) is False
    monkeypatch.setattr(bridge, "ensure", real_ensure)
    monkeypatch.setattr(bridge, "status", real_status)
    real_install = bridge._install_cli_then_serve
    monkeypatch.setattr(bridge, "_install_cli_then_serve", lambda: None)

    class _NoStart:
        def __init__(self, *_a, **_k):
            return None

        def start(self):
            return None

    monkeypatch.setattr(bridge.threading, "Thread", _NoStart)
    monkeypatch.setattr(bridge, "list_models", lambda: None)
    monkeypatch.setattr(bridge, "app_installed", lambda: False)
    monkeypatch.setattr(bridge, "llama_binary", lambda: None)
    bridge._set("idle")
    opened = bridge.ensure()
    assert opened["phase"] == "idle"
    assert opened["running"] is False
    monkeypatch.setattr(bridge, "_install_cli_then_serve", real_install)

    monkeypatch.setattr(bridge.os, "sysconf", lambda _key: "nope")
    assert bridge._memory_bytes() == 16 * 1000**3

    calls = {"n": 0}

    def _run(cmd, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 5, "", " \n")

    monkeypatch.setattr(bridge.shutil, "which", lambda name: "/usr/bin/curl" if name == "curl" else None)
    monkeypatch.setattr(bridge.subprocess, "run", _run)
    monkeypatch.setattr(bridge, "llama_binary", lambda: "/bin/llama")
    monkeypatch.setattr(bridge, "list_models", lambda: None)
    monkeypatch.setattr(bridge, "_install_cli_then_serve", real_install)
    bridge._install_cli_then_serve()
    assert bridge._state["detail"] == "llama installer exited 5"


class _Msg:
    def __init__(self, role, content=""):
        self.role = role
        self.content = content


class _Session:
    def __init__(self, status, session_id="s1", last_message_at=None):
        self.status = status
        self.id = session_id
        self.last_message_at = last_message_at
        self.updated_at = None


class _Store:
    def __init__(self):
        self.projects = {}
        self.sessions = {}
        self.copied = []
        self.deleted = []

    def create_project(self, **kwargs):
        project = SimpleNamespace(id=f"proj-{len(self.projects) + 1}", **kwargs)
        self.projects[project.id] = project
        return project

    def get_project(self, pid):
        return self.projects.get(pid)

    def insert_project_copy(self, project):
        self.copied.append(project.id)
        self.projects[project.id] = project

    def delete_project(self, pid):
        self.deleted.append(pid)

    def get_session(self, sid):
        return self.sessions.get(sid)

    def list_messages(self, _sid):
        return []

    def list_events(self, _sid):
        return []


class _Svc:
    def __init__(self, store, workspace):
        self.store = store
        self.workspace = workspace
        self.messages = []
        self.interrupts = []
        self.fail = None

    def create_session(self, **kwargs):
        if self.fail == "create":
            raise self.error
        session = SimpleNamespace(
            id=f"s{len(self.store.sessions) + 1}",
            workspace_path=self.workspace,
            project_id=kwargs.get("project_id"),
            status="idle",
        )
        self.store.sessions[session.id] = session
        return session

    error = RuntimeError("boom")

    def ensure_workspace(self, sid):
        return self.store.sessions[sid]

    def submit_message(self, **kwargs):
        if self.fail == "submit":
            raise self.error
        self.messages.append(kwargs)

    def interrupt(self, sid):
        self.interrupts.append(sid)
        if self.fail == "interrupt":
            raise RuntimeError("busy")


def _cell(qid="q1"):
    return SimpleNamespace(
        question_id=qid,
        title="T",
        model_id="gemma",
        provider="openai",
        prompt="Answer?",
        question=SimpleNamespace(
            ideal="A",
            question="Q",
            focus="math",
            id=qid,
            eval_mode="mcq",
            source={},
            metadata={},
        ),
    )


def _pack(pack_id="mmlu"):
    return SimpleNamespace(id=pack_id, questions=[], matrices={"default": {}})


def _deps(tmp_path, store=None):
    bench = store or _Store()
    svc = _Svc(bench, str(tmp_path))
    deps = SimpleNamespace(
        store=bench,
        worker_store=lambda: bench,
        worker_service=lambda: svc,
    )
    return deps, svc, bench


def _install_spawn(monkeypatch):
    pkg = ModuleType("sandwalk_bench")
    pkg.__path__ = []
    spawn_mod = ModuleType("sandwalk_bench.spawn")
    spawn_mod.copy_cell_inputs = lambda *_a, **_k: None
    spawn_mod.bench_kickoff_message = lambda **_k: "go"
    spawn_mod.default_project_name = lambda *_a, **_k: "Bench"
    spawn_mod.build_project_description = lambda **_k: "desc"
    monkeypatch.setitem(sys.modules, "sandwalk_bench", pkg)
    monkeypatch.setitem(sys.modules, "sandwalk_bench.spawn", spawn_mod)
    return spawn_mod


def _patch_suite(monkeypatch, cells, wait="settled"):
    _install_spawn(monkeypatch)
    monkeypatch.setattr(spawn, "ensure_sandwalk_bench_importable", lambda: True)
    monkeypatch.setattr(spawn, "_resolve_mcq_cells", lambda **_k: (cells, _pack(), "mmlu"))
    monkeypatch.setattr(
        spawn.SettingsService,
        "get",
        staticmethod(lambda: SimpleNamespace(provider="openai", model="gemma", openai_profile_id=None)),
    )
    monkeypatch.setattr(spawn, "resolve_bench_provider", lambda provider, profile_id=None: provider)
    monkeypatch.setattr(spawn, "capture_bench_environment", lambda *_a, **_k: {"runtime": {}})
    monkeypatch.setattr(spawn, "save_checkpoint", lambda _payload: None)
    monkeypatch.setattr(spawn, "save_result", lambda _result: None)
    monkeypatch.setattr(spawn, "get_result", lambda _run_id: None)
    monkeypatch.setattr(spawn, "delete_checkpoint", lambda _run_id: None)
    monkeypatch.setattr(spawn, "rollup_suite_usage", lambda **_k: None)
    monkeypatch.setattr(spawn, "delete_bench_project_data", lambda *_a, **_k: None)
    monkeypatch.setattr(spawn, "_wait_until_settled", lambda *_a, **_k: wait)
    monkeypatch.setattr(
        spawn,
        "_grade_session",
        lambda *_a, **_k: {"correct": True, "predicted": "A"},
    )
    monkeypatch.setattr(
        "agent_server.bench_service.catalog.pack_display_title",
        lambda _pack_id: "MMLU",
    )
    monkeypatch.setattr(
        "agent_server.bench_service.retry_extra.take_extra_retry",
        lambda _run_id: [],
    )


def _run(deps, **overrides):
    payload = {
        "deps": deps,
        "suite_id": "mmlu",
        "pack_id": "mmlu",
        "matrix": None,
        "model_id": "gemma",
        "provider": "openai",
        "sample_size": 1,
        "project_name": None,
    }
    payload.update(overrides)
    return spawn.run_agent_suite(**payload)


def test_suite_entry_coding_and_skipped_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(spawn, "ensure_sandwalk_bench_importable", lambda: False)
    with pytest.raises(RuntimeError, match="sandwalk-bench"):
        _run(_deps(tmp_path)[0])

    deps, _svc, _store = _deps(tmp_path)
    _patch_suite(monkeypatch, [_cell()])
    cancelled = _run(deps, cancel_check=lambda: True, provider=None)
    assert cancelled["status"] == "cancelled"

    monkeypatch.setattr(
        "agent_server.bench_service.coding_suites.CODING_SUITES",
        {"mbpp": object()},
    )
    monkeypatch.setattr(
        spawn,
        "_resolve_coding_cells",
        lambda **_k: ([_cell("code")], _pack("mbpp"), "mbpp"),
    )
    coded = _run(deps, suite_id="mbpp", pack_id="mbpp")
    assert coded["status"] == "completed"

    monkeypatch.setattr(
        spawn,
        "_resolve_cells",
        lambda **_k: ([], _pack("custom"), "custom", [{"cell": _cell()}]),
    )
    with pytest.raises(RuntimeError, match="skipped"):
        _run(deps, suite_id="custom", pack_id="custom")

    monkeypatch.setattr(
        spawn,
        "_resolve_cells",
        lambda **_k: (
            [_cell("q1")],
            _pack("custom"),
            "Custom",
            [
                {
                    "cell": _cell("skip"),
                    "reason": "missing skill",
                    "missing_skills": ["fold"],
                    "missing_mcps": [],
                }
            ],
        ),
    )
    mixed = _run(deps, suite_id="custom", pack_id="custom")
    assert mixed["status"] == "completed"
    assert any(row.get("skipped") for row in mixed["questions"])


def test_resume_skips_exhausted_and_recovers_project(monkeypatch, tmp_path):
    bench = _Store()
    chat = _Store()
    svc = _Svc(bench, str(tmp_path))
    deps = SimpleNamespace(
        store=chat,
        worker_store=lambda: bench,
        worker_service=lambda: svc,
    )
    _patch_suite(monkeypatch, [_cell("q1"), _cell("q2")])

    class _Row:
        def get(self, _key, default=None):
            return default

    def _explode(_pid):
        raise RuntimeError("db")

    bench.get_project = _explode
    chat.get_project = _explode

    def _chat_session(sid):
        if sid == "bad":
            raise RuntimeError("missing")
        if sid == "good":
            return SimpleNamespace(project_id="proj-recovered", id=sid)
        return None

    def _bench_session(_sid):
        raise RuntimeError("bench closed")

    bench.get_session = _bench_session
    chat.get_session = _chat_session
    monkeypatch.setattr(
        spawn,
        "get_result",
        lambda _run_id: {
            "name": "Prior",
            "time_s": 3,
            "questions": [
                _Row(),
                {"session_id": "bad"},
                {"sessionId": "good", "question_id": "kept"},
            ],
        },
    )
    monkeypatch.setattr(
        "agent_server.bench_service.results_store._exhausted_questions_from_stores",
        lambda _project_id, _stores: {"q2"},
    )
    monkeypatch.setattr(
        "agent_server.bench_service.results_store._terminal_question_ids",
        lambda _prior: {"q1"},
    )
    result = _run(
        deps,
        run_id="resume-1",
        resume_checkpoint={
            "run_id": "resume-1",
            "completed_question_ids": [],
            "remaining_question_ids": ["q1", "q2"],
            "project_id": "missing-proj",
            "environment": {"runtime": {}},
            "name": "Prior",
            "elapsed_s": 2,
        },
    )
    assert result["status"] == "completed"
    assert result["project_id"] == "proj-recovered"
    assert result["name"] == "Prior"
    errors = [(row.get("judge") or {}).get("error", "") for row in result["questions"]]
    assert any("Not retried" in text for text in errors)
    assert svc.messages == []


def test_mirror_project_cleanup_and_extra_retry(monkeypatch, tmp_path):
    bench = _Store()
    chat = _Store()

    def _delete(pid):
        chat.deleted.append(pid)
        raise RuntimeError("mirror")

    chat.delete_project = _delete
    svc = _Svc(bench, str(tmp_path))
    deps = SimpleNamespace(
        store=chat,
        worker_store=lambda: bench,
        worker_service=lambda: svc,
    )
    _patch_suite(monkeypatch, [_cell()])
    cleaned = _run(deps, cleanup_sessions=True, project_name="Kept")
    assert cleaned["sessions_cleaned"] is True
    assert chat.copied
    assert chat.deleted

    calls = {"n": 0}

    def _extras(_run_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return ["q2", "missing", "q1"]
        return []

    monkeypatch.setattr("agent_server.bench_service.retry_extra.take_extra_retry", _extras)
    monkeypatch.setattr(
        spawn,
        "get_result",
        lambda _run_id: {
            "questions": [
                {"question_id": "q2", "correct": False},
                {"question_id": "q1", "correct": True},
            ],
            "name": "Again",
            "time_s": 1,
        },
    )
    _patch_suite(monkeypatch, [_cell("q1"), _cell("q2")])
    monkeypatch.setattr("agent_server.bench_service.retry_extra.take_extra_retry", _extras)
    monkeypatch.setattr(
        spawn,
        "get_result",
        lambda _run_id: {
            "questions": [
                {"question_id": "q2", "correct": False},
                {"question_id": "q1", "correct": True},
            ],
            "name": "Again",
        },
    )
    deps, svc, _store = _deps(tmp_path)
    retried = _run(
        deps,
        run_id="extra-1",
        resume_checkpoint={
            "run_id": "extra-1",
            "completed_question_ids": ["q2"],
            "remaining_question_ids": ["q1"],
            "force_retry": True,
            "environment": {"runtime": {}},
            "elapsed_s": 1,
            "name": "Again",
        },
    )
    assert retried["status"] == "completed"
    assert {row["question_id"] for row in retried["questions"]} == {"q1", "q2"}
    assert len(svc.messages) == 2


def test_run_cell_stop_submit_and_worker_errors(monkeypatch, tmp_path):
    deps, svc, _store = _deps(tmp_path)
    calls = {"n": 0}

    def _stop_after_claim():
        calls["n"] += 1
        if calls["n"] >= 2:
            return "pause"
        return None

    _patch_suite(monkeypatch, [_cell()])
    paused = _run(deps, stop_check=_stop_after_claim)
    assert paused["status"] == "paused"

    calls["n"] = 0

    def _stop_after_copy():
        calls["n"] += 1
        if calls["n"] >= 3:
            return "pause"
        return None

    paused_later = _run(deps, stop_check=_stop_after_copy)
    assert paused_later["status"] == "paused"

    svc.fail = "submit"
    svc.error = RuntimeError("event loop is closed")
    looped = _run(deps)
    assert looped["status"] == "paused"

    svc.fail = "submit"
    svc.error = RuntimeError("disk full")
    failed = _run(deps)
    assert failed["status"] == "completed"
    assert failed["questions"][0]["eval_mode"] == "error"

    svc.fail = "create"
    svc.error = ValueError("weird")
    valued = _run(deps)
    assert valued["questions"][0]["judge"]["error"] == "weird"

    svc.fail = "interrupt"
    _patch_suite(monkeypatch, [_cell()], wait="stopped")
    stopped = _run(deps)
    assert stopped["status"] == "paused"
    assert svc.interrupts

    _patch_suite(monkeypatch, [_cell()], wait="stalled")
    svc.fail = "interrupt"
    stalled = _run(deps)
    assert stalled["status"] == "completed"
    assert "stalled" in stalled["questions"][0]["judge"]["error"].lower()


def test_peer_pause_interrupts_in_flight_session(monkeypatch, tmp_path):
    deps, svc, _store = _deps(tmp_path)
    _patch_suite(monkeypatch, [_cell("q1"), _cell("q2")])
    roles: dict[int, str] = {}
    counts: dict[int, int] = {}
    lock = threading.Lock()
    blocker_in_submit = threading.Event()
    peer_finished = threading.Event()

    def _stop():
        tid = threading.get_ident()
        with lock:
            role = roles.setdefault(tid, "A" if not roles else "B")
            counts[tid] = counts.get(tid, 0) + 1
            nth = counts[tid]
        if role == "B" and nth == 1:
            assert blocker_in_submit.wait(5)
            return None
        if role == "B":
            return "pause"
        return None

    def _submit(**kwargs):
        blocker_in_submit.set()
        assert peer_finished.wait(5)
        svc.messages.append(kwargs)

    def _interrupt(sid):
        svc.interrupts.append(sid)
        peer_finished.set()
        raise RuntimeError("busy")

    svc.submit_message = _submit
    svc.interrupt = _interrupt
    result = _run(deps, concurrency=2, stop_check=_stop)
    assert result["status"] == "paused"
    assert svc.interrupts


def test_copy_inputs_and_capsule_edges(monkeypatch, tmp_path):
    spawn_mod = _install_spawn(monkeypatch)
    copied = []

    def _copy(pack, cell, workspace):
        copied.append((pack.id, cell.question_id, workspace))

    spawn_mod.copy_cell_inputs = _copy
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spawn._copy_inputs(_pack("mmlu"), _cell(), workspace)
    spawn._copy_inputs(_pack("mbpp"), _cell("code"), workspace)
    assert copied == []

    real_capsule = spawn._copy_bix_capsule
    monkeypatch.setattr(spawn, "_copy_bix_capsule", lambda *_a, **_k: True)
    bix = SimpleNamespace(
        question_id="b1",
        question=SimpleNamespace(source={"data_folder": "cap"}),
    )
    spawn._copy_inputs(_pack("bixbench"), bix, workspace)
    assert copied == []

    monkeypatch.setattr(spawn, "_copy_bix_capsule", lambda *_a, **_k: False)
    spawn._copy_inputs(_pack("bixbench"), bix, workspace)
    plain = SimpleNamespace(question_id="p1", question=SimpleNamespace(source={}))
    spawn._copy_inputs(_pack("yaml"), plain, workspace)
    assert [item[0] for item in copied] == ["bixbench", "yaml"]
    monkeypatch.setattr(spawn, "_copy_bix_capsule", real_capsule)

    capsules = ModuleType("sandwalk_bench.capsules")
    data = tmp_path / "capsule"
    data.mkdir()
    (data / "f.txt").write_text("rows", encoding="utf-8")
    tokens = []

    def _ensure(folder, token=None):
        tokens.append((folder, token))
        if len(tokens) == 1:
            raise RuntimeError("network")
        return data

    capsules.ensure_capsule = _ensure
    monkeypatch.setitem(sys.modules, "sandwalk_bench.capsules", capsules)
    monkeypatch.setattr(
        "agent_server.bench_service.dataset_install.resolve_hf_token",
        lambda: "",
    )
    (workspace / "data").mkdir()
    (workspace / "data" / "old.txt").write_text("old", encoding="utf-8")
    assert spawn._copy_bix_capsule({"data_folder": "cap"}, workspace) is False
    monkeypatch.setattr(
        "agent_server.bench_service.dataset_install.resolve_hf_token",
        lambda: "hf-token",
    )
    assert spawn._copy_bix_capsule({"data_folder": "cap"}, workspace) is True
    assert (workspace / "data" / "f.txt").read_text(encoding="utf-8") == "rows"
    assert tokens[0][1] is None
    assert tokens[1][1] == "hf-token"


def test_grade_session_edges(monkeypatch):
    captured = {}

    def _judge(**kwargs):
        captured.update(kwargs)
        return {"overall_pass": True}

    def _grade(**kwargs):
        captured["judge_ok"] = kwargs["judge_ok"]
        captured["predicted"] = kwargs["predicted"]
        return kwargs["judge_ok"] is True

    monkeypatch.setattr(spawn, "run_llm_judge", _judge)
    monkeypatch.setattr(spawn, "grade_row", _grade)
    monkeypatch.setattr(spawn, "extract_answer", lambda text: f"parsed:{text}" if text else "")
    monkeypatch.setattr(spawn, "collect_tool_names_from_events", lambda events: ["run_python"] if events else [])
    monkeypatch.setattr(spawn, "heuristic_checklist", lambda _tools, _checks: {"tool": True})

    class _Bare:
        def list_messages(self, _sid):
            return [_Msg("assistant", "   "), _Msg("user", "hi"), _Msg("assistant", "Answer: 7")]

    cell = SimpleNamespace(question=None, question_id="qx", prompt="p" * 2500)
    bare = SimpleNamespace(
        store=_Bare(),
        worker_store=lambda: _Bare(),
        worker_service=lambda: SimpleNamespace(),
    )
    row = spawn._grade_session(bare, session_id="s1", cell=cell, index=0)
    assert row["eval_mode"] == "checklist"
    assert row["category"] == "qx"
    assert row["question"] == "p" * 2000
    assert captured["judge_ok"] is True
    assert "Tools:" not in captured["evidence"]

    question = SimpleNamespace(
        eval_mode="llm_verifier",
        ideal="A",
        source={"categories": "bio"},
        metadata={"checklist": ["tool"]},
        focus="",
        question="What?",
        id="q-bio",
    )
    cell.question = question

    class _Events:
        def list_messages(self, _sid):
            return [_Msg("assistant", "long answer")]

        def list_events(self, _sid):
            return [SimpleNamespace(type="tool")]

    graded = spawn._grade_session(
        SimpleNamespace(worker_store=lambda: _Events()),
        session_id="s1",
        cell=cell,
        index=2,
    )
    assert graded["category"] == "bio"
    assert captured["evidence"].startswith("Tools: run_python")
    assert captured["judge_ok"] is True
    assert graded["correct"] is True

    question.eval_mode = "mcq"
    question.focus = ""
    question.source = {}
    question.metadata = None
    mcq = spawn._grade_session(
        SimpleNamespace(worker_store=lambda: _Events()),
        session_id="s1",
        cell=cell,
        index=3,
    )
    assert mcq["eval_mode"] == "mcq"
    assert mcq["category"] == "q-bio"
    assert mcq["judge"] is None
    assert mcq["predicted"] == "parsed:long answer"


def test_wait_activity_offline_and_stall_interrupt(monkeypatch):
    clock = {"n": 0}

    def _now():
        clock["n"] += 1
        return (0, 1, 100)[min(clock["n"] - 1, 2)]

    store = _Store()
    store.session = _Session("running", last_message_at=1_000_000_000)
    store.get_session = lambda _sid: store.session
    deps = SimpleNamespace(
        worker_store=lambda: store,
        worker_service=lambda: SimpleNamespace(interrupt=lambda _sid: None),
    )
    monkeypatch.setattr("agent_server.offline_mode.is_offline", lambda: False)
    assert (
        spawn._wait_until_settled(
            deps,
            session_id="s1",
            timeout_s=30,
            stall_s=30,
            now=_now,
            sleeper=lambda _seconds: None,
        )
        == "timeout"
    )

    def _offline():
        raise RuntimeError("offline probe")

    monkeypatch.setattr("agent_server.offline_mode.is_offline", _offline)
    ticks = {"n": -1.0}

    def _tick():
        ticks["n"] += 1
        return ticks["n"]

    waiting = SimpleNamespace(
        worker_store=lambda: _Store(),
        worker_service=lambda: SimpleNamespace(interrupt=lambda _sid: None),
    )
    waiting.worker_store = lambda: store
    store.session = _Session("queued")
    assert (
        spawn._wait_until_settled(
            waiting,
            session_id="s1",
            timeout_s=30,
            stall_s=30,
            now=_tick,
            sleeper=lambda _seconds: None,
        )
        == "timeout"
    )

    def _late(_sid):
        raise RuntimeError("late")

    ticks["n"] = -1.0
    store.session = _Session("running")
    monkeypatch.setattr("agent_server.offline_mode.is_offline", lambda: False)
    stalled = SimpleNamespace(
        worker_store=lambda: store,
        worker_service=lambda: SimpleNamespace(interrupt=_late),
    )
    assert (
        spawn._wait_until_settled(
            stalled,
            session_id="s1",
            timeout_s=30,
            stall_s=30,
            now=_tick,
            sleeper=lambda _seconds: None,
        )
        == "stalled"
    )


@dataclass
class _MatrixCell:
    question_id: str
    model_key: str = ""
    model_id: str = ""
    provider: str = ""
    title: str = ""
    prompt: str = ""
    question: object = None


def test_preferred_matrix_when_suite_has_no_colon(tmp_path, monkeypatch):
    pkg = ModuleType("sandwalk_bench")
    pkg.__path__ = []
    bix = ModuleType("sandwalk_bench.bixbench")
    pack_mod = ModuleType("sandwalk_bench.pack")
    paths = ModuleType("sandwalk_bench.paths")
    schema = ModuleType("sandwalk_bench.schema")
    spawn_mod = ModuleType("sandwalk_bench.spawn")
    packs = tmp_path / "packs"
    packs.mkdir()
    paths.PACKS_DIR = packs
    schema.MatrixCell = _MatrixCell
    spawn_mod.copy_cell_inputs = lambda *_a, **_k: None
    bix.jsonl_path = lambda: tmp_path / "missing.jsonl"
    bix.as_is_pack = lambda _rows: SimpleNamespace(questions=[], id="bix")
    bix.load_jsonl = lambda: []
    yaml_pack = SimpleNamespace(id="bio", questions=[], matrices={"default": {}, "extra": {}})
    pack_mod.load_pack = lambda _path: yaml_pack
    pack_mod.list_packs = lambda: [packs / "bio.yaml"]
    seen = {}

    def _expand(_pack, matrix):
        seen["matrix"] = matrix
        return [_MatrixCell(question_id="q")]

    pack_mod.expand_matrix = _expand
    for module in (pkg, bix, pack_mod, paths, schema, spawn_mod):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(
        "agent_server.bench_service.pack_requirements.partition_cells_by_requirements",
        lambda cells, store=None: (cells, []),
    )
    monkeypatch.setattr(
        "agent_server.bench_service.catalog.pack_matches_id",
        lambda _loaded, _pack_id: True,
    )
    monkeypatch.setattr(
        "agent_server.bench_service.catalog.pack_display_title",
        lambda _pack_id: "",
    )
    monkeypatch.setattr(
        "agent_server.bench_service.catalog._preferred_matrix",
        lambda _pack: ("extra", None),
    )
    (packs / "bio.yaml").write_text("pack: bio\n", encoding="utf-8")
    _cells, _pack, title, skipped = spawn._resolve_cells(
        pack_id="bio",
        matrix=None,
        suite_id="bio",
        sample_size=None,
        model_id="",
        provider=None,
    )
    assert seen["matrix"] == "extra"
    assert title == "bio"
    assert skipped == []

    monkeypatch.setattr(
        "agent_server.bench_service.catalog._preferred_matrix",
        lambda _pack: (None, None),
    )
    spawn._resolve_cells(
        pack_id="bio",
        matrix=None,
        suite_id="bio",
        sample_size=None,
        model_id="",
        provider=None,
    )
    assert seen["matrix"] == "default"
