"""Unit tests for skill runtime dependency adapters (anydoc)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.skills.deps import (
    get_adapter,
    has_runtime_deps,
    install_skill_deps,
    status_for,
)
from agent.skills.deps import anydoc as anydoc_mod


def test_has_runtime_deps_for_anydoc_skill():
    assert has_runtime_deps("convert-documents-to-markdown")
    assert has_runtime_deps("anydoc")
    assert not has_runtime_deps("fold")


def test_get_adapter_normalizes_underscores():
    adapter = get_adapter("convert_documents_to_markdown")
    assert adapter is not None
    assert adapter.adapter_id == "anydoc"


def test_unknown_skill_raises(monkeypatch):
    with pytest.raises(LookupError, match="No runtime dependency"):
        install_skill_deps("not-a-real-skill")


def test_doctor_missing_node(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(anydoc_mod, "anydoc_home", lambda: tmp_path / "anydoc")
    monkeypatch.setattr(anydoc_mod, "anydoc_bin", lambda: tmp_path / "anydoc" / "bin" / "anydoc")
    monkeypatch.setattr(anydoc_mod, "_find_node", lambda: (None, "Node.js not found on PATH"))
    monkeypatch.setattr(anydoc_mod, "_find_npm", lambda: None)

    status = anydoc_mod.doctor()
    assert status.status == "missing"
    assert status.adapter_id == "anydoc"
    assert any(c.name == "node" and c.status == "missing" for c in status.checks)
    assert status.setup_steps


def test_install_requires_node(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(anydoc_mod, "anydoc_home", lambda: tmp_path / "anydoc")
    monkeypatch.setattr(anydoc_mod, "anydoc_bin", lambda: tmp_path / "anydoc" / "bin" / "anydoc")
    monkeypatch.setattr(anydoc_mod, "_find_node", lambda: (None, "Node.js not found on PATH"))

    result = anydoc_mod.install(force=False)
    assert not result.ok
    assert "Node" in result.summary


def test_install_skips_when_ready(monkeypatch, tmp_path: Path):
    home = tmp_path / "anydoc"
    binary = home / "node_modules" / ".bin" / "anydoc"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    binary.chmod(0o755)

    monkeypatch.setattr(anydoc_mod, "anydoc_home", lambda: home)
    monkeypatch.setattr(anydoc_mod, "anydoc_bin", lambda: binary)
    monkeypatch.setattr(anydoc_mod, "_find_node", lambda: ("/usr/bin/node", "v22.0.0"))
    monkeypatch.setattr(anydoc_mod, "_find_npm", lambda: "/usr/bin/npm")
    monkeypatch.setattr(
        anydoc_mod,
        "_convert_sample",
        lambda _binary: (True, "Sample CSV converted to Markdown"),
    )

    result = anydoc_mod.install(force=False)
    assert result.ok
    assert "already installed" in result.summary.lower()


def test_status_for_all_returns_anydoc():
    rows = status_for(None)
    assert any(row.adapter_id == "anydoc" for row in rows)


def test_service_deps_mixin(monkeypatch):
    from agent_server.skills_service.deps import DepsMixin

    fake = SimpleNamespace(
        adapter_id="anydoc",
        skill_name="convert-documents-to-markdown",
        status="ok",
        summary="healthy",
        command="anydoc",
        has_runtime_deps=True,
        checks=[],
        setup_steps=[],
    )
    monkeypatch.setattr(
        "agent.skills.deps.has_runtime_deps",
        lambda name: name == "convert-documents-to-markdown",
    )
    monkeypatch.setattr("agent.skills.deps.doctor_skill", lambda name: fake)

    svc = DepsMixin()
    status = svc.get_deps("convert-documents-to-markdown")
    assert status.adapter_id == "anydoc"
    assert status.status == "ok"
