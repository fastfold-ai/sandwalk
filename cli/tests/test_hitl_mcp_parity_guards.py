"""Coverage for HITL decisions, MCP catalog routes, bio lookups, and sandbox guards."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.hitl.decisions import (
    build_approve,
    build_edit,
    build_reject,
    build_respond,
    extract_interrupt_payload,
    validate_decisions,
)
from agent.sandbox.guards import (
    _session_workspace_roots,
    make_safe_import,
    make_safe_open,
    make_safe_subprocess,
)
from agent_server.routes.mcp_catalog import register_mcp_catalog_routes
from tools.parity import (
    mychem_lookup,
    mydisease_lookup,
    mygene_lookup,
    mytaxon_lookup,
    myvariant_lookup,
)


def test_hitl_decisions_cover_each_type_and_interrupt_shapes() -> None:
    assert build_approve(scope=" all ")["scope"] == "remaining"
    assert "message" not in build_approve(scope="once")
    assert "explicitly asks" in build_reject("  ")["message"]
    assert build_reject("no")["message"] == "no"
    assert build_respond("   ")["message"] == "(no message)"
    edited = build_edit(name="read", args={"path": "a"})
    assert edited["edited_action"]["args"] == {"path": "a"}

    actions = [{"name": "read"}, {"name": "write"}]
    configs = [{"action_name": "write", "allowed_decisions": ["edit"]}]
    with pytest.raises(ValueError, match="Expected 2"):
        validate_decisions([{"type": "approve"}], action_requests=actions)
    with pytest.raises(ValueError, match="must be an object"):
        validate_decisions(["nope", {"type": "edit"}], action_requests=actions, review_configs=configs)
    with pytest.raises(ValueError, match="not allowed"):
        validate_decisions(
            [{"type": "approve"}, {"type": "approve"}],
            action_requests=actions,
            review_configs=configs,
        )
    with pytest.raises(ValueError, match="edited_action"):
        validate_decisions(
            [{"type": "approve"}, {"type": "edit"}],
            action_requests=actions,
            review_configs=configs,
        )
    with pytest.raises(ValueError, match="edited_action.name"):
        validate_decisions(
            [{"type": "approve"}, {"type": "edit", "edited_action": {"args": {}}}],
            action_requests=[{"name": "read"}, {"name": ""}],
            review_configs=configs,
        )
    with pytest.raises(ValueError, match="edited_action.args"):
        validate_decisions(
            [{"type": "approve"}, {"type": "edit", "edited_action": {"name": "write", "args": []}}],
            action_requests=actions,
            review_configs=configs,
        )

    normalized = validate_decisions(
        [
            {"type": "approve", "scope": "run"},
            {"type": "edit", "edited_action": {"name": "write", "args": {"path": "b"}}},
        ],
        action_requests=actions,
        review_configs=configs,
    )
    assert normalized[0]["scope"] == "remaining"
    assert normalized[1]["edited_action"]["name"] == "write"

    rejected = validate_decisions(
        [{"type": "reject", "message": "stop"}, {"type": "respond", "message": "ok"}],
        action_requests=[{"name": "a"}, {"name": "b"}],
    )
    assert rejected[0]["type"] == "reject"
    assert rejected[1]["message"] == "ok"

    assert extract_interrupt_payload(object(), {}) is None

    class Agent:
        def get_state(self, _config):
            raise RuntimeError("paused")

    assert extract_interrupt_payload(Agent(), {}) is None

    class Empty:
        def get_state(self, _config):
            return SimpleNamespace(interrupts=[], tasks=[])

    assert extract_interrupt_payload(Empty(), {}) is None

    class FromTask:
        def get_state(self, _config):
            return SimpleNamespace(
                interrupts=[],
                tasks=[SimpleNamespace(interrupts=[SimpleNamespace(value="nope")])],
            )

    assert extract_interrupt_payload(FromTask(), {}) is None

    class Ready:
        def get_state(self, _config):
            return SimpleNamespace(
                interrupts=[
                    SimpleNamespace(
                        value={"action_requests": [{"name": "read"}], "review_configs": []}
                    )
                ]
            )

    payload = extract_interrupt_payload(Ready(), {})
    assert payload["action_requests"][0]["name"] == "read"


def _server(catalog_id: str):
    now = datetime.now(UTC)
    from agent_server.models import McpServer

    return McpServer(
        id=catalog_id,
        name=catalog_id,
        transport="stdio",
        command="pymol",
        created_at=now,
        updated_at=now,
    )


def test_mcp_catalog_routes(monkeypatch) -> None:
    service = SimpleNamespace(
        catalog_statuses=lambda: [
            {
                "id": "pymol",
                "name": "PyMOL",
                "description": "viewer",
                "transport": "stdio",
                "auth_mode": "none",
                "preferred_auth": "none",
            }
        ],
        reset_featured_defaults=lambda: {
            "installed": ["pymol"],
            "errors": [{"id": "exa", "error": "missing"}, "skip-me"],
        },
        install_featured=lambda catalog_id, force=False: {"server": _server(catalog_id)},
        validate=lambda catalog_id, _body: {
            "ok": True,
            "toolCount": 1,
            "message": "ready",
            "tools": ["fetch"],
            "toolDetails": [
                {"name": "fetch", "title": "Fetch", "description": "d", "inputSchema": {}},
                "skip",
            ],
        },
    )
    app = FastAPI()
    register_mcp_catalog_routes(app, SimpleNamespace(store=object(), mcp_service=service))
    monkeypatch.setattr("agent_server.routes.mcp_catalog.seed_catalog_defaults", lambda _store: None)
    client = TestClient(app)

    listed = client.get("/v1/mcp-servers/catalog")
    assert listed.status_code == 200
    assert listed.json()["data"][0]["id"] == "pymol"

    reset = client.post("/v1/mcp-servers/catalog/reset-defaults")
    assert reset.json()["installed"] == ["pymol"]
    assert reset.json()["errors"][0]["id"] == "exa"

    monkeypatch.setattr(
        "agent.mcp_catalog.get_catalog_entry",
        lambda _catalog_id: SimpleNamespace(transport="stdio", auth_mode="none"),
    )
    installed = client.post("/v1/mcp-servers/catalog/pymol/install")
    assert installed.status_code == 201

    monkeypatch.setattr(
        "agent.mcp_catalog.get_catalog_entry",
        lambda _catalog_id: SimpleNamespace(transport="http", auth_mode="api_key"),
    )
    monkeypatch.setattr(
        "agent_server.routes.mcp_catalog.install_catalog_server",
        lambda _store, catalog_id: _server(catalog_id),
    )
    monkeypatch.setattr(
        "agent_server.routes.mcp_catalog.enrich_mcp_server",
        lambda server: server,
    )
    remote = client.post("/v1/mcp-servers/catalog/exa/install")
    assert remote.status_code == 201

    def missing(_catalog_id):
        raise KeyError(_catalog_id)

    monkeypatch.setattr("agent.mcp_catalog.get_catalog_entry", missing)
    assert client.post("/v1/mcp-servers/catalog/nope/install").status_code == 404

    def broken(_catalog_id):
        raise RuntimeError("cannot install")

    monkeypatch.setattr("agent.mcp_catalog.get_catalog_entry", broken)
    assert client.post("/v1/mcp-servers/catalog/nope/install").status_code == 400

    validated = client.post("/v1/mcp-servers/catalog/pymol/validate")
    assert validated.json()["toolDetails"][0]["name"] == "fetch"

    def unknown(_catalog_id, _body):
        raise KeyError("missing")

    service.validate = unknown
    assert client.post("/v1/mcp-servers/catalog/missing/validate").status_code == 404


def test_bioentity_lookups_shape_hits_and_errors(monkeypatch) -> None:
    def fail(*_args, **_kwargs):
        return None, "down"

    monkeypatch.setattr("tools.parity.request_json", fail)
    assert mygene_lookup("  ")["error"] == "missing_query"
    assert mygene_lookup("TP53")["error"] == "api_error"
    assert mydisease_lookup("")["error"] == "missing_query"
    assert mydisease_lookup("cancer")["error"] == "api_error"
    assert myvariant_lookup("")["error"] == "missing_query"
    assert myvariant_lookup("rs1")["error"] == "api_error"
    assert mytaxon_lookup("")["error"] == "missing_query"
    assert mytaxon_lookup("human")["error"] == "api_error"
    assert mychem_lookup("")["error"] == "missing_query"
    assert mychem_lookup("aspirin")["error"] == "api_error"

    def ok(*_args, **_kwargs):
        return {
            "hits": [
                {
                    "symbol": "TP53",
                    "name": "tumor",
                    "ensembl": [{"gene": "ENSG1"}],
                    "_score": 1,
                    "disease_ontology": {"doid": "DOID:1", "name": "cancer"},
                    "dbsnp": {"rsid": "rs1"},
                    "clinvar": {"hgvs": "g>a", "clinsig": "pathogenic"},
                    "vcf": {"gene": "TP53", "position": 10},
                    "scientific_name": "Homo sapiens",
                    "chembl": {
                        "pref_name": "aspirin",
                        "molecule_chembl_id": "CHEMBL25",
                        "molecule_structures": {"canonical_smiles": "CC"},
                    },
                    "drugbank": {"id": "DB00945"},
                },
                {"ensembl": {"gene": "ENSG2"}, "name": None},
                {"ensembl": "not-a-record", "name": "bare"},
            ]
        }, None

    monkeypatch.setattr("tools.parity.request_json", ok)
    gene = mygene_lookup("TP53", species="human")
    assert gene["hits"][0]["ensembl_gene"] == "ENSG1"
    assert gene["hits"][1]["ensembl_gene"] == "ENSG2"
    disease = mydisease_lookup("cancer")
    assert disease["hits"][0]["doid"] == "DOID:1"
    variant = myvariant_lookup("rs1")
    assert variant["hits"][0]["rsid"] == "rs1"
    taxon = mytaxon_lookup("human")
    assert taxon["hits"][0]["scientific_name"] == "Homo sapiens"
    chem = mychem_lookup("aspirin")
    assert chem["hits"][0]["smiles"] == "CC"
    assert chem["hits"][0]["chembl_id"] == "CHEMBL25"


def test_sandbox_guards_block_imports_and_limit_files(tmp_path, monkeypatch) -> None:
    safe_import = make_safe_import(lambda name, *args, **kwargs: name)
    with pytest.raises(ImportError, match="blocked"):
        safe_import("subprocess.popen")
    assert safe_import("json") == "json"

    monkeypatch.setenv("SANDWALK_CONFIG_DIR", str(tmp_path / "missing-config"))
    monkeypatch.delenv("SANDWALK_SESSION_WORKSPACE", raising=False)
    assert _session_workspace_roots() == []

    config = tmp_path / "config"
    workspace = tmp_path / "workspace"
    config.mkdir()
    workspace.mkdir()
    monkeypatch.setenv("SANDWALK_CONFIG_DIR", str(config))
    monkeypatch.setenv("SANDWALK_SESSION_WORKSPACE", str(workspace))

    def boom(_root):
        raise RuntimeError("mount")

    monkeypatch.setattr("agent_server.project_folder.project_mount_target", boom)
    assert workspace in _session_workspace_roots()

    output = tmp_path / "out"
    output.mkdir()
    import builtins

    real_open = builtins.open

    def tracking_open(file, mode="r", *args, **kwargs):
        if isinstance(file, int):
            return SimpleNamespace(fd=file)
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", tracking_open)
    opener = make_safe_open(output, extra_read_dirs=[config])
    assert opener(0, "r").fd == 0
    monkeypatch.setattr("agent_server.file_access.full_file_access_enabled", lambda: False)
    with pytest.raises(PermissionError, match="reads are restricted"):
        opener("/etc/passwd", "r")

    allowed = output / "note.txt"
    with opener(allowed, "w") as handle:
        handle.write("ok")
    assert allowed.read_text(encoding="utf-8") == "ok"

    monkeypatch.setattr("agent_server.file_access.full_file_access_enabled", lambda: True)
    outside = tmp_path / "secret.txt"
    with opener(outside, "a") as handle:
        handle.write("x")
    assert outside.read_text(encoding="utf-8") == "x"

    runner = make_safe_subprocess()
    with pytest.raises(PermissionError, match="Empty command"):
        runner([])
    with pytest.raises(PermissionError, match="not in allowed"):
        runner(["rm", "-rf", "/"])

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(cmd=cmd, kwargs=kwargs)

    monkeypatch.setattr("subprocess.run", fake_run)
    result = runner(["/usr/bin/samtools", "view"], text=True)
    assert result.kwargs["text"] is True
    encoded = runner(["bwa"])
    assert encoded.kwargs["encoding"] == "utf-8"
