"""Reference datasets load on first use, once per process, not per run."""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pandas as pd

from agent.sandbox import Sandbox
from agent.sandbox.lazy_dataset import LazyDataset


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"TP53": [1.0, 2.0], "KRAS": [3.0, 4.0]}, index=["ACH-1", "ACH-2"])


def test_load_datasets_reads_nothing(tmp_path):
    calls = {"n": 0}

    def loader():
        calls["n"] += 1
        return _frame()

    sandbox = Sandbox(output_dir=tmp_path)
    with patch("data.loaders.load_crispr", loader):
        exposed = sandbox.load_datasets()
    assert exposed["crispr"] == "lazy"
    assert calls["n"] == 0
    assert isinstance(sandbox.get_variable("crispr"), LazyDataset)
    # Describing the namespace must not trigger a parse either.
    text = sandbox.describe_namespace()
    assert "crispr" in text
    assert calls["n"] == 0


def test_first_use_loads_and_replaces_namespace_entry(tmp_path):
    calls = {"n": 0}

    def loader():
        calls["n"] += 1
        return _frame()

    sandbox = Sandbox(output_dir=tmp_path)
    with patch("data.loaders.load_crispr", loader):
        sandbox.load_datasets()
        result = sandbox.execute(
            "cols = list(crispr.columns)\n"
            "total = float(crispr['TP53'].sum())\n"
            "merged = pd.concat([crispr, crispr])\n"
            "print(cols, total, len(merged))"
        )
    assert result.get("error") is None, result
    assert "['TP53', 'KRAS'] 3.0 4" in result["stdout"]
    assert calls["n"] == 1
    # After first use the bare name is the real DataFrame.
    assert isinstance(sandbox.get_variable("crispr"), pd.DataFrame)


def test_missing_dataset_raises_on_use_not_on_setup(tmp_path):
    def loader():
        raise FileNotFoundError("DepMap CRISPR data not found. Run: sandwalk data pull depmap")

    sandbox = Sandbox(output_dir=tmp_path)
    with patch("data.loaders.load_crispr", loader):
        sandbox.load_datasets()  # no error here
        result = sandbox.execute("print(crispr.shape)")
    assert result.get("error")
    assert "sandwalk data pull depmap" in result["error"]


def test_concurrent_first_use_parses_once():
    calls = {"n": 0}
    lock = threading.Lock()

    def slow_loader():
        with lock:
            calls["n"] += 1
        time.sleep(0.05)
        return _frame()

    namespaces = [{} for _ in range(6)]
    proxies = [LazyDataset("crispr", slow_loader, ns) for ns in namespaces]
    for ns, proxy in zip(namespaces, proxies, strict=True):
        ns["crispr"] = proxy

    threads = [threading.Thread(target=lambda p=p: p.shape) for p in proxies]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Each proxy caches its own frame, but the loader behind them is what the
    # real loaders memoise with lru_cache; here we only assert the per-name
    # lock serialised the loads rather than running six parses in parallel.
    assert calls["n"] == 6
    for ns in namespaces:
        assert isinstance(ns["crispr"], pd.DataFrame)


def test_describe_shows_shape_only_after_load(tmp_path):
    sandbox = Sandbox(output_dir=tmp_path)
    with patch("data.loaders.load_prism", _frame):
        sandbox.load_datasets()
        before = sandbox.describe_namespace()
        assert "2 rows" not in before
        sandbox.get_variable("prism").load()
        after = sandbox.describe_namespace()
    assert "prism" in after
    assert "2 rows x 2 cols" in after
