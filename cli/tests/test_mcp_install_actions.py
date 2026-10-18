"""CLI `mcp install` / `mcp doctor` branches for featured local servers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from agent.mcp_manage import install_actions as actions


def _console() -> MagicMock:
    return MagicMock()


def test_install_usage_and_unknown_catalog():
    console = _console()
    assert actions.handle_install(["install"], console, store=None, service=None) == 2
    assert actions.handle_install(["install", "nope"], console, store=None, service=None) == 1


def test_install_pymol_and_raymol_success_and_warnings():
    service = MagicMock()
    service.install_featured.return_value = {
        "launcherMessage": "launcher ok",
        "enable": {"ok": True, "toolCount": 3},
    }
    console = _console()
    assert actions.handle_install(["install", "pymol"], console, store=None, service=service) == 0
    assert actions.handle_install(
        ["install", "raymol", "--force"], console, store=None, service=service
    ) == 0

    service.install_featured.return_value = {
        "enable": {"ok": False, "message": "probe failed"},
    }
    assert actions.handle_install(["install", "pymol", "-f"], console, store=None, service=service) == 0
    assert actions.handle_install(["install", "raymol"], console, store=None, service=service) == 0

    service.install_featured.return_value = {}
    assert actions.handle_install(["install", "pymol"], console, store=None, service=service) == 1


def test_install_featured_errors_and_remote_catalog():
    service = MagicMock()
    service.install_featured.side_effect = RuntimeError("boom")
    console = _console()
    assert actions.handle_install(["install", "pymol"], console, store=None, service=service) == 1
    service.install_featured.side_effect = KeyError("missing")
    assert actions.handle_install(["install", "raymol"], console, store=None, service=service) == 1

    service.install_featured.side_effect = None
    service.install_featured.return_value = {
        "server": SimpleNamespace(name="Tamarind"),
    }
    assert actions.handle_install(["install", "tamarind"], console, store=None, service=service) == 0
    service.install_featured.side_effect = KeyError("nope")
    assert actions.handle_install(["install", "tamarind"], console, store=None, service=service) == 1


def test_doctor_unknown_pymol_raymol_and_remote(monkeypatch):
    console = _console()
    assert actions.handle_doctor(["doctor", "missing"], console, store=None, service=None) == 1

    monkeypatch.setattr(actions, "pymol_doctor_checks", lambda: [
        {"status": "ok", "detail": "launcher"},
        {"status": "error", "detail": "token", "fix": "start listening"},
        {"status": "weird", "detail": "other"},
    ])
    monkeypatch.setattr(actions, "raymol_doctor_checks", lambda: [
        {"status": "warn", "detail": "app"},
    ])
    monkeypatch.setattr(actions, "credentials_configured", lambda entry: True)
    service = MagicMock()
    service.validate.return_value = {"ok": False, "message": "down"}
    assert actions.handle_doctor(["doctor"], console, store=None, service=service) == 1
    service.validate.return_value = {"ok": True, "message": "up"}
    monkeypatch.setattr(actions, "pymol_doctor_checks", lambda: [{"status": "ok", "detail": "fine"}])
    assert actions.handle_doctor(["doctor", "pymol"], console, store=None, service=service) == 0

    monkeypatch.setattr(actions, "credentials_configured", lambda entry: False)
    assert actions.handle_doctor(["doctor", "raymol"], console, store=None, service=service) == 1
    monkeypatch.setattr(actions, "credentials_configured", lambda entry: True)
    service.validate.return_value = {"ok": True, "message": "raymol up"}
    monkeypatch.setattr(actions, "raymol_doctor_checks", lambda: [{"status": "ok", "detail": "fine"}])
    assert actions.handle_doctor(["doctor", "raymol"], console, store=None, service=service) == 0

    service.validate.return_value = {"ok": False, "message": "remote down"}
    assert actions.handle_doctor(["doctor", "tamarind"], console, store=None, service=service) == 1
    service.validate.return_value = {"ok": True, "message": "remote up"}
    assert actions.handle_doctor(["doctor", "tamarind"], console, store=None, service=service) == 0
