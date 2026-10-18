"""`/specialist` argv dispatch without touching the specialist store."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from agent.specialists_manage import dispatch


def test_specialist_argv(monkeypatch):
    console = MagicMock()
    for name in ("cmd_list", "cmd_active", "cmd_show", "cmd_use", "cmd_clear", "cmd_delete", "cmd_create"):
        monkeypatch.setattr(dispatch, name, lambda *args, **kwargs: 0)

    assert dispatch.handle_specialist_argv([], console) == 0
    assert dispatch.handle_specialist_argv(["list"], console) == 0
    assert dispatch.handle_specialist_argv(["ls"], console) == 0
    assert dispatch.handle_specialist_argv(["active"], console) == 0
    assert dispatch.handle_specialist_argv(["status"], console) == 0
    assert dispatch.handle_specialist_argv(["show"], console) == 1
    assert dispatch.handle_specialist_argv(["show", "fold", "lab"], console) == 0
    assert dispatch.handle_specialist_argv(["use"], console) == 1
    assert dispatch.handle_specialist_argv(["enable", "fold"], console) == 0
    assert dispatch.handle_specialist_argv(["clear"], console) == 0
    assert dispatch.handle_specialist_argv(["unset"], console) == 0
    assert dispatch.handle_specialist_argv(["delete"], console) == 1
    assert dispatch.handle_specialist_argv(["rm", "fold"], console) == 0
    assert dispatch.handle_specialist_argv(["create"], console) == 1
    assert dispatch.handle_specialist_argv(["create", '""'], console) == 1
    assert dispatch.handle_specialist_argv(["add", '"Fold Lab"', "--slug", "fold"], console) == 0

    monkeypatch.setattr(dispatch, "resolve_specialist_ref", lambda ref: SimpleNamespace(slug="fold"))
    assert dispatch.handle_specialist_argv(["fold"], console) == 0
    monkeypatch.setattr(dispatch, "resolve_specialist_ref", lambda ref: None)
    assert dispatch.handle_specialist_argv(["nope"], console) == 1
