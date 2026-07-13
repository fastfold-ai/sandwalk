"""Tests for Modal dependency auto-heal helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.sandbox_deps import ensure_modal_deps, modal_deps_importable


def test_modal_deps_importable_false():
    with patch(
        "agent.sandbox_deps.importlib.import_module",
        side_effect=ImportError("No module named 'langchain_modal'"),
    ):
        ok, detail = modal_deps_importable()
    assert ok is False
    assert "langchain_modal" in detail


def test_ensure_modal_deps_skips_install_when_present():
    with patch(
        "agent.sandbox_deps.modal_deps_importable",
        return_value=(True, "ok"),
    ):
        ok, detail = ensure_modal_deps(auto_install=True)
    assert ok is True
    assert detail == "ok"


def test_ensure_modal_deps_auto_installs(monkeypatch):
    calls = {"n": 0}

    def _importable():
        calls["n"] += 1
        if calls["n"] == 1:
            return False, "missing"
        return True, "langchain-modal and modal importable"

    proc = MagicMock(returncode=0, stderr="", stdout="")
    with patch("agent.sandbox_deps.modal_deps_importable", side_effect=_importable):
        with patch("agent.sandbox_deps.shutil.which", return_value="/usr/bin/uv"):
            with patch("agent.sandbox_deps.subprocess.run", return_value=proc) as run:
                ok, detail = ensure_modal_deps(auto_install=True)
    assert ok is True
    assert "Installed" in detail
    assert run.called
    args = run.call_args.args[0]
    assert args[:3] == ["/usr/bin/uv", "pip", "install"]
    assert "langchain-modal>=0.0.1" in args
    assert "modal>=0.73" in args


def test_ensure_modal_deps_no_auto_install():
    with patch(
        "agent.sandbox_deps.modal_deps_importable",
        return_value=(False, "missing"),
    ):
        ok, detail = ensure_modal_deps(auto_install=False)
    assert ok is False
    assert "pip install" in detail
