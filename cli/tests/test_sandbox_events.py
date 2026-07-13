"""Tests for in-process sandbox status event bus."""

from __future__ import annotations

import asyncio

from agent_server.models import SessionSandboxStatus
from agent_server.sandbox_events import SessionSandboxEventBus, build_sandbox_event_payload


def _status(session_id: str = "s1", status: str = "running") -> SessionSandboxStatus:
    return SessionSandboxStatus(
        session_id=session_id,
        backend="modal",
        status=status,  # type: ignore[arg-type]
        modal_configured=True,
    )


def test_build_sandbox_event_payload():
    payload = build_sandbox_event_payload(_status())
    assert payload["type"] == "sandbox_status"
    assert payload["ready"] is True
    assert payload["sessionId"] == "s1"
    assert payload["status"] == "running"


def test_event_bus_delivers_to_subscriber():
    async def _run() -> None:
        bus = SessionSandboxEventBus()
        bus.bind_loop(asyncio.get_running_loop())

        async def _collect() -> dict:
            async for event in bus.subscribe("s1"):
                return event
            raise AssertionError("no event")

        task = asyncio.create_task(_collect())
        await asyncio.sleep(0)
        bus.publish(_status(status="starting"))
        event = await asyncio.wait_for(task, timeout=1)
        assert event["status"] == "starting"
        assert event["type"] == "sandbox_status"

    asyncio.run(_run())
