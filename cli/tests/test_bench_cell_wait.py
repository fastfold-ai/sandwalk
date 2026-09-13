"""Bench cell wait: timeout, stall, and pause must not hang the suite."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agent_server.bench_service import spawn_core as sc


@pytest.fixture(autouse=True)
def _online(monkeypatch):
    monkeypatch.setattr(
        "agent_server.offline_mode.is_offline", lambda: False, raising=False
    )


class _Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _deps(*, status: str, events=None, interrupt=None):
    session = SimpleNamespace(
        id="sess-1",
        status=status,
        last_message_at="1970-01-01T00:16:40+00:00",
        updated_at="1970-01-01T00:16:40+00:00",
    )
    store = MagicMock()
    store.get_session.return_value = session
    store.list_messages.return_value = []
    store.list_events.return_value = events or []
    service = MagicMock()
    if interrupt is not None:
        service.interrupt.side_effect = interrupt
    deps = MagicMock()
    deps.worker_store.return_value = store
    deps.worker_service.return_value = service
    return deps, service, session


def test_wait_settles_when_session_goes_idle():
    clock = _Clock()
    deps, service, session = _deps(status="running")

    def flip(_sid: str):
        session.status = "idle"

    store = deps.worker_store()

    def get_session(_sid: str):
        if clock.now > 1_002:
            session.status = "idle"
        return session

    store.get_session.side_effect = get_session
    outcome = sc._wait_until_settled(
        deps,
        "sess-1",
        timeout_s=30,
        stall_s=30,
        now=clock,
        sleeper=clock.sleep,
    )
    assert outcome == "settled"
    service.interrupt.assert_not_called()


def test_wait_stalls_without_new_activity():
    clock = _Clock()
    deps, service, _session = _deps(status="running")
    outcome = sc._wait_until_settled(
        deps,
        "sess-1",
        timeout_s=600,
        stall_s=30,
        now=clock,
        sleeper=clock.sleep,
    )
    assert outcome == "stalled"
    service.interrupt.assert_called()


def test_wait_hard_timeout_interrupts():
    clock = _Clock()
    event = SimpleNamespace(timestamp="2099-01-01T00:00:00+00:00")
    deps, service, _session = _deps(status="running", events=[event])
    outcome = sc._wait_until_settled(
        deps,
        "sess-1",
        timeout_s=30,
        stall_s=600,
        now=clock,
        sleeper=clock.sleep,
    )
    assert outcome == "timeout"
    service.interrupt.assert_called()


def test_wait_stopped_on_pause():
    clock = _Clock()
    deps, service, _session = _deps(status="running")
    outcome = sc._wait_until_settled(
        deps,
        "sess-1",
        stop_check=lambda: "pause",
        timeout_s=30,
        stall_s=30,
        now=clock,
        sleeper=clock.sleep,
    )
    assert outcome == "stopped"
    service.interrupt.assert_called()
