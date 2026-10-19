"""Coverage for Python env sizing and MCP mention steering."""

from __future__ import annotations

from pathlib import Path

from agent.mcp_manage.mentions import build_mcp_mention_context, extract_mcp_mentions
from agent_server.storage_service.python_env import (
    _python_env_category,
    list_installed_packages,
    resolve_python_env_root,
)


def test_resolve_python_env_root_and_packages(tmp_path, monkeypatch) -> None:
    venv = tmp_path / "venv"
    bindir = venv / "bin"
    bindir.mkdir(parents=True)
    exe = bindir / "python"
    exe.write_text("", encoding="utf-8")
    (venv / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
    assert resolve_python_env_root(exe) == venv.resolve()

    plain = tmp_path / "plain"
    (plain / "bin").mkdir(parents=True)
    bare = plain / "bin" / "python"
    bare.write_text("", encoding="utf-8")
    assert resolve_python_env_root(bare) == plain.resolve()

    system = tmp_path / "python3"
    system.write_text("", encoding="utf-8")
    site_dir = tmp_path / "site-packages"
    site_dir.mkdir()
    monkeypatch.setattr("site.getsitepackages", lambda: [str(site_dir), str(tmp_path / "missing")])
    monkeypatch.setattr("site.getusersitepackages", lambda: str(tmp_path / "no-user"))
    assert resolve_python_env_root(system) == site_dir.resolve()

    def no_sites():
        raise AttributeError("no")

    monkeypatch.setattr("site.getsitepackages", no_sites)
    monkeypatch.setattr("site.getusersitepackages", lambda: None)
    assert resolve_python_env_root(system) is None

    class Dist:
        def __init__(self, name, version, boom=False):
            self.name = name
            self._version = version
            self.boom = boom
            self.metadata = {"Name": name}

        @property
        def version(self):
            if self.boom:
                raise RuntimeError("meta")
            return self._version

    monkeypatch.setattr(
        "importlib.metadata.distributions",
        lambda: [Dist("Demo", "1"), Dist("demo", "2"), Dist("", "0"), Dist("bad", "1", boom=True)],
    )
    names = [name for name, _version in list_installed_packages()]
    assert names == ["Demo"]

    def boom_dist():
        raise RuntimeError("metadata")

    monkeypatch.setattr("importlib.metadata.distributions", boom_dist)
    assert list_installed_packages() == []

    monkeypatch.setattr(
        "agent_server.storage_service.resolve_python_env_root",
        lambda: None,
    )
    assert _python_env_category() is None
    monkeypatch.setattr(
        "agent_server.storage_service.resolve_python_env_root",
        lambda: venv,
    )
    monkeypatch.setattr("agent_server.storage_service._path_size_bytes", lambda _root: 12)
    monkeypatch.setattr(
        "agent_server.storage_service.list_installed_packages",
        lambda: [("Pkg", "1")] * 401,
    )
    category = _python_env_category()
    assert category is not None
    assert category.label.endswith(venv.name + ")")
    assert category.children[-1].id == "python_env:pkg:truncated"


def test_mcp_mentions_extract_and_steer(monkeypatch) -> None:
    text = "use ⟦mcp:ray%20mol:RayMol⟧ and mcp: linear then mcp:linear"
    mentions = extract_mcp_mentions(text)
    assert mentions[0].startswith("ray")
    assert any(item.lower().endswith("linear") for item in mentions)
    assert extract_mcp_mentions("") == []

    class Store:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def list_mcp_servers(self):
            raise RuntimeError("no store")

    monkeypatch.setattr("agent_server.store.AgentStore", Store)
    enabled = {
        "name": "Linear",
        "catalog_id": "lin-catalog",
        "id": "srv",
        "enabled": True,
        "description": "issues",
    }
    tools = {f"tool-{index}": f"tool-{index}" for index in range(25)}
    context = build_mcp_mention_context(
        "mcp:Linear",
        mcp_servers=[enabled, "skip"],
        mcp_tools_by_server={"lin-catalog": list(tools)},
        max_mcps=1,
    )
    assert "Linear (`lin-catalog`)" in context
    assert "(+1 more)" in context

    disabled = {"name": "RayMol", "catalog_id": "raymol", "enabled": False}

    class DisabledStore(Store):
        def list_mcp_servers(self):
            return [disabled, "nope"]

    monkeypatch.setattr("agent_server.store.AgentStore", DisabledStore)
    steered = build_mcp_mention_context("mcp:raymol", mcp_servers=[])
    assert "RayMol" in steered
    assert "not enabled" in steered

    class PresentStore(Store):
        def list_mcp_servers(self):
            return [{"name": "Exa", "catalog_id": "exa", "enabled": True}]

    monkeypatch.setattr("agent_server.store.AgentStore", PresentStore)
    filtered = build_mcp_mention_context("mcp:exa", mcp_servers=[])
    assert "Exa" in filtered

    unknown = build_mcp_mention_context("mcp:not-a-real-server-xyz", mcp_servers=[])
    assert "not found" in unknown
