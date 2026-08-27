"""Capy meta-agent isolation, extract/seed, and spawn split command."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from agent_server.app import create_app
from agent_server.capy import CAPY_EXCLUDED_DEEPAGENTS_TOOLS, bind_capy_deps, is_capy_session
from agent_server.capy.extract import extract_session
from agent_server.capy.session import get_or_create_capy_session
from agent_server.service import AgentService
from agent_server.service.context import build_run_context
from agent_server.store import AgentStore
from tools import capy as capy_tools


def test_capy_session_hidden_from_sidebar(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    capy = get_or_create_capy_session(store, svc)
    worker = svc.create_session(title="Lab", workspace_path=None)
    assert is_capy_session(capy)
    ids = {item.id for item in store.list_sessions()}
    assert worker.id in ids
    assert capy.id not in ids
    again = get_or_create_capy_session(store, svc)
    assert again.id == capy.id


def test_capy_session_http_returns_json(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        first = client.get("/v1/capy/session")
        assert first.status_code == 200
        assert first.headers["content-type"].startswith("application/json")
        body = first.json()
        assert body["source"] == "capy"
        assert body["id"]
        second = client.get("/v1/capy/session")
        assert second.json()["id"] == body["id"]
        listed = client.get("/v1/sessions?source=capy")
        assert listed.status_code == 200
        assert listed.json()["data"][0]["id"] == body["id"]


def test_capy_run_context_skips_mcp_and_skills(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    capy = get_or_create_capy_session(store, svc)
    ctx = build_run_context(store, capy.id)
    assert ctx.capy_mode is True
    assert ctx.mcp_servers == []
    assert ctx.allowed_skill_names == []
    assert ctx.allowed_tool_names
    assert all(name.startswith("capy.") for name in ctx.allowed_tool_names)
    assert "capy.bench_launch" in ctx.allowed_tool_names
    assert "capy.doctor" in ctx.allowed_tool_names
    assert "capy.bench_results" in ctx.allowed_tool_names
    assert "capy.list_projects" in ctx.allowed_tool_names
    assert "orchestrate" in (ctx.specialist_instructions or "").lower()
    assert "execute" in CAPY_EXCLUDED_DEEPAGENTS_TOOLS
    assert "run_python" not in ctx.allowed_tool_names


def test_read_session_truncates(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    worker = svc.create_session(title="Fold BRCA1", workspace_path=None)
    for index in range(30):
        store.add_message(
            session_id=worker.id,
            role="user" if index % 2 == 0 else "assistant",
            content=f"turn {index} " + ("x" * 400),
        )
    result = extract_session(store, worker.id)
    assert result["ok"] is True
    assert result["truncated"] is True
    assert len(result["excerpt"]) <= 8000
    capy = get_or_create_capy_session(store, svc)
    blocked = extract_session(store, capy.id)
    assert blocked["ok"] is False


def test_seed_session_posts_prefixed_brief(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    bind_capy_deps(SimpleNamespace(store=store, service=svc))
    source = svc.create_session(title="Open", workspace_path=None)
    target = svc.create_session(title="AI", workspace_path=None)
    store.add_message(session_id=source.id, role="user", content="hello research")
    store.add_message(session_id=source.id, role="assistant", content="ok")
    sent = {}

    def fake_submit(*, session_id, content):
        sent["session_id"] = session_id
        sent["content"] = content
        return SimpleNamespace(run_id="run-1")

    monkeypatch.setattr(svc, "submit_message", fake_submit)
    result = capy_tools.capy_seed_session(
        source_id=source.id,
        target_id=target.id,
        brief="takeaways",
        also_prompt="continue",
    )
    assert result["ok"] is True
    assert sent["session_id"] == target.id
    assert "Imported context from “Open”" in sent["content"]
    assert "takeaways" in sent["content"]
    assert "continue" in sent["content"]
    assert "hello research" not in sent["content"]


def test_spawn_sessions_emits_open_split(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    bind_capy_deps(SimpleNamespace(store=store, service=svc))
    published = []
    monkeypatch.setattr(
        "agent_server.session_event_bus.session_event_bus.publish",
        lambda typ, payload: published.append((typ, payload)),
    )
    monkeypatch.setattr(
        svc,
        "submit_message",
        lambda **kwargs: SimpleNamespace(run_id="r"),
    )
    result = capy_tools.capy_spawn_sessions(count=3, message="hi")
    assert result["ok"] is True
    assert len(result["sessionIds"]) == 3
    published = [item for item in published if item[0] == "ui.command"]
    assert published
    typ, payload = published[0]
    assert typ == "ui.command"
    assert payload["action"] == "open_split"
    assert payload["sessionIds"] == result["sessionIds"]


def test_reset_capy_keeps_same_session(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    from agent_server.capy.session import reset_capy_session

    capy = get_or_create_capy_session(store, svc)
    store.add_message(session_id=capy.id, role="user", content="old")
    store.add_message(session_id=capy.id, role="assistant", content="reply")
    reset = reset_capy_session(store, svc)
    assert reset.id == capy.id
    assert store.list_messages(capy.id) == []
    assert store.list_sessions() == [] or all(
        item.id != capy.id for item in store.list_sessions()
    )
    hidden = store.list_sessions(include_hidden=True)
    assert any(item.id == capy.id for item in hidden)


def test_parse_suites_and_launch(monkeypatch):
    from agent_server.models.bench import BenchSuiteCard
    from agent_server.models.models_catalog import AgentModel, AgentModelList

    bind_capy_deps(
        SimpleNamespace(
            store=object(),
            models_service=SimpleNamespace(
                list_models=lambda **_k: AgentModelList(
                    data=[
                        AgentModel(
                            id="gpt-test",
                            label="GPT test",
                            provider="openai",
                            source="cloud",
                        )
                    ],
                    count=1,
                )
            ),
            specialists_service=SimpleNamespace(list=lambda: []),
        )
    )
    monkeypatch.setattr(
        "agent_server.bench_service.list_suite_cards",
        lambda _store: [
            BenchSuiteCard(
                id="gpqa",
                title="GPQA",
                available=True,
                sample_sizes=[10, 30],
                default_sample_size=10,
            )
        ],
    )
    monkeypatch.setattr(
        "agent_server.settings_service.SettingsService.get",
        lambda: SimpleNamespace(model="gpt-test", provider="openai"),
    )
    catalog = capy_tools.capy_bench_catalog()
    assert catalog["suites"][0]["id"] == "gpqa"
    assert catalog["models"][0]["id"] == "gpt-test"
    assert catalog["defaults"]["parallelRuns"] == 4

    captured = {}

    def fake_enqueue(_deps, req):
        captured["req"] = req
        return ["run-1", "run-2"]

    monkeypatch.setattr("agent_server.bench_service.enqueue", fake_enqueue)
    result = capy_tools.capy_bench_launch(
        suite_ids="gpqa:30",
        model="gpt-test",
        models="other-model",
        concurrency="2",
        parallel_runs="4",
        thinking="true",
        cleanup_sessions="false",
    )
    assert result["ok"] is True
    assert result["runIds"] == ["run-1", "run-2"]
    req = captured["req"]
    assert req.suites[0].suite_id == "gpqa"
    assert req.suites[0].sample_size == 30
    assert req.model == "gpt-test"
    assert req.models == ["other-model"]
    assert req.concurrency == 2
    assert req.parallel_runs == 4
    assert req.thinking is True
    assert req.client_surface == "ui"

    missing = capy_tools.capy_bench_launch(suite_ids="")
    assert missing["ok"] is False


def test_bench_results_and_inspect(monkeypatch):
    bind_capy_deps(
        SimpleNamespace(
            store=SimpleNamespace(
                lifetime_tokens_by_run=lambda ids: {rid: 4200 for rid in ids}
            )
        )
    )
    monkeypatch.setattr(
        "agent_server.bench_service.list_results_page",
        lambda **_k: {
            "data": [
                {
                    "run_id": "run-a",
                    "benchmark": "gpqa",
                    "model_id": "gpt-test",
                    "accuracy": 0.8,
                    "correct": 8,
                    "total": 10,
                    "time_s": 12.5,
                    "status": "completed",
                }
            ],
            "total": 1,
        },
    )
    listed = capy_tools.capy_bench_results()
    assert listed["runs"][0]["runId"] == "run-a"
    assert listed["runs"][0]["lifetimeTokens"] == 4200

    monkeypatch.setattr(
        "agent_server.bench_service.resolve_result_run_id", lambda rid: rid
    )
    monkeypatch.setattr(
        "agent_server.bench_service.get_result",
        lambda _rid: {
            "run_id": "run-a",
            "benchmark": "gpqa",
            "model_id": "gpt-test",
            "accuracy": 0.5,
            "correct": 1,
            "total": 2,
            "time_s": 9,
            "status": "completed",
            "input_tokens": 100,
            "output_tokens": 50,
            "lifetime_tokens": 150,
            "category_scores": {"bio": 0.5},
            "questions": [
                {"id": "q1", "correct": True, "prompt": "ok"},
                {"id": "q2", "correct": False, "prompt": "missed EGFR"},
            ],
        },
    )
    monkeypatch.setattr(
        "agent_server.bench_service.apply_live_status", lambda row: row
    )
    detail = capy_tools.capy_bench_inspect(run_id="run-a")
    assert detail["ok"] is True
    assert detail["run"]["lifetimeTokens"] == 150
    assert detail["run"]["questions"]["wrong"] == 1
    assert detail["run"]["questions"]["showingWrong"][0]["id"] == "q2"


def test_doctor_summarizes_problems_and_diagnostics(monkeypatch):
    monkeypatch.setattr(
        "agent.doctor.to_report",
        lambda **_k: {
            "ok": False,
            "summary": {"ok": 2, "warn": 1, "error": 1, "total": 4},
            "checks": [
                {"name": "python", "status": "ok", "detail": "3.13", "category": "runtime", "fix": None},
                {
                    "name": "llm",
                    "status": "error",
                    "detail": "No keys",
                    "category": "llm",
                    "fix": "Add a model",
                },
                {
                    "name": "mcp",
                    "status": "warn",
                    "detail": "offline",
                    "category": "mcp",
                    "fix": None,
                },
            ],
        },
    )
    monkeypatch.setattr(
        "agent.diagnostics.logging_setup.ensure_logging_configured", lambda: None
    )
    monkeypatch.setattr(
        "agent.diagnostics.collectors._system_info",
        lambda _v: {"service": "sandwalk", "version": "test", "python": "3.13"},
    )
    monkeypatch.setattr(
        "agent.diagnostics.collectors._skills_summary",
        lambda: {"total": 3, "enabled": 2, "disabled": 1},
    )
    monkeypatch.setattr(
        "tools.capy._log_issue_lines",
        lambda **_k: {"files": ["agent-server.log"], "newest": "agent-server.log", "issues": []},
    )
    report = capy_tools.capy_doctor(scope="full")
    assert report["ok"] is False
    assert report["counts"]["error"] == 1
    assert {item["name"] for item in report["problems"]} == {"llm", "mcp"}
    assert report["diagnostics"]["skills"]["enabled"] == 2


def test_spawn_and_move_honor_project_scope(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    from agent_server.capy.scope import set_capy_scope

    store = AgentStore(tmp_path / "agent.db")
    svc = AgentService(store)
    bind_capy_deps(SimpleNamespace(store=store, service=svc))
    project = store.create_project(name="EGFR")
    set_capy_scope(project_id=project.id, session_id=None)
    in_project = capy_tools.capy_spawn_sessions(count=1, title_prefix="In proj")
    assert in_project["ok"] is True
    created = store.get_session(in_project["sessionIds"][0])
    assert created is not None
    assert created.project_id == project.id
    under_all = capy_tools.capy_spawn_sessions(
        count=1, title_prefix="Loose", project_id="all"
    )
    loose = store.get_session(under_all["sessionIds"][0])
    assert loose is not None
    assert loose.project_id is None
    moved = capy_tools.capy_move_session(
        session_ids=loose.id, project_id="EGFR"
    )
    assert moved["ok"] is True
    assert store.get_session(loose.id).project_id == project.id
    listed = capy_tools.capy_list_projects()
    assert listed["currentProjectId"] == project.id
    set_capy_scope(project_id=None, session_id=None)
