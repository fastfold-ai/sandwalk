"""Tests for datasets + tools management APIs."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.config import Config
from agent_server.app import create_app
from agent_server.datasets_service import DatasetsService
from agent_server.tools_service import ToolsService
from agent_server.models import UpdateToolRequest


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import agent.config as config_mod

    config_dir = tmp_path / ".fastfold-cli"
    config_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config_mod, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(
        config_mod, "CONFIG_BACKUP_FILE", config_dir / "config.json.bak"
    )
    cfg = Config(
        {
            "data.base": str(config_dir / "data"),
            "agent.hidden_tools": [],
        }
    )
    cfg.save()
    return cfg


def test_datasets_list_and_manual_install(isolated_config: Config):
    service = DatasetsService()
    listing = service.list_datasets()
    assert listing.count >= 1
    ids = {d.id for d in listing.data}
    assert "depmap" in ids

    # A manual dataset cannot be auto-installed (l1000 needs a prepare script).
    result = service.install("l1000")
    assert result.ok is False
    assert "manual" in result.summary.lower()

    with pytest.raises(KeyError):
        service.install("does-not-exist")


def test_hidden_tools_helpers(isolated_config: Config):
    cfg = Config.load()
    assert cfg.hidden_tools() == []
    cfg.set_tool_hidden("target.degron_predict", True)
    cfg.save()
    reloaded = Config.load()
    assert reloaded.is_tool_hidden("target.degron_predict")
    reloaded.set_tool_hidden("target.degron_predict", False)
    reloaded.save()
    assert Config.load().hidden_tools() == []


def test_tools_service_toggle(isolated_config: Config):
    service = ToolsService()
    catalog = service.list_tools()
    assert catalog.count > 0
    sample = catalog.data[0]
    assert sample.enabled is True

    updated = service.update_tool(sample.id, UpdateToolRequest(enabled=False))
    assert updated.enabled is False

    enabled_only = service.list_tools(enabled_only=True)
    assert all(t.id != sample.id for t in enabled_only.data)

    with pytest.raises(KeyError):
        service.set_tool_enabled("nope.nope", False)


def test_tools_service_batch(isolated_config: Config):
    service = ToolsService()
    catalog = service.list_tools()
    ids = [t.id for t in catalog.data[:4]]

    disabled = service.batch_action("disable", ids)
    assert disabled.ok is True
    assert disabled.requested == len(ids)
    assert set(disabled.succeeded) == set(ids)
    after = {t.id: t.enabled for t in service.list_tools().data}
    assert all(after[i] is False for i in ids)

    enabled = service.batch_action("enable", ids)
    assert enabled.ok is True
    after2 = {t.id: t.enabled for t in service.list_tools().data}
    assert all(after2[i] is True for i in ids)

    mixed = service.batch_action("disable", [ids[0], "nope.nope"])
    assert mixed.ok is False
    assert "nope.nope" in mixed.failed
    assert ids[0] in mixed.succeeded


def test_data_tools_http_routes(isolated_config: Config, tmp_path: Path):
    app = create_app(
        store_path=tmp_path / "agent-dt.db", allowed_hosts=["testserver"]
    )
    client = TestClient(app)

    datasets = client.get("/v1/datasets")
    assert datasets.status_code == 200
    assert datasets.json()["count"] >= 1

    tools = client.get("/v1/tools")
    assert tools.status_code == 200
    payload = tools.json()
    assert payload["count"] > 0
    tool_id = payload["data"][0]["id"]

    patched = client.patch(f"/v1/tools/{tool_id}", json={"enabled": False})
    assert patched.status_code == 200
    assert patched.json()["enabled"] is False

    missing = client.patch("/v1/tools/nope.nope", json={"enabled": False})
    assert missing.status_code == 404

    manual = client.post("/v1/datasets/l1000/install")
    assert manual.status_code == 200
    assert manual.json()["ok"] is False

    unknown = client.post("/v1/datasets/nope/install")
    assert unknown.status_code == 404
