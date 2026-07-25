"""Socket Mode adapter behaviour that does not require the Slack SDK."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

from agent_server.connectors.gateway import InboundMessage
from agent_server.connectors.slack_socket import SlackSocketAdapter

T = TypeVar("T")


def run(coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


class FakeSocketClient:
    def __init__(self, *, alive: bool) -> None:
        self.alive = alive
        self.auto_reconnect_enabled = True
        self.reconnect_calls = 0

    def is_connected(self) -> bool:
        return self.alive

    async def connect_to_new_endpoint(self, force: bool = False) -> None:
        self.reconnect_calls += 1
        self.alive = True


class FakeSocket:
    def __init__(self, *, alive: bool) -> None:
        self.client = FakeSocketClient(alive=alive)


def adapter(on_message, **kwargs) -> SlackSocketAdapter:  # type: ignore[no-untyped-def]
    return SlackSocketAdapter(
        team_id="T1",
        bot_token="xoxb-test",
        app_token="xapp-test",
        on_message=on_message,
        **kwargs,
    )


def mention_event() -> dict:
    return {
        "type": "app_mention",
        "user": "U1",
        "channel": "C1",
        "ts": "1712000000.000100",
        "text": "<@B0BOT> hi",
    }


def test_handle_event_forwards_mapped_message() -> None:
    seen: list[InboundMessage] = []

    async def on_message(message: InboundMessage) -> None:
        seen.append(message)

    subject = adapter(on_message)
    subject._bot_user_id = "B0BOT"
    run(subject._handle_event(mention_event()))

    assert len(seen) == 1
    assert seen[0].team_id == "T1"
    assert seen[0].mentions_me is True


def test_handle_event_skips_unmappable_payloads() -> None:
    seen: list[InboundMessage] = []

    async def on_message(message: InboundMessage) -> None:
        seen.append(message)

    subject = adapter(on_message)
    subject._bot_user_id = "B0BOT"
    run(subject._handle_event({"type": "message", "bot_id": "B9"}))
    run(subject._handle_event({}))

    assert seen == []


def test_handler_failure_does_not_propagate() -> None:
    async def on_message(_message: InboundMessage) -> None:
        raise RuntimeError("agent exploded")

    subject = adapter(on_message)
    subject._bot_user_id = "B0BOT"

    # A failing handler must not bubble up and tear down the socket.
    run(subject._handle_event(mention_event()))


def test_watchdog_revives_a_dead_socket() -> None:
    async def on_message(_message: InboundMessage) -> None:
        return None

    subject = adapter(on_message, watchdog_interval=0.01)
    subject._socket = FakeSocket(alive=False)
    assert subject.connected is False

    async def drive() -> None:
        task = asyncio.create_task(subject._watchdog())
        await asyncio.sleep(0.05)
        subject._closing = True
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    run(drive())

    assert subject._socket.client.reconnect_calls >= 1
    assert subject.reconnects >= 1


def test_watchdog_leaves_a_healthy_socket_alone() -> None:
    async def on_message(_message: InboundMessage) -> None:
        return None

    subject = adapter(on_message, watchdog_interval=0.01)
    subject._socket = FakeSocket(alive=True)

    async def drive() -> None:
        task = asyncio.create_task(subject._watchdog())
        await asyncio.sleep(0.05)
        subject._closing = True
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    run(drive())

    assert subject._socket.client.reconnect_calls == 0
    assert subject.reconnects == 0


def test_connected_is_false_without_a_socket() -> None:
    async def on_message(_message: InboundMessage) -> None:
        return None

    assert adapter(on_message).connected is False


def test_connect_without_the_sdk_reports_failure(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import builtins

    real_import = builtins.__import__

    def blocked(name: str, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        if name.startswith(("slack_bolt", "slack_sdk")):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)

    async def on_message(_message: InboundMessage) -> None:
        return None

    assert run(adapter(on_message).connect()) is False
