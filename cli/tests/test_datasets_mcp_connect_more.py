"""Coverage for dataset install, MCP connect routes, and Groq-style chat models."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.deepagents_runtime.chat_model_cerebras import build_cerebras_chat_model
from agent.deepagents_runtime.chat_model_fireworks import build_fireworks_chat_model
from agent.deepagents_runtime.chat_model_groq import build_groq_chat_model
from agent.mcp_manage.resolve import resolve_server_ref
from agent_server.datasets_service import DatasetsService
from agent_server.routes.mcp_servers_connect import register_mcp_server_connect_routes


def test_datasets_service_install_and_remove(monkeypatch) -> None:
    records = [
        {
            "id": "depmap",
            "description": "crispr",
            "status": "missing",
            "files_found": 0,
            "files_expected": 2,
            "size_bytes": None,
            "size_display": "-",
            "auto_download": True,
            "path": "/data/depmap",
            "source": "figshare",
            "note": None,
        }
    ]

    def listed():
        return list(records)

    monkeypatch.setattr("data.downloader.list_dataset_records", listed)
    service = DatasetsService()
    assert service.list_datasets().count == 1
    assert service.get_dataset(" missing ") is None
    assert service.get_dataset("depmap").id == "depmap"

    monkeypatch.setattr(
        "data.downloader.DATASETS",
        {
            "depmap": {"auto_download": True},
            "manual": {"auto_download": False, "note": "fetch it"},
            "blank": {"auto_download": False, "note": "  "},
        },
    )

    outcome = {"status": "complete"}

    def download(name):
        records[0]["status"] = outcome["status"]

    monkeypatch.setattr("data.downloader.download_dataset", download)
    installed = service.install("depmap")
    assert installed.ok is True
    outcome["status"] = "partial"
    partial = service.install("depmap")
    assert partial.ok is False
    outcome["status"] = "missing"
    failed = service.install("depmap")
    assert "did not complete" in failed.summary
    manual = service.install("manual")
    assert manual.ok is False
    assert "fetch it" in manual.summary
    blank = service.install("blank")
    assert "Manual download required" in blank.summary
    try:
        service.install("nope")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass

    def removed(name):
        return {**records[0], "id": name, "removed": True, "status": "missing"}

    monkeypatch.setattr("data.downloader.remove_dataset", removed)
    gone = service.remove("depmap")
    assert "removed from local disk" in gone.summary

    def absent(name):
        return {**records[0], "id": name, "removed": False, "status": "missing"}

    monkeypatch.setattr("data.downloader.remove_dataset", absent)
    assert "not installed" in service.remove("depmap").summary
    try:
        service.remove("nope")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass


def test_mcp_connect_routes_and_server_resolution(monkeypatch) -> None:
    service = SimpleNamespace(
        start_oauth_custom=lambda server_id: {
            "authorizeUrl": "https://example.test/auth",
            "state": "st",
            "redirectUri": "https://example.test/back",
            "serverId": server_id,
        },
        connect_custom_api_key=lambda server_id, api_key: {
            "ok": True,
            "toolCount": 1,
            "message": "connected",
            "tools": ["search"],
        },
        validate=lambda catalog_id, server_id: {
            "ok": True,
            "toolCount": 1,
            "message": "ready",
            "tools": ["search"],
            "toolDetails": [{"name": "search", "title": "Search", "description": "d", "inputSchema": {}}, "skip"],
        },
    )
    app = FastAPI()
    register_mcp_server_connect_routes(app, SimpleNamespace(mcp_service=service))
    client = TestClient(app)
    oauth = client.post("/v1/mcp-servers/srv/connect", json={"method": "oauth"})
    assert oauth.status_code == 200
    assert oauth.json()["authorizeUrl"].startswith("https://")
    missing_key = client.post("/v1/mcp-servers/srv/connect", json={"method": "api_key"})
    assert missing_key.status_code == 400
    keyed = client.post("/v1/mcp-servers/srv/connect", json={"method": "api_key", "apiKey": "secret"})
    assert keyed.json()["toolCount"] == 1
    validated = client.post("/v1/mcp-servers/srv/validate")
    assert validated.json()["toolDetails"][0]["name"] == "search"

    def missing(*_args, **_kwargs):
        raise KeyError("gone")

    service.start_oauth_custom = missing
    assert client.post("/v1/mcp-servers/srv/connect", json={"method": "oauth"}).status_code == 404

    def bad(*_args, **_kwargs):
        raise ValueError("bad")

    service.connect_custom_api_key = bad
    assert client.post(
        "/v1/mcp-servers/srv/connect", json={"method": "api_key", "apiKey": "secret"}
    ).status_code == 400
    service.validate = missing
    assert client.post("/v1/mcp-servers/srv/validate").status_code == 404

    entry = SimpleNamespace(id="linear", name="Linear")
    server = SimpleNamespace(id="abc123", name="Linear", catalog_id="linear")
    store = SimpleNamespace(list_mcp_servers=lambda: [server])
    monkeypatch.setattr("agent.mcp_manage.resolve.get_catalog_entry", lambda key: entry if key == "linear" else None)
    found_entry, found_server = resolve_server_ref("linear", store)
    assert found_server is server
    by_id, _ = resolve_server_ref("abc", store)
    assert by_id is entry
    by_name, _ = resolve_server_ref("linear", store)
    assert by_name is entry
    assert resolve_server_ref("  ", store) == (None, None)
    assert resolve_server_ref("nope", store) == (None, None)


def test_compatible_chat_models_pass_api_keys(monkeypatch) -> None:
    captured: dict[str, dict] = {}

    class Model:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs

    for module in ("langchain_groq", "langchain_cerebras", "langchain_fireworks"):
        monkeypatch.setitem(
            __import__("sys").modules,
            module,
            SimpleNamespace(ChatGroq=Model, ChatCerebras=Model, ChatFireworks=Model),
        )
    monkeypatch.setattr(
        "agent.model_catalog.resolve_catalog_model_id",
        lambda model: model,
    )
    config = SimpleNamespace(
        get=lambda key: "",
        llm_api_key=lambda provider: "secret" if provider == "groq" else "",
    )
    build_groq_chat_model(config, temperature=0.2)
    assert captured["kwargs"]["api_key"] == "secret"
    config.llm_api_key = lambda provider: ""
    build_cerebras_chat_model(config, temperature=0)
    assert "api_key" not in captured["kwargs"]
    build_fireworks_chat_model(config, temperature=0.1)
    assert captured["kwargs"]["temperature"] == 0.1
