"""Coverage for runtime event emit, session queries, and the skill prompt index."""

from __future__ import annotations

from types import SimpleNamespace

from agent.skills import prompt as skill_prompt
from agent_server.service.emit_events import (
    _event_payload,
    _todos_from_write_todos_call,
    make_event_emitter,
)
from agent_server.store import AgentStore
from agent_server.store.session_queries import exhausted_bench_question_ids, open_bench_question_ids


class _Stored:
    timestamp = "2026-10-19T00:00:00Z"


class _EmitStore:
    def __init__(self, session) -> None:
        self.session = session
        self.events: list[dict] = []
        self.statuses: list[str] = []
        self.usage: list[dict] = []

    def get_session(self, _session_id):
        return self.session

    def set_session_status(self, _session_id, status) -> None:
        self.statuses.append(status)
        self.session.status = status

    def append_event(self, **kwargs):
        self.events.append(kwargs)
        return _Stored()

    def upsert_usage_run(self, **kwargs) -> None:
        self.usage.append(kwargs)


def test_event_payloads_and_emitter(monkeypatch) -> None:
    assert _event_payload("stream", {"delta": "hi"})["delta"] == "hi"
    approval = _event_payload(
        "approval_required",
        {
            "interrupt_id": "i",
            "action_requests": [{"name": "write"}],
            "review_configs": [
                {"action_name": "write", "allowed_decisions": ["approve"], "description": "d"},
                "skip",
            ],
        },
    )
    assert approval["reviewConfigs"][0]["actionName"] == "write"
    assert _event_payload("approval_resolved", {"decisions": [{"type": "approve"}]})["decisions"]
    assert _todos_from_write_todos_call({"arguments": {}}) is None
    todos = _todos_from_write_todos_call(
        {"arguments": {"todos": ["nope", {"content": "  "}, {"content": "ship", "active_form": "shipping"}]}}
    )
    assert todos[0]["content"] == "ship"

    monkeypatch.setattr("agent_server.usage_service.parse.parse_usage_tokens", lambda _payload: {
        "input_tokens": 1,
        "output_tokens": 2,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
    })
    monkeypatch.setattr("agent_server.usage_service.parse.active_model_id", lambda: "gpt")
    monkeypatch.setattr("agent_server.usage_service.parse.active_provider", lambda: "openai")
    monkeypatch.setattr("agent_server.usage_service.parse.day_key_from_timestamp", lambda _ts: "2026-10-19")
    monkeypatch.setattr("agent_server.usage_service.parse.surface_for_session", lambda _session: "cli")
    monkeypatch.setattr(
        "agent_server.service.emit_events.plan_created_payload_from_tool_call",
        lambda **_kwargs: {"path": "plans/a.md", "title": "A", "summary": ""},
    )

    session = SimpleNamespace(source=None, status="running", project_id="p")
    store = _EmitStore(session)
    emit = make_event_emitter(store, "s1", "r1")
    emit("mystery")
    emit("stream", delta="tok")
    emit("activity", text="working")
    emit("usage", input_tokens=1, tokens_per_second=3)
    emit(
        "tool_start",
        name="write_todos",
        arguments={"todos": [{"content": "ship"}]},
        tool_call_id="c1",
    )
    emit("approval_required", interrupt_id="i", action_requests=[], review_configs=[])
    emit("approval_resolved", interrupt_id="i", decisions=[])
    assert store.usage
    assert any(event["event_type"] == "todos.updated" for event in store.events)
    assert any(event["event_type"] == "plan.created" for event in store.events)
    assert store.statuses == ["awaiting_approval", "running"]

    session.status = "idle"
    before = len(store.events)
    emit("activity", text="late")
    assert len(store.events) == before

    bench = SimpleNamespace(source="bench", status="running", project_id=None)
    bench_store = _EmitStore(bench)
    bench_emit = make_event_emitter(bench_store, "b", "r")
    bench_emit("stream", delta="x")
    bench_emit("activity", text="quiet")
    assert bench_store.events == []


def test_session_queries_filter_bench_and_search(tmp_path) -> None:
    store = AgentStore(tmp_path / "agent.db", exclusive=True)
    project = store.create_project(name="Lab")
    normal = store.create_session(title="Find me", workspace_path=None, project_id=project.id, source="slack")
    bench = store.create_session(title="q1 · item", workspace_path=None, project_id=project.id, source="bench")
    store.create_session(title="hidden", workspace_path=None, project_id=None, source="capy")
    store.set_session_status(bench.id, "running")
    store.set_session_status(normal.id, "interrupted")

    assert "bench" not in store.sessions_revision()
    listed = store.list_sessions(project_id=project.id)
    assert {item.id for item in listed} == {normal.id, bench.id}
    assert store.list_sessions(include_hidden=True)
    assert store.get_session(normal.id).title == "Find me"
    assert store.get_session("missing") is None
    assert store.get_session_by_source("  ") is None
    assert store.get_session_by_source("CAPY").source == "capy"
    assert store.list_sessions_by_ids(["", normal.id])[0].id == normal.id
    assert store.list_sessions_by_ids([]) == []
    counts = store.bench_question_session_counts([project.id, " ", "missing"])
    assert counts[project.id]["q1"]["running"] == 1
    assert store.interrupted_bench_questions_by_project([project.id])[project.id] == ["q1"]
    assert store.bench_question_session_counts([]) == {}
    assert open_bench_question_ids({"q": {"running": 0, "interrupted": 2}}) == []
    assert exhausted_bench_question_ids({"q": {"running": 0, "interrupted": 2}}) == ["q"]
    found = store.search_sessions("find", limit=0)
    assert found[0].id == normal.id
    assert store.search_sessions("   ")


def test_skill_prompt_index_helpers(tmp_path, monkeypatch) -> None:
    missing = tmp_path / "gone"
    assert skill_prompt._path_signature(missing) == ""
    assert skill_prompt._read_text_prefix(missing, 10) == ""
    assert skill_prompt._read_text_prefix(tmp_path, 0) == ""
    note = tmp_path / "note.txt"
    note.write_text("hello skill", encoding="utf-8")
    assert "hello" in skill_prompt._read_text_prefix(note, 5)
    assert "skill" in skill_prompt._tokenize_skill_text("The skill and a plan")

    cache = tmp_path / "index.json"
    monkeypatch.setattr(skill_prompt._skills, "SKILLS_PROMPT_INDEX_CACHE", cache)
    assert skill_prompt._read_prompt_index_cache()["entries"] == {}
    cache.write_text("{", encoding="utf-8")
    assert skill_prompt._read_prompt_index_cache()["entries"] == {}
    cache.write_text("[]", encoding="utf-8")
    assert skill_prompt._read_prompt_index_cache()["entries"] == {}
    cache.write_text('{"version": 2, "entries": []}', encoding="utf-8")
    assert skill_prompt._read_prompt_index_cache()["entries"] == {}
    skill_prompt._write_prompt_index_cache({"sites": {"snippet": "build"}})
    assert skill_prompt._read_prompt_index_cache()["entries"]["sites"]["snippet"] == "build"

    def refuse(_path):
        raise OSError("ro")

    monkeypatch.setattr(skill_prompt._skills.SKILLS_PROMPT_INDEX_CACHE.__class__, "write_text", refuse)
    skill_prompt._write_prompt_index_cache({"sites": {"snippet": "nope"}})
