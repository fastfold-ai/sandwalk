"""Slack should show that a mention is being worked on, and say when it is done.

Answers can take a minute. Without feedback on the message itself, the person
who asked has no way to tell the agent from a dead bot.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from agent_server.connectors.gateway import InboundMessage
from agent_server.connectors.service import (
    DONE_REACTION,
    FAILED_REACTION,
    WORKING_REACTION,
    ConnectorService,
)


@dataclass
class FakeSession:
    status: str


class FakeAdapter:
    """Records reaction calls the way Slack would receive them."""

    def __init__(self) -> None:
        self.calls: list[tuple[str | None, str | None]] = []

    async def set_reaction(self, *, channel_id, ts, add=None, remove=None):
        self.calls.append((add, remove))

    @property
    def reactions_added(self) -> list[str]:
        return [add for add, _ in self.calls if add]


class ScriptedStore:
    """Returns a queued sequence of statuses, then holds the last one."""

    def __init__(self, statuses: list[str]) -> None:
        self._statuses = list(statuses)
        self.polls = 0

    def get_session(self, session_id: str):
        self.polls += 1
        if not self._statuses:
            return None
        status = self._statuses.pop(0) if len(self._statuses) > 1 else self._statuses[0]
        return FakeSession(status=status)


def run(coro):
    return asyncio.run(coro)


def service_with(store, adapter) -> ConnectorService:
    service = ConnectorService.__new__(ConnectorService)
    service.store = store
    service._sockets = {"T1": adapter}
    service._progress_tasks = set()
    return service


def message() -> InboundMessage:
    return InboundMessage(
        team_id="T1",
        channel_id="C1",
        user_id="U1",
        text="hi",
        ts="1700000000.000100",
        mentions_me=True,
    )


def test_marks_working_then_done(monkeypatch):
    monkeypatch.setattr("agent_server.connectors.service._POLL_SECONDS", 0.01)
    adapter = FakeAdapter()
    store = ScriptedStore(["running", "running", "idle"])

    run(service_with(store, adapter)._run_progress(message(), ["s1"]))

    assert adapter.calls[0] == (WORKING_REACTION, None)
    assert adapter.calls[-1] == (DONE_REACTION, WORKING_REACTION)


def test_marks_failure_when_the_run_errors(monkeypatch):
    monkeypatch.setattr("agent_server.connectors.service._POLL_SECONDS", 0.01)
    adapter = FakeAdapter()
    store = ScriptedStore(["running", "error"])

    run(service_with(store, adapter)._run_progress(message(), ["s1"]))

    assert adapter.calls[-1] == (FAILED_REACTION, WORKING_REACTION)


def test_a_run_that_finishes_before_the_first_poll_still_resolves(monkeypatch):
    """Never leave the eyes on: a fast answer may never be observed as busy."""
    monkeypatch.setattr("agent_server.connectors.service._POLL_SECONDS", 0.01)
    monkeypatch.setattr("agent_server.connectors.service._START_GRACE_SECONDS", 0.05)
    adapter = FakeAdapter()
    store = ScriptedStore(["idle"])

    run(
        asyncio.wait_for(
            service_with(store, adapter)._run_progress(message(), ["s1"]), timeout=5
        )
    )

    assert adapter.calls[-1] == (DONE_REACTION, WORKING_REACTION)


def test_a_vanished_session_does_not_hang(monkeypatch):
    monkeypatch.setattr("agent_server.connectors.service._POLL_SECONDS", 0.01)
    adapter = FakeAdapter()
    store = ScriptedStore([])

    run(
        asyncio.wait_for(
            service_with(store, adapter)._run_progress(message(), ["s1"]), timeout=5
        )
    )

    assert adapter.calls[-1] == (FAILED_REACTION, WORKING_REACTION)


def test_no_socket_for_the_team_is_harmless():
    service = service_with(ScriptedStore(["idle"]), FakeAdapter())
    service._sockets = {}
    run(service._run_progress(message(), ["s1"]))


def test_reactions_never_break_the_answer(monkeypatch):
    """A workspace missing reactions:write must still get its reply."""
    monkeypatch.setattr("agent_server.connectors.service._POLL_SECONDS", 0.01)

    class Broken(FakeAdapter):
        async def set_reaction(self, **kwargs):
            raise RuntimeError("missing_scope")

    service = service_with(ScriptedStore(["running", "idle"]), Broken())
    with pytest.raises(RuntimeError):
        # The adapter itself raises here, which is why the real one swallows
        # every failure internally — see SlackSocketAdapter.set_reaction.
        run(service._run_progress(message(), ["s1"]))
