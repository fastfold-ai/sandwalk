"""Drive Capy tool functions with a fake store so the branches run locally."""

from __future__ import annotations

from types import SimpleNamespace

from agent_server.bench_service.dataset_install import BenchInstallError
from agent_server.models.bench import BenchActiveStatus, BenchInstallResponse, BenchSuiteCard
from tools import capy as capy_tools


class _Store:
    def list_sessions(self):
        return [
            SimpleNamespace(
                id="s1", title="Lab", status="idle", project_id="p1",
                last_message_at=None, source="ui",
            ),
            SimpleNamespace(
                id="capy", title="Capy", status="idle", project_id=None,
                last_message_at=None, source="capy",
            ),
        ]

    def get_session(self, sid):
        if sid == "s1":
            return SimpleNamespace(id="s1", title="Lab", source="ui", project_id="p1")
        if sid == "capy":
            return SimpleNamespace(id="capy", title="Capy", source="capy", project_id=None)
        return None

    def get_project(self, pid):
        if pid == "p1":
            return SimpleNamespace(id="p1", name="Alpha", folder_path="/work")
        if pid == "gone":
            return None
        return None

    def list_projects(self):
        return [
            SimpleNamespace(id="p1", name="Alpha", session_count=1, pinned=True),
            SimpleNamespace(id="p2", name="Alpine", session_count=0, pinned=False),
        ]

    def list_mcp_servers(self):
        return [SimpleNamespace(id="mcp", name="Local", enabled=True)]

    def create_project(self, name, description=None):
        if name == "boom":
            raise RuntimeError("duplicate")
        return SimpleNamespace(id="pnew", name=name)

    def lifetime_tokens_by_run(self, ids):
        if ids == ["explode"]:
            raise RuntimeError("no tokens")
        return dict.fromkeys(ids, 5)


class _Service:
    _active_runs = {"run": 1}

    def submit_message(self, session_id, content):
        if "fail" in content:
            raise RuntimeError("busy")
        return SimpleNamespace(run_id="r1")

    def create_session(self, **kwargs):
        return SimpleNamespace(id=f"new-{kwargs['title']}", title=kwargs["title"])

    def update_session(self, **kwargs):
        if kwargs["session_id"] == "bad":
            raise RuntimeError("locked")


def _card():
    return BenchSuiteCard(id="gpqa", title="GPQA", available=True, sample_sizes=[10], question_count=10)


def _raiser(exc):
    def _inner(*args, **kwargs):
        raise exc

    return _inner


