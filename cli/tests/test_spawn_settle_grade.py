"""Cell wait and grading without starting a bench run."""

from __future__ import annotations

from types import SimpleNamespace

from agent_server.bench_service import spawn_core as spawn


class _Msg:
    def __init__(self, role, content=""):
        self.role = role
        self.content = content


class _Session:
    def __init__(self, status, session_id="s1"):
        self.status = status
        self.id = session_id
        self.last_message_at = None
        self.updated_at = None


class _Store:
    def __init__(self, session, messages=None, events=None, boom_events=False):
        self.session = session
        self.messages = messages or []
        self.events = events or []
        self.boom_events = boom_events
        self.interrupts = []

    def get_session(self, session_id):
        return self.session

    def list_messages(self, session_id):
        return self.messages

    def list_events(self, session_id):
        if self.boom_events:
            raise RuntimeError("events")
        return self.events


class _Deps:
    def __init__(self, store):
        self.store = store
        self._svc = SimpleNamespace(interrupt=lambda session_id: None)

    def worker_store(self):
        return self.store

    def worker_service(self):
        return self._svc


def test_epoch_helpers():
    assert spawn._iso_epoch(None) == 0
    assert spawn._iso_epoch(3) == 3
    assert spawn._iso_epoch("not-a-date") == 0
    assert spawn._iso_epoch("2026-01-01T00:00:00Z") > 0
    session = SimpleNamespace(id="s", last_message_at=5, updated_at=2)
    assert spawn._session_activity_epoch(SimpleNamespace(), session) == 5
    event = SimpleNamespace(timestamp="2026-01-02T00:00:00Z")
    store = SimpleNamespace(list_events=lambda sid: [event])
    assert spawn._session_activity_epoch(store, session) > 5
    def _boom(sid):
        raise RuntimeError("no")

    store.list_events = _boom
    assert spawn._session_activity_epoch(store, session) == 5


def test_wait_until_settled_outcomes(monkeypatch):
    monkeypatch.setattr(spawn, "is_offline", lambda: False, raising=False)
    monkeypatch.setattr("agent_server.offline_mode.is_offline", lambda: False)

    missing = _Deps(_Store(None))
    assert spawn._wait_until_settled(missing, session_id="s1", timeout_s=30, stall_s=30) == "settled"

    stopped = _Deps(_Store(_Session("running")))

    def _interrupt_fails(session_id):
        raise RuntimeError("no")

    stopped._svc.interrupt = _interrupt_fails
    assert spawn._wait_until_settled(
        stopped, session_id="s1", timeout_s=30, stall_s=30, stop_check=lambda: "pause"
    ) == "stopped"
    assert spawn._wait_until_settled(
        stopped, session_id="s1", timeout_s=30, stall_s=30, cancel_check=lambda: True
    ) == "stopped"

    clock = {"t": 0.0}

    def now():
        return clock["t"]

    def sleep(seconds):
        clock["t"] += seconds

    finished = _Deps(_Store(_Session("running")))

    def flip(session_id):
        finished.store.session.status = "idle"

    finished.store.get_session = lambda session_id: finished.store.session
    # first look is running, sleep happens only after the settled check fails
    states = ["running", "idle"]

    def get_session(session_id):
        status = states.pop(0) if states else "idle"
        return _Session(status)

    finished.store.get_session = get_session
    assert spawn._wait_until_settled(
        finished, session_id="s1", timeout_s=30, stall_s=30, now=now, sleeper=sleep
    ) == "settled"

    clock["t"] = 0
    idle = _Deps(_Store(_Session("idle"), messages=[_Msg("assistant", "done")]))
    assert spawn._wait_until_settled(
        idle, session_id="s1", timeout_s=30, stall_s=30, now=now, sleeper=sleep
    ) == "settled"

    ticks = {"n": -1.0}

    def tick():
        ticks["n"] += 1
        return ticks["n"]

    stalled = _Deps(_Store(_Session("running")))
    assert spawn._wait_until_settled(
        stalled, session_id="s1", timeout_s=30, stall_s=30, now=tick, sleeper=lambda seconds: None
    ) == "stalled"

    ticks["n"] = -1.0
    monkeypatch.setattr("agent_server.offline_mode.is_offline", lambda: True)

    def _late(session_id):
        raise RuntimeError("late")

    waiting = _Deps(_Store(_Session("queued")))
    waiting._svc.interrupt = _late
    assert spawn._wait_until_settled(
        waiting, session_id="s1", timeout_s=30, stall_s=30, now=tick, sleeper=lambda seconds: None
    ) == "timeout"


def test_grade_session(monkeypatch):
    question = SimpleNamespace(
        eval_mode="checklist",
        ideal="42",
        source={"categories": "bio"},
        metadata={"checklist": ["tool"], "judge_rubric": "be strict"},
        focus="",
        question="What is the answer?",
        id="q1",
    )
    cell = SimpleNamespace(question=question, question_id="q1", prompt="What?")
    store = _Store(
        _Session("idle"),
        messages=[_Msg("user", "q"), _Msg("assistant", "Answer: 42")],
        events=[SimpleNamespace(type="tool")],
    )
    monkeypatch.setattr(spawn, "collect_tool_names_from_events", lambda events: ["run_python"])
    monkeypatch.setattr(spawn, "heuristic_checklist", lambda tools, checklist: {"tool": False})
    monkeypatch.setattr(
        spawn,
        "run_llm_judge",
        lambda **kwargs: {"overall_pass": True, "predicted": "42"},
    )
    monkeypatch.setattr(spawn, "grade_row", lambda **kwargs: True)
    row = spawn._grade_session(_Deps(store), session_id="s1", cell=cell, index=3)
    assert row["correct"] is True
    assert row["judge"]["predicted"] == "42"
    assert row["tools_seen"] == ["run_python"]

    question.eval_mode = "code_exec"
    monkeypatch.setattr(spawn, "grade_row", lambda **kwargs: kwargs["predicted"].startswith("print"))
    store.messages = [_Msg("assistant", "print(1)")]
    coded = spawn._grade_session(_Deps(store), session_id="s1", cell=cell, index=1)
    assert coded["eval_mode"] == "code_exec"
    assert coded["predicted"].startswith("print")
