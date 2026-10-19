"""Coverage for expression diff, live progress, PRISM build, and Modal filesystem I/O."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
from rich.console import Console

from agent.orchestrator.progress_display import make_progress_callback, render_progress_panel
from agent.sandbox_backend.filesystem_io import _patch_modal_filesystem_io
from data.downloader.prism_builder import _PRISM_FILES, _download_prism
from tools.expression_diff import _resolve_groups_by_lineage, diff_expression

_LFC_NAME, _TREAT_NAME, _CELL_NAME = (item[0] for item in _PRISM_FILES.values())


def _expression_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "UP": [5.0, 6.0, 5.5, 0.0, 0.2, 0.1],
            "DOWN": [0.0, 0.1, 0.2, 4.0, 5.0, 4.5],
            "SAME": [1.0, 2.0, 1.5, 1.0, 2.0, 1.5],
            "FLAT": [3.0, 3.0, 3.0, 3.0, 3.0, 3.0],
            "SHIFT": [5.0, 5.0, 5.0, 1.0, 1.0, 1.0],
            "SKIP": [float("nan"), float("nan"), float("nan"), 1.0, 1.0, 1.0],
        },
        index=["A1", "A2", "A3", "B1", "B2", "B3"],
    )


def _lineage_models() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "OncotreeLineage": [
                "Multiple Myeloma",
                "Multiple Myeloma",
                "Solid Tumor",
                "Solid Tumor",
                "Lung",
                "Lung",
            ],
            "ModelID": ["ACH-1", None, "ACH-3", "ACH-4", "NOT-IN-EXPR", None],
            "DepMap_ID": ["IGNORED", "ACH-2", None, None, None, None],
        }
    )


def _lineage_expression() -> pd.DataFrame:
    return pd.DataFrame(
        {"TP53": [5.0, 6.0, 0.0, 0.5], "MYC": [1.0, 1.2, 0.2, 0.4]},
        index=["ACH-1", "ACH-2", "ACH-3", "ACH-4"],
    )


def _panel_text(panel) -> str:
    console = Console(width=200, record=True)
    console.print(panel)
    return console.export_text()


class _ModalFS:
    def __init__(self) -> None:
        self.written: dict[str, bytes] = {}

    def write_bytes(self, content, path):
        if path == "/perm":
            raise PermissionError("denied")
        if path == "/missing":
            raise FileNotFoundError("absent")
        if path == "/boom":
            raise RuntimeError("disk full")
        self.written[path] = content

    def read_bytes(self, path):
        if path == "/mv":
            return memoryview(b"abc")
        if path == "/txt":
            return "hello"
        if path == "/bin":
            return b"raw"
        if path == "/missing":
            raise FileNotFoundError("gone")
        if path == "/boom":
            raise OSError("read failed")
        raise AssertionError(path)


def _prism_payloads() -> dict[str, str]:
    return {
        _LFC_NAME: (
            "row_id,broad_id,dose,LFC\n"
            "ACH-000001::P946.2::PR500B::REP300,BRD-1,10,1.5\n"
            "ACH-000002::X::Y::Z,BRD-1,10,-0.2\n"
            "ACH-000003::A::B::C,BRD-MISSING,5,0.1\n"
            "ACH-000001::dup::d::d,BRD-DUP,1,0.4\n"
        ),
        _TREAT_NAME: (
            "broad_id,name,extra\n"
            "BRD-1,imatinib,x\n"
            "BRD-DUP,dupname,x\n"
            "BRD-DUP,dupname-alt,y\n"
        ),
        _CELL_NAME: (
            "depmap_id,ccle_name,extra\n"
            "ACH-000001,CELL1,x\n"
            "ACH-000001,CELL1B,y\n"
            "ACH-000003,CELL3,z\n"
        ),
    }


def _write_prism_raw(raw: Path, payloads: dict[str, str] | None = None) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    for name, text in (payloads or _prism_payloads()).items():
        (raw / name).write_text(text)


def test_resolve_groups_by_lineage_maps_labels(monkeypatch):
    expr = _lineage_expression()
    monkeypatch.setattr(
        "data.loaders.load_depmap_model",
        lambda: _lineage_models(),
        raising=False,
    )
    matched_a, matched_b = _resolve_groups_by_lineage(
        ["myeloma"],
        ["solid_tumor_extra"],
        expr,
    )
    assert set(matched_a) == {"ACH-1", "ACH-2"}
    assert set(matched_b) == {"ACH-3", "ACH-4"}

    fallback = pd.DataFrame(
        {
            "disease": ["Myeloid", "Myeloid", "Lymphoid"],
            "StrippedCellLineName": ["ACH-1", "ACH-2", "ABSENT"],
        }
    )
    monkeypatch.setattr("data.loaders.load_depmap_model", lambda: fallback, raising=False)
    only_a, only_b = _resolve_groups_by_lineage(["myeloid"], ["lymphoid"], expr)
    assert only_a == []
    assert only_b == []


def test_resolve_groups_by_lineage_misses_and_errors(monkeypatch):
    expr = _lineage_expression()

    monkeypatch.setattr(
        "data.loaders.load_depmap_model",
        lambda: pd.DataFrame({"foo": [1, 2]}),
        raising=False,
    )
    assert _resolve_groups_by_lineage(["myeloma"], ["solid"], expr) == ([], [])

    monkeypatch.setattr(
        "data.loaders.load_depmap_model",
        lambda: pd.DataFrame(
            {"lineage": ["Myeloma", "Myeloma"], "ModelID": ["NOPE-1", "NOPE-2"]}
        ),
        raising=False,
    )
    assert _resolve_groups_by_lineage(["myeloma"], ["solid"], expr) == ([], [])

    monkeypatch.setattr(
        "data.loaders.load_depmap_model",
        lambda: pd.DataFrame(
            {
                "primary_disease": ["Myeloma", "Myeloma", "Carcinoma"],
                "ModelID": ["ACH-1", "ACH-2", "ACH-3"],
            }
        ),
        raising=False,
    )
    assert _resolve_groups_by_lineage(["myeloma"], ["unmatched"], expr) == ([], [])
    assert _resolve_groups_by_lineage(["no-such"], ["also-missing"], expr) == ([], [])

    def _boom():
        raise RuntimeError("depmap unavailable")

    monkeypatch.setattr("data.loaders.load_depmap_model", _boom, raising=False)
    assert _resolve_groups_by_lineage(["myeloma"], ["solid"], expr) == ([], [])

    monkeypatch.delattr("data.loaders.load_depmap_model", raising=False)
    assert _resolve_groups_by_lineage(["myeloma"], ["solid"], expr) == ([], [])


def test_diff_expression_rejects_empty_and_unknown_samples(monkeypatch):
    assert "must be provided" in diff_expression()["error"]
    assert "non-empty" in diff_expression(group_a=[], group_b=["A1"])["error"]

    class _TruthyThenEmpty:
        """Passes the first emptiness check, then looks empty after normalization."""

        def __init__(self) -> None:
            self.seen = 0

        def __bool__(self) -> bool:
            self.seen += 1
            return self.seen == 1

    monkeypatch.setattr("data.loaders.load_l1000", lambda: _expression_frame(), raising=False)
    emptied = diff_expression(group_a=_TruthyThenEmpty(), group_b=_TruthyThenEmpty())
    assert emptied == {"error": "Both group_a and group_b must be non-empty lists"}

    monkeypatch.delattr("data.loaders.load_depmap_model", raising=False)

    missing_a = diff_expression(gene="UP", group_a="A1", group_b=["B1", "B2"])
    assert "Group A" in missing_a["error"]
    assert "A1" in missing_a["error"]

    missing_b = diff_expression(
        gene="UP",
        group_a=["A1", "A2"],
        group_b=["missing-1", "missing-2"],
    )
    assert "Group B" in missing_b["error"]

    unknown = diff_expression(
        gene="NOPE",
        group_a=["A1", "A2"],
        group_b=["B1", "B2"],
        dataset="l1000",
    )
    assert "NOPE" in unknown["error"]
    assert "l1000" in unknown["error"]


def test_diff_expression_lineage_resolution_and_single_gene(monkeypatch):
    monkeypatch.setattr("data.loaders.load_l1000", lambda: _lineage_expression(), raising=False)
    monkeypatch.setattr(
        "data.loaders.load_depmap_model",
        lambda: _lineage_models(),
        raising=False,
    )
    result = diff_expression(
        gene="TP53",
        group_a="multiple myeloma",
        group_b="solid-tumor",
        note="ignored",
    )
    assert result["n_tested"] == 1
    assert result["group_a_size"] == 2
    assert result["group_b_size"] == 2
    row = result["results"][0]
    assert row["gene"] == "TP53"
    assert row["direction"] == "up_in_A"
    assert row["fdr"] == row["p_value"]
    assert "Cohen" in result["summary"]


def test_diff_expression_all_genes_effects_and_skipped_rows(monkeypatch):
    monkeypatch.setattr("data.loaders.load_l1000", lambda: _expression_frame(), raising=False)
    result = diff_expression(
        gene="all",
        group_a=["A1", "A2", "A3"],
        group_b=["B1", "B2", "B3"],
    )
    by_gene = {row["gene"]: row for row in result["results"]}
    assert set(by_gene) == {"UP", "DOWN", "SAME", "FLAT", "SHIFT"}
    assert by_gene["UP"]["direction"] == "up_in_A"
    assert by_gene["DOWN"]["direction"] == "up_in_B"
    assert by_gene["SAME"]["direction"] == "unchanged"
    assert by_gene["FLAT"]["cohens_d"] == 0.0
    assert by_gene["SHIFT"]["cohens_d"] == 0.0
    assert by_gene["UP"]["cohens_d"] != 0.0
    assert "fdr" in by_gene["UP"]
    assert result["n_tested"] == 5
    assert "genes tested" in result["summary"]


def test_diff_expression_no_testable_genes_and_mannwhitney_error(monkeypatch):
    empty = pd.DataFrame(
        {"SKIP": [float("nan"), float("nan"), 1.0, 1.0]},
        index=["A1", "A2", "B1", "B2"],
    )
    monkeypatch.setattr("data.loaders.load_l1000", lambda: empty, raising=False)
    result = diff_expression(gene="all", group_a=["A1", "A2"], group_b=["B1", "B2"])
    assert result["results"] == []
    assert "No testable genes" in result["summary"]

    calls = {"n": 0}

    def _mannwhitneyu(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("bad ranks")
        return 3.0, 0.25

    monkeypatch.setattr("data.loaders.load_l1000", lambda: _expression_frame(), raising=False)
    monkeypatch.setattr("scipy.stats.mannwhitneyu", _mannwhitneyu)
    partial = diff_expression(
        gene="all",
        group_a=["A1", "A2", "A3"],
        group_b=["B1", "B2", "B3"],
    )
    assert partial["n_tested"] == 4
    assert calls["n"] == 5


def test_progress_callback_records_events_until_terminal():
    lock = threading.Lock()
    statuses = {1: "running", 2: "completed", 3: "failed"}
    step_counts = {1: (0, 0), 2: (4, 0), 3: (1, 2)}
    details = {1: "queued", 2: "keep", 3: "keep"}
    callback_for = make_progress_callback(lock, statuses, step_counts, details)
    running = callback_for(1)

    running("planning_start")
    assert details[1] == "planning"
    running("planned", step_count=3)
    assert details[1] == "planned 3 step(s)"
    running("execution_start", iteration=2)
    assert "iteration 2" in details[1]
    running("step_running", step_id=7, tool="expression.diff_expression")
    assert "step 7 running" in details[1]
    running("step_completed", completed_steps=2, failed_steps=1, step_id=7, tool="search")
    assert step_counts[1] == (2, 1)
    running("step_completed")
    assert "step ? completed" in details[1]
    running("step_failed", step_id=8, tool="search")
    assert details[1].endswith("search")
    running("step_failed", step_id=9, tool="search", error="timeout", failed_steps=2)
    assert "timeout" in details[1]
    assert step_counts[1] == (2, 2)
    running("replan")
    assert details[1] == "replanning after observer feedback"
    running("replanned", step_count=1)
    assert details[1] == "replanned 1 step(s)"
    running("synthesis_start")
    running("synthesis_interrupted")
    assert details[1] == "synthesis interrupted"
    running("synthesis_end")
    assert details[1] == "thread synthesis complete"
    running("ignored-event")
    assert details[1] == "thread synthesis complete"

    callback_for(2)("planning_start")
    callback_for(3)("planned", step_count=9)
    assert details[2] == "keep"
    assert details[3] == "keep"


def test_render_progress_panel_statuses_and_evidence(monkeypatch):
    monkeypatch.setattr("agent.orchestrator.progress_display.time.time", lambda: 1000.0)
    goals = [
        SimpleNamespace(thread_id=1, angle="running-known-start"),
        SimpleNamespace(thread_id=2, angle="running-no-start"),
        SimpleNamespace(thread_id=3, angle="done"),
        SimpleNamespace(thread_id=4, angle="broken"),
        SimpleNamespace(thread_id=5, angle="waiting"),
    ]
    statuses = {
        1: "running",
        2: "running",
        3: "completed",
        4: "failed",
        5: "pending",
    }
    step_counts = {1: (2, 1), 2: (0, 0), 3: (3, 0), 4: (0, 1), 5: (0, 0)}
    details = {
        1: "planning",
        2: "queued",
        3: "thread complete",
        4: "error: boom",
        5: "queued",
    }
    start_times = {1: 990.0}
    durations = {3: 4.0, 4: 2.5}
    lock = threading.Lock()

    panel = render_progress_panel(
        goals,
        ["hit-a", "hit-b"],
        lock,
        statuses,
        step_counts,
        details,
        start_times,
        durations,
    )
    text = _panel_text(panel)
    assert panel.title == "Parallel Research"
    assert str(panel.border_style) == "cyan"
    assert "Thread 1: running-known-start" in text
    assert "[10.0s]" in text
    assert "Thread 2: running-no-start" in text
    assert "[0.0s]" in text
    assert "Thread 3: done" in text
    assert "[4.0s]" in text
    assert "Thread 4: broken (error: boom) [2.5s]" in text
    assert "Thread 5: waiting - queued" in text
    assert "Active threads: 2/5" in text
    assert "Evidence board: 2 entries" in text

    quiet = render_progress_panel(
        goals[:1],
        [],
        lock,
        statuses,
        step_counts,
        details,
        start_times,
        durations,
    )
    quiet_text = _panel_text(quiet)
    assert "Active threads: 1/1" in quiet_text
    assert "Evidence board" not in quiet_text


def test_download_prism_skips_existing_and_failed_fetch(tmp_path, monkeypatch):
    dest = tmp_path / "present"
    dest.mkdir()
    (dest / "prism_LFC_COLLAPSED.csv").write_text("pert_name,pert_dose,ccle_name,LFC\n")
    cfg = MagicMock()

    def _unexpected(*_args, **_kwargs):
        raise AssertionError("download should be skipped")

    monkeypatch.setattr("data.downloader._download_file", _unexpected)
    assert _download_prism(dest, cfg) is True
    cfg.set.assert_called_once_with("data.prism", str(dest))
    cfg.save.assert_called_once()

    failed = tmp_path / "failed"
    failed.mkdir()
    cfg_fail = MagicMock()

    def _reject(*_args, **_kwargs):
        return False

    monkeypatch.setattr("data.downloader._download_file", _reject)
    assert _download_prism(failed, cfg_fail) is False
    cfg_fail.save.assert_not_called()
    assert not (failed / "prism_LFC_COLLAPSED.csv").exists()

    partial = tmp_path / "partial"
    _write_prism_raw(partial / "_prism_raw", {_LFC_NAME: "not,used\n"})
    calls = []

    def _reject_next(url, target, fname):
        calls.append(fname)
        return False

    monkeypatch.setattr("data.downloader._download_file", _reject_next)
    assert _download_prism(partial, MagicMock()) is False
    assert calls == [_TREAT_NAME]


def test_download_prism_builds_table_and_cleans_raw_files(tmp_path, monkeypatch):
    payloads = _prism_payloads()

    def _fake_download(url, target, fname):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payloads[fname])
        return True

    monkeypatch.setattr("data.downloader._download_file", _fake_download)
    dest = tmp_path / "built"
    cfg = MagicMock()
    assert _download_prism(dest, cfg) is True
    final = dest / "prism_LFC_COLLAPSED.csv"
    built = pd.read_csv(final)
    assert list(built.columns) == ["pert_name", "pert_dose", "ccle_name", "LFC"]
    assert len(built) == 2
    assert set(built["pert_name"]) == {"imatinib", "dupname"}
    assert set(built["ccle_name"]) == {"CELL1"}
    assert not (dest / "_prism_raw").exists()
    cfg.set.assert_called_once_with("data.prism", str(dest))
    cfg.save.assert_called_once()

    leftover = tmp_path / "leftover"
    raw = leftover / "_prism_raw"
    _write_prism_raw(raw)
    (raw / "keep.txt").write_text("stay")
    monkeypatch.setattr(
        "data.downloader._download_file",
        lambda *_args, **_kwargs: True,
    )
    cfg_left = MagicMock()
    assert _download_prism(leftover, cfg_left) is True
    assert (leftover / "prism_LFC_COLLAPSED.csv").exists()
    assert (raw / "keep.txt").exists()
    assert not (raw / _LFC_NAME).exists()
    cfg_left.save.assert_called_once()


def test_download_prism_build_failure(tmp_path, monkeypatch):
    dest = tmp_path / "bad"
    _write_prism_raw(
        dest / "_prism_raw",
        dict.fromkeys((_LFC_NAME, _TREAT_NAME, _CELL_NAME), "a,b\n1,2\n"),
    )

    def _unexpected(*_args, **_kwargs):
        raise AssertionError("raw files already exist")

    monkeypatch.setattr("data.downloader._download_file", _unexpected)
    cfg = MagicMock()
    assert _download_prism(dest, cfg) is False
    assert not (dest / "prism_LFC_COLLAPSED.csv").exists()
    cfg.save.assert_not_called()


def test_patch_modal_filesystem_io_guards(monkeypatch):
    backend = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "deepagents.backends.protocol", None)
    _patch_modal_filesystem_io(backend, SimpleNamespace(filesystem=object()))
    assert not hasattr(backend, "upload_files")

    monkeypatch.undo()
    bare = SimpleNamespace()
    _patch_modal_filesystem_io(bare, SimpleNamespace(filesystem=None))
    assert not hasattr(bare, "upload_files")
    missing = SimpleNamespace()
    _patch_modal_filesystem_io(missing, SimpleNamespace())
    assert not hasattr(missing, "upload_files")


def test_patched_upload_and_download_cover_io_errors():
    filesystem = _ModalFS()
    backend = SimpleNamespace()
    _patch_modal_filesystem_io(backend, SimpleNamespace(filesystem=filesystem))

    uploaded = backend.upload_files(
        [
            ("relative", b"nope"),
            ("/ok", b"data"),
            ("/perm", b"p"),
            ("/missing", b"m"),
            ("/boom", b"b"),
        ]
    )
    assert [item.path for item in uploaded] == [
        "relative",
        "/ok",
        "/perm",
        "/missing",
        "/boom",
    ]
    assert [item.error for item in uploaded] == [
        "invalid_path",
        None,
        "permission_denied",
        "file_not_found",
        "disk full",
    ]
    assert filesystem.written["/ok"] == b"data"

    downloaded = backend.download_files(
        ["relative", "/mv", "/txt", "/bin", "/missing", "/boom"]
    )
    assert [item.error for item in downloaded] == [
        "invalid_path",
        None,
        None,
        None,
        "file_not_found",
        "read failed",
    ]
    assert downloaded[1].content == b"abc"
    assert downloaded[2].content == b"hello"
    assert downloaded[3].content == b"raw"
    assert downloaded[4].content is None


def test_patched_download_reports_unsupported_reads():
    backend = SimpleNamespace()
    filesystem = SimpleNamespace(write_bytes=lambda content, path: None, read_bytes=None)
    _patch_modal_filesystem_io(backend, SimpleNamespace(filesystem=filesystem))
    downloaded = backend.download_files(["relative", "/data"])
    assert [item.error for item in downloaded] == ["invalid_path", "read_unsupported"]
    assert downloaded[1].content is None