def test_capy_tools(monkeypatch):
    store = _Store()
    service = _Service()
    models = SimpleNamespace(
        list_models=_raiser(RuntimeError("models down"))
    )
    specialists = SimpleNamespace(list=_raiser(RuntimeError("no specs")))
    pty = SimpleNamespace(run_sync=lambda awaitable: {"terminal": {"id": "t1", "title": "Claude", "workspacePath": "/work"}, "command": "claude"})
    deps = SimpleNamespace(
        store=store,
        service=service,
        models_service=models,
        specialists_service=specialists,
        pty_manager=pty,
    )
    monkeypatch.setattr(capy_tools, "_deps", lambda: deps)
    monkeypatch.setattr(
        "agent_server.capy.scope.get_capy_scope",
        lambda: {"project_id": "p1", "session_id": "s1"},
    )
    published = []
    monkeypatch.setattr(
        "agent_server.session_event_bus.session_event_bus.publish",
        lambda topic, payload: published.append((topic, payload)),
    )

    assert capy_tools._parse_grid(grid="9x9") is None
    assert capy_tools._parse_grid(grid="2x2") == {"rows": 2, "cols": 2}
    assert capy_tools._parse_grid(rows=1, cols=0) is None
    capy_tools._emit_open_split(["only"])
    assert published == []
    assert capy_tools._resolve_project_id(store, "a")["ok"] is False
    assert capy_tools._resolve_project_id(store, "missing")["ok"] is False
    assert capy_tools._resolve_project_id(store, "p1")["projectName"] == "Alpha"
    assert capy_tools._as_bool(None, True) is True
    assert capy_tools._as_bool(True) is True
    assert capy_tools._as_bool("yes") is True
    assert capy_tools._as_int("no", 3) == 3
    assert capy_tools._csv([" a ", ""]) == ["a"]
    assert capy_tools._parse_suites("gpqa:10,:4", None)[0]["sample_size"] == 10

    listed = capy_tools.capy_list_sessions()
    assert listed["sessions"][0]["id"] == "s1"
    monkeypatch.setattr(
        "agent_server.capy.extract.extract_session",
        lambda store, sid: {"ok": False, "summary": "missing"} if sid == "nope" else {
            "ok": True, "title": "Lab", "excerpt": "hello", "sessionId": sid,
        },
    )
    assert capy_tools.capy_read_session("s1")["ok"] is True
    assert capy_tools.capy_summarize_session("nope")["ok"] is False
    assert "summary" in capy_tools.capy_summarize_session("s1")

    assert capy_tools.capy_send_message("", "hi")["ok"] is False
    assert capy_tools.capy_send_message("missing", "hi")["ok"] is False
    assert capy_tools.capy_send_message("capy", "hi")["ok"] is False
    assert capy_tools.capy_send_message("s1", "fail")["ok"] is False
    assert capy_tools.capy_send_message("s1", "hello")["ok"] is True

    spawned = capy_tools.capy_spawn_sessions(count=1, message="fail", grid="2x1", project_id="p1")
    assert spawned["ok"] is True
    assert capy_tools.capy_spawn_sessions(project_id="missing")["ok"] is False
    assert capy_tools.capy_open_split("s1")["ok"] is False
    opened = capy_tools.capy_open_split(["s1", "s2"], grid="2x1")
    assert opened["ok"] is True

    assert capy_tools.capy_seed_session("nope")["ok"] is False
    assert capy_tools.capy_seed_session("s1", target_id="missing")["ok"] is False
    assert capy_tools.capy_seed_session("s1", target_id="capy")["ok"] is False
    assert capy_tools.capy_seed_session("s1", target_id="s1", also_prompt="fail")["ok"] is False
    seeded = capy_tools.capy_seed_session("s1", brief="note")
    assert seeded["ok"] is True

    monkeypatch.setattr("agent.skills.list_skills", lambda: [SimpleNamespace(name="fold", enabled=True)])
    monkeypatch.setattr("agent.skills.install_skill", lambda spec: {"ok": True, "summary": "have it"} if spec == "dict" else spec)
    monkeypatch.setattr("agent.skills.set_skill_enabled", lambda name, enabled: {"ok": False} if name == "dict" else True)
    assert capy_tools.capy_skills_list()["skills"][0]["name"] == "fold"
    assert capy_tools.capy_skills_install("")["ok"] is False
    assert capy_tools.capy_skills_install("dict")["ok"] is True
    assert capy_tools.capy_skills_install("fold")["ok"] is True
    assert capy_tools.capy_skills_set_enabled("")["ok"] is False
    assert capy_tools.capy_skills_set_enabled("dict")["ok"] is False
    assert capy_tools.capy_skills_set_enabled("fold", False)["ok"] is True

    assert "MCP" in capy_tools.capy_mcp_list()["summary"]
    bare = SimpleNamespace()
    deps.store = bare
    assert capy_tools.capy_mcp_list()["servers"] == []
    deps.store = store

    assert capy_tools.capy_app_status()["activeRuns"] == 1
    deps.service = SimpleNamespace()
    assert capy_tools.capy_app_status()["activeRuns"] == -1
    deps.service = service
    monkeypatch.setattr(
        "agent_server.status_service.schedule_restart",
        lambda: SimpleNamespace(ok=False, message="later"),
    )
    assert capy_tools.capy_server_restart()["ok"] is False

    monkeypatch.setattr("agent_server.bench_service.list_suite_cards", lambda store: [_card()])
    monkeypatch.setattr(
        "agent_server.settings_service.SettingsService.get",
        staticmethod(lambda: SimpleNamespace(model="gpt", provider="openai")),
    )
    catalog = capy_tools.capy_bench_catalog()
    assert catalog["models"][0]["error"]
    deps.models_service = SimpleNamespace(
        list_models=lambda **kwargs: SimpleNamespace(
            data=[SimpleNamespace(id="m", label="M", provider="openai", supports_reasoning_effort=False)]
        )
    )
    deps.specialists_service = SimpleNamespace(
        list=lambda: [SimpleNamespace(id="sp", name="Spec", slug="spec")]
    )
    assert capy_tools.capy_bench_catalog()["specialists"]
    monkeypatch.setattr(
        "agent_server.bench_service.get_active_status",
        lambda: BenchActiveStatus(running=True, phase="running", current_model="gpt"),
    )
    assert "Bench running" in capy_tools.capy_bench_status()["summary"]
    assert capy_tools.capy_bench_launch("")["ok"] is False
    monkeypatch.setattr("agent_server.bench_service.enqueue", lambda deps, req: ["run-1"])
    assert capy_tools.capy_bench_launch("gpqa:10", models="other", thinking="yes")["ok"] is True
    monkeypatch.setattr(
        "agent_server.bench_service.enqueue",
        _raiser(RuntimeError("full")),
    )
    assert capy_tools.capy_bench_launch("gpqa")["ok"] is False
    assert capy_tools.capy_bench_install("")["ok"] is False
    monkeypatch.setattr(
        "agent_server.bench_service.install_jobs.start_install",
        _raiser(BenchInstallError("token", needs_hf_token=True)),
    )
    assert capy_tools.capy_bench_install("gpqa")["needsHfToken"] is True
    monkeypatch.setattr(
        "agent_server.bench_service.install_jobs.start_install",
        lambda key: BenchInstallResponse(ok=True, suite_id=key, summary="go", status="installing"),
    )
    assert capy_tools.capy_bench_install("gpqa")["ok"] is True

    monkeypatch.setattr(
        "agent_server.bench_service.list_results_page",
        lambda **kwargs: {"data": [{"run_id": "r", "benchmark": "gpqa", "lifetime_tokens": 3}, {"run_id": "explode"}], "total": 2},
    )
    assert capy_tools.capy_bench_results(sort="usage_desc")["total"] >= 1
    monkeypatch.setattr("agent_server.bench_service.resolve_result_run_id", lambda key: key)
    monkeypatch.setattr("agent_server.bench_service.get_result", lambda rid: None)
    monkeypatch.setattr("agent_server.bench_service.checkpoint.load_checkpoint", lambda rid: None)
    assert capy_tools.capy_bench_inspect("")["ok"] is False
    assert capy_tools.capy_bench_inspect("missing")["ok"] is False
    monkeypatch.setattr(
        "agent_server.bench_service.checkpoint.load_checkpoint",
        lambda rid: {"run_id": rid} if rid == "ckpt" else None,
    )
    monkeypatch.setattr(
        "agent_server.bench_service.result_from_checkpoint",
        lambda ckpt: {"run_id": "ckpt", "benchmark": "gpqa", "accuracy": 0.5, "correct": 1, "total": 2, "questions": [{"correct": False, "prompt": "q", "skipped": False}, "nope"]},
    )
    monkeypatch.setattr("agent_server.bench_service.apply_live_status", lambda row: row)
    inspected = capy_tools.capy_bench_inspect("ckpt")
    assert inspected["ok"] is True

    monkeypatch.setattr("agent.diagnostics.collectors._collect_log_files", lambda: [])
    assert capy_tools._log_issue_lines()["issues"] == []
    log = SimpleNamespace(name="server.log")
    monkeypatch.setattr("agent.diagnostics.collectors._collect_log_files", lambda: [log])
    monkeypatch.setattr(
        "agent.diagnostics.collectors._read_log_tail",
        lambda path: "ok\nERROR boom\n",
    )
    assert capy_tools._log_issue_lines()["issues"]
    monkeypatch.setattr("agent.diagnostics.logging_setup.ensure_logging_configured", lambda: None)
    monkeypatch.setattr("agent.doctor.to_report", lambda scope: {
        "ok": False,
        "summary": {"error": 1, "warn": 0, "ok": 1, "total": 2},
        "checks": [{"name": "api", "status": "error", "detail": "down", "fix": "restart", "category": "core"}],
    })
    monkeypatch.setattr("agent.diagnostics.collectors._system_info", lambda version: {"version": version})
    monkeypatch.setattr("agent.diagnostics.collectors._skills_summary", lambda: {"count": 0})
    assert capy_tools.capy_doctor("nope")["scope"] == "full"

    projects = capy_tools.capy_list_projects()
    assert projects["currentProjectId"] == "p1"
    assert capy_tools.capy_create_project("")["ok"] is False
    assert capy_tools.capy_create_project("boom")["ok"] is False
    created = capy_tools.capy_create_project("New", create_chat="yes", message="fail")
    assert created["ok"] is True
    assert capy_tools.capy_move_session("", "missing")["ok"] is False
    assert capy_tools.capy_move_session("", "p1")["ok"] is False
    moved = capy_tools.capy_move_session("missing,capy,bad,s1", "all")
    assert moved["errors"]

    import agent_server.external_agents_service as ext

    monkeypatch.setattr(ext, "list_external", lambda kind, folder, limit: [{"id": "e1"}])
    monkeypatch.setattr(ext, "list_installed", lambda: [{"label": "Claude", "installed": True}, {"label": "Codex", "installed": False}])
    listed_ext = capy_tools.capy_list_external_sessions(project_id="p1")
    assert listed_ext["ok"] is True
    monkeypatch.setattr(ext, "list_external", _raiser(ext.ExternalAgentError("no cli")))
    assert capy_tools.capy_list_external_sessions(project_id="missing")["ok"] is False
    assert capy_tools.capy_list_external_sessions()["ok"] is False

    monkeypatch.setattr(
        ext,
        "import_session",
        lambda **kwargs: SimpleNamespace(id="imp", title="Imported", source_label="Claude", workspace_path="/work"),
    )
    assert capy_tools.capy_import_external_session("claude", "e1", "p1")["ok"] is True
    monkeypatch.setattr(ext, "import_session", _raiser(ext.ExternalAgentError("bad")))
    assert capy_tools.capy_import_external_session("claude", "e1")["ok"] is False

    def _launch(**kwargs):
        return {"terminal": {"id": "t1", "title": "Claude", "workspacePath": "/work"}, "command": "claude"}

    monkeypatch.setattr(ext, "launch_terminal", _launch)
    opened_term = capy_tools.capy_launch_external_agent("claude", project_id="p1", prompt="hi")
    assert opened_term["ok"] is True
    monkeypatch.setattr(ext, "launch_terminal", _raiser(ext.ExternalAgentError("missing bin")))
    assert capy_tools.capy_launch_external_agent("claude")["ok"] is False
    deps.pty_manager = SimpleNamespace(run_sync=_raiser(RuntimeError("pty")))
    monkeypatch.setattr(ext, "launch_terminal", _launch)
    assert "terminal" in capy_tools.capy_launch_external_agent("claude")["summary"].lower()
    deps.pty_manager = pty

    assert capy_tools.capy_handoff_session("", "claude")["ok"] is False
    assert capy_tools.capy_handoff_session("capy", "claude")["ok"] is False
    monkeypatch.setattr(
        ext,
        "export_handoff",
        lambda **kwargs: {"workspacePath": "/work", "prompt": "go", "messages": 2, "path": "/work/handoff.md"},
    )
    handed = capy_tools.capy_handoff_session("s1", "claude")
    assert handed["ok"] is True
    monkeypatch.setattr(ext, "export_handoff", _raiser(ext.ExternalAgentError("no")))
    assert capy_tools.capy_handoff_session("s1", "claude")["ok"] is False
