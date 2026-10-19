"""Coverage for dataset removal, PPI stats, MCP dispatch, and loop progress."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.loop.progress import LoopProgressMixin
from agent.mcp_manage.dispatch import handle_mcp_argv
from data.downloader.removal import remove_dataset
from tools.network_ppi_stats import (
    _compute_network_stats,
    _expand_depth2,
    _functional_enrichment,
)


class _Cfg:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = dict(values)
        self.unset_keys: list[str] = []
        self.saved = False

    def get(self, key: str):
        return self.values.get(key)

    def unset(self, key: str) -> None:
        self.unset_keys.append(key)
        self.values.pop(key, None)

    def save(self) -> None:
        self.saved = True


class _Console:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def print(self, *args, **_kwargs) -> None:
        self.lines.append(" ".join(str(arg) for arg in args))


class _Store:
    def __init__(self, *, boom: bool = False, session=None) -> None:
        self.boom = boom
        self.session = session
        self.events: list[tuple] = []
        self.usage: list[dict] = []

    def append_event(self, **kwargs):
        if self.boom:
            raise RuntimeError("store down")
        self.events.append(kwargs)
        return type("Stored", (), {"timestamp": "2026-10-19T00:00:00Z"})()

    def get_session(self, _session_id):
        return self.session

    def upsert_usage_run(self, **kwargs) -> None:
        self.usage.append(kwargs)


def test_remove_dataset_rejects_unknown_and_outside_base(monkeypatch, tmp_path: Path) -> None:
    cfg = _Cfg({"data.base": str(tmp_path)})
    monkeypatch.setattr("data.downloader.Config.load", lambda: cfg)

    with pytest.raises(KeyError):
        remove_dataset("not-a-dataset")

    calls = {"n": 0}
    real_resolve = Path.resolve

    def flipping_resolve(self: Path):
        calls["n"] += 1
        if calls["n"] == 2:
            return Path("/tmp/sandwalk-outside-dataset")
        return real_resolve(self)

    monkeypatch.setattr(Path, "resolve", flipping_resolve)
    with pytest.raises(ValueError, match="outside data base"):
        remove_dataset("depmap")


def test_remove_dataset_deletes_dir_file_and_custom_config(monkeypatch, tmp_path: Path) -> None:
    base = tmp_path / "data"
    base.mkdir()
    folder = base / "depmap"
    folder.mkdir()
    (folder / "a.csv").write_text("x", encoding="utf-8")
    cfg = _Cfg({"data.base": str(base), "data.depmap": str(folder)})
    monkeypatch.setattr("data.downloader.Config.load", lambda: cfg)
    monkeypatch.setattr(
        "data.downloader.list_dataset_records",
        lambda: [{"id": "depmap", "status": "ready"}],
    )

    removed = remove_dataset("depmap")
    assert removed["removed"] is True
    assert removed["status"] == "ready"
    assert cfg.saved is True
    assert "data.depmap" in cfg.unset_keys
    assert not folder.exists()

    lone = base / "prism"
    lone.write_text("file", encoding="utf-8")
    cfg2 = _Cfg({"data.base": str(base)})
    monkeypatch.setattr("data.downloader.Config.load", lambda: cfg2)
    monkeypatch.setattr("data.downloader.list_dataset_records", lambda: [])
    gone = remove_dataset("prism")
    assert gone["removed"] is True
    assert gone["status"] == "missing"
    assert gone["id"] == "prism"
    assert not lone.exists()


def test_expand_depth2_skips_empty_and_errors(monkeypatch) -> None:
    assert _expand_depth2("https://string", 400, {"TP53"}, ["TP53"], []) == []

    def boom(*_args, **_kwargs):
        return None, "down"

    monkeypatch.setattr("tools.network_ppi_stats.request_json", boom)
    edges = [{"gene_a": "TP53", "gene_b": "MDM2", "score": 0.9}]
    assert _expand_depth2("https://string", 400, {"TP53", "MDM2"}, ["TP53"], edges) == []


def test_expand_depth2_adds_new_partners(monkeypatch) -> None:
    def ok(*_args, **_kwargs):
        return [
            {"preferredName_A": "MDM2", "preferredName_B": "TP53", "score": 0.2},
            {"preferredName_A": "MDM2", "preferredName_B": "CDKN1A", "score": 0.8},
        ], None

    monkeypatch.setattr("tools.network_ppi_stats.request_json", ok)
    nodes = {"TP53", "MDM2"}
    edges = [{"gene_a": "TP53", "gene_b": "MDM2", "score": 0.9}]
    added = _expand_depth2("https://string", 400, nodes, ["TP53"], edges)
    assert added == [{"gene_a": "MDM2", "gene_b": "CDKN1A", "score": 0.8}]
    assert "CDKN1A" in nodes


def test_network_stats_counts_hubs_and_triangles() -> None:
    edges = [
        {"gene_a": "A", "gene_b": "B", "score": 1},
        {"gene_a": "B", "gene_b": "C", "score": 1},
        {"gene_a": "A", "gene_b": "C", "score": 1},
    ]
    stats, clustering = _compute_network_stats({"A", "B", "C", "D"}, edges, [])
    assert stats["node_count"] == 4
    assert stats["edge_count"] == 3
    assert stats["hub_genes"][0]["degree"] == 2
    assert clustering > 0
    lonely, _ = _compute_network_stats({"Z"}, [], [])
    assert lonely["avg_degree"] == 0
    assert lonely["clustering_coefficient"] == 0


def test_functional_enrichment_sorts_and_handles_errors(monkeypatch) -> None:
    assert _functional_enrichment("https://string", ["TP53"]) == []

    def boom(*_args, **_kwargs):
        return None, "nope"

    monkeypatch.setattr("tools.network_ppi_stats.request_json", boom)
    assert _functional_enrichment("https://string", ["TP53", "MDM2"]) == []

    def ok(*_args, **_kwargs):
        return [
            {"category": "Process", "term": "late", "description": "b", "fdr": 0.2, "p_value": 0.3, "number_of_genes": 2, "preferredNames": "TP53"},
            {"category": "Process", "term": "early", "description": "a", "fdr": 0.01, "p_value": 0.02, "number_of_genes": 4, "preferredNames": "TP53,MDM2"},
        ], None

    monkeypatch.setattr("tools.network_ppi_stats.request_json", ok)
    rows = _functional_enrichment("https://string", ["TP53", "MDM2"])
    assert [row["term"] for row in rows] == ["early", "late"]
    assert rows[0]["gene_count"] == 4


def test_mcp_dispatch_routes_every_action(monkeypatch) -> None:
    console = _Console()
    seen: list[str] = []

    def record(name):
        def _handler(*_args, **_kwargs):
            seen.append(name)
            return 0

        return _handler

    monkeypatch.setattr("agent.mcp_manage.dispatch.print_mcp_status", lambda _console: seen.append("list"))
    monkeypatch.setattr("agent.mcp_manage.dispatch._store", lambda: object())
    monkeypatch.setattr("agent.mcp_manage.dispatch._service", lambda _store: object())
    for name, target in {
        "catalog": "handle_catalog",
        "install": "handle_install",
        "doctor": "handle_doctor",
        "connect": "handle_connect",
        "disconnect": "handle_disconnect",
        "enable": "handle_enable_disable",
        "validate": "handle_validate",
        "add": "handle_add",
        "remove": "handle_remove",
    }.items():
        monkeypatch.setattr(f"agent.mcp_manage.dispatch.{target}", record(name))

    assert handle_mcp_argv([], console) == 0
    assert handle_mcp_argv(["status"], console) == 0
    assert handle_mcp_argv(["catalog"], console) == 0
    assert handle_mcp_argv(["install", "pymol"], console) == 0
    assert handle_mcp_argv(["doctor"], console) == 0
    assert handle_mcp_argv(["connect", "exa"], console) == 0
    assert handle_mcp_argv(["disconnect", "exa"], console) == 0
    assert handle_mcp_argv(["disable", "exa"], console) == 0
    assert handle_mcp_argv(["tools", "exa"], console) == 0
    assert handle_mcp_argv(["add", "local"], console) == 0
    assert handle_mcp_argv(["rm", "local"], console) == 0
    assert handle_mcp_argv(["help"], console) == 0
    assert "mcp" in console.lines[0]
    assert handle_mcp_argv(["nope"], console) == 2
    assert any("Unknown mcp action" in line for line in console.lines)
    assert seen[0] == "list"


def test_loop_progress_forwards_callbacks_and_store_events(monkeypatch) -> None:
    mixin = LoopProgressMixin()
    mixin.store = _Store()
    seen: list[tuple] = []

    def modern(event, **payload):
        seen.append((event, payload))

    mixin._emit_store_progress(
        session_id="s",
        run_id="r",
        event="mystery",
        progress_callback=modern,
        text="hi",
    )
    assert seen == [("mystery", {"text": "hi"})]
    assert mixin.store.events == []

    def legacy(text):
        seen.append(("legacy", text))

    mixin._emit_store_progress(
        session_id="s",
        run_id="r",
        event="activity",
        progress_callback=legacy,
        text="working",
    )
    assert ("legacy", "working") in seen
    assert mixin.store.events[-1]["event_type"] == "run.progress"

    def broken(_event, **_payload):
        raise RuntimeError("callback")

    mixin._emit_store_progress(
        session_id="s",
        run_id="r",
        event="stream",
        progress_callback=broken,
        delta="tok",
    )
    assert mixin.store.events[-1]["payload"]["delta"] == "tok"

    mixin._emit_store_progress(
        session_id="s",
        run_id="r",
        event="tool_end",
        name="read",
        output="ok",
        is_error=False,
        duration_s=1.5,
        tool_call_id="c1",
    )
    assert mixin.store.events[-1]["event_type"] == "tool.completed"

    tokens = {
        "input_tokens": 3,
        "output_tokens": 4,
        "cache_read_tokens": 1,
        "cache_creation_tokens": 0,
    }
    monkeypatch.setattr("agent_server.usage_service.parse.parse_usage_tokens", lambda _payload: tokens)
    monkeypatch.setattr("agent_server.usage_service.parse.active_model_id", lambda: "gpt")
    monkeypatch.setattr("agent_server.usage_service.parse.active_provider", lambda: "openai")
    monkeypatch.setattr("agent_server.usage_service.parse.day_key_from_timestamp", lambda _ts: "2026-10-19")
    monkeypatch.setattr("agent_server.usage_service.parse.surface_for_session", lambda _session: "cli")
    mixin._emit_store_progress(session_id="s", run_id="r", event="usage", input_tokens=3)
    assert mixin.store.usage[-1]["model_id"] == "gpt"
    assert mixin.store.usage[-1]["provider"] == "openai"

    monkeypatch.setattr("agent_server.usage_service.parse.active_model_id", lambda: None)
    monkeypatch.setattr("agent_server.usage_service.parse.active_provider", lambda: None)
    mixin._emit_store_progress(session_id="s", run_id="r", event="usage")
    assert "modelId" not in mixin.store.events[-1]["payload"]

    monkeypatch.setattr(
        "agent_server.service.plan_events.plan_created_payload_from_tool_call",
        lambda **_kwargs: {"path": "plans/a.md", "title": "A", "summary": ""},
    )
    mixin._emit_store_progress(
        session_id="s",
        run_id="r",
        event="tool_start",
        name="write_file",
        arguments={"path": "plans/a.md"},
        tool_call_id="c2",
    )
    assert mixin.store.events[-1]["event_type"] == "plan.created"

    mixin.store = _Store(boom=True)
    mixin._emit_store_progress(session_id="s", run_id="r", event="activity", text="still ok")
