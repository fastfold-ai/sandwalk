"""Resolve bench cells from a fake sandwalk_bench package."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace

from agent_server.bench_service import spawn_core as spawn


@dataclass
class _Cell:
    question_id: str
    model_key: str = ""
    model_id: str = ""
    provider: str = ""
    title: str = ""
    prompt: str = ""
    question: object = None


def _install_bench(monkeypatch, tmp_path):
    pkg = ModuleType("sandwalk_bench")
    pkg.__path__ = []
    bix = ModuleType("sandwalk_bench.bixbench")
    pack_mod = ModuleType("sandwalk_bench.pack")
    paths = ModuleType("sandwalk_bench.paths")
    schema = ModuleType("sandwalk_bench.schema")
    spawn_mod = ModuleType("sandwalk_bench.spawn")
    packs = tmp_path / "packs"
    packs.mkdir()
    paths.PACKS_DIR = packs
    schema.MatrixCell = _Cell
    spawn_mod.copy_cell_inputs = lambda *args: None
    jsonl = tmp_path / "bix.jsonl"
    bix.jsonl_path = lambda: jsonl
    question = SimpleNamespace(id="q1", title="Fold", question="What is it?")
    bix_pack = SimpleNamespace(questions=[question, question], id="bixbench-verified-50")
    bix.as_is_pack = lambda rows: bix_pack
    bix.load_jsonl = lambda: [{"id": "q1"}]
    yaml_pack = SimpleNamespace(
        id="bio",
        questions=[],
        matrices={"default": {}, "extra": {}},
    )

    def load_pack(path):
        if "bad" in path.name:
            raise RuntimeError("bad pack")
        return yaml_pack

    good = packs / "bio.yaml"
    good.write_text("pack: bio\n")
    pack_mod.list_packs = lambda: [packs / "bad.yaml", good]
    pack_mod.load_pack = load_pack
    pack_mod.expand_matrix = lambda pack, matrix: [
        _Cell(question_id="q", provider="openrouter"),
        _Cell(question_id="q", provider="openai"),
        _Cell(question_id="q2", provider="openai"),
    ]
    for module in (pkg, bix, pack_mod, paths, schema, spawn_mod):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(
        "agent_server.bench_service.pack_requirements.partition_cells_by_requirements",
        lambda cells, store=None: (cells[:2], [{"cell": cells[0], "reason": "missing"}]),
    )
    monkeypatch.setattr(
        "agent_server.bench_service.catalog.pack_matches_id",
        lambda loaded, pack_id: True,
    )
    monkeypatch.setattr(
        "agent_server.bench_service.catalog.pack_display_title",
        lambda pack_id: "Bio Capybara",
    )
    monkeypatch.setattr(
        "agent_server.bench_service.catalog._preferred_matrix",
        lambda pack: (None, None),
    )
    return jsonl, yaml_pack


def test_resolve_bix_and_yaml_cells(tmp_path, monkeypatch):
    jsonl, _pack = _install_bench(monkeypatch, tmp_path)
    with __import__("pytest").raises(FileNotFoundError):
        spawn._resolve_cells(
            pack_id="bixbench-verified-50",
            matrix=None,
            suite_id="bixbench-verified-50",
            sample_size=None,
            model_id="",
            provider=None,
        )
    jsonl.write_text("{}\n")
    cells, pack, suite_id, skipped = spawn._resolve_cells(
        pack_id="other",
        matrix=None,
        suite_id="bixbench-verified-50",
        sample_size=1,
        model_id="",
        provider=None,
    )
    assert suite_id == "bixbench-verified-50"
    assert len(cells) == 1
    assert skipped == []
    assert pack.questions

    resolved, _pack, title, skipped = spawn._resolve_cells(
        pack_id="bio-capybara",
        matrix=None,
        suite_id="bio:skills",
        sample_size=1,
        model_id="openai/gpt-test",
        provider=None,
        store=object(),
    )
    assert title == "Bio Capybara"
    assert len(resolved) == 1
    assert resolved[0].model_id == "openai/gpt-test"
    assert resolved[0].provider == "openrouter"
    assert skipped

    row = spawn._skipped_question_row(
        {"cell": resolved[0], "reason": "no skill", "missing_skills": ["fold"]},
        index=0,
    )
    assert row["skipped"] is True
    assert row["missing_skills"] == ["fold"]
