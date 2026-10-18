"""`mcp add` / `mcp remove` argument parsing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from agent.mcp_manage import crud_actions as crud


def test_add_and_remove(monkeypatch):
    console = MagicMock()
    store = MagicMock()
    store.create_mcp_server.return_value = SimpleNamespace(
        name="local", transport="streamable_http", id="abcdef123456"
    )
    assert crud.handle_add(["add"], console, store=store) == 2
    assert crud.handle_add(["add", "local", "--nope"], console, store=store) == 2
    assert crud.handle_add(["add", "local", "--transport", "weird", "--url", "http://x"], console, store=store) == 2
    assert crud.handle_add(["add", "local"], console, store=store) == 2

    assert crud.handle_add(
        ["add", "remote", "--url", "http://x", "--transport", "sse"],
        console,
        store=store,
    ) == 0
    store.create_mcp_server.return_value = SimpleNamespace(
        name="stdio", transport="stdio", id="bbbbbbbb"
    )
    assert crud.handle_add(
        ["add", "tool", "--command", "python", "--arg", "-m", "--args", "mod", "--transport", "stdio"],
        console,
        store=store,
    ) == 0
    assert crud.handle_add(
        ["add", "http", "--transport", "http", "--url", "http://y"],
        console,
        store=store,
    ) == 0
    assert crud.handle_add(
        ["add", "plain", "--transport", "streamablehttp", "--url", "http://z"],
        console,
        store=store,
    ) == 0

    service = MagicMock()
    assert crud.handle_remove(["remove"], console, store=store, service=service) == 2
    monkeypatch.setattr(crud, "resolve_server_ref", lambda ref, store: (None, None))
    assert crud.handle_remove(["remove", "missing"], console, store=store, service=service) == 1
    server = SimpleNamespace(id="id-1", name="PyMOL")
    entry = SimpleNamespace(id="pymol")
    monkeypatch.setattr(crud, "resolve_server_ref", lambda ref, store: (entry, server))
    service.disconnect.side_effect = RuntimeError("offline")
    assert crud.handle_remove(["remove", "pymol"], console, store=store, service=service) == 0
    store.delete_mcp_server.assert_called_with("id-1")
    monkeypatch.setattr(crud, "resolve_server_ref", lambda ref, store: (None, server))
    assert crud.handle_remove(["remove", "custom"], console, store=store, service=service) == 0
