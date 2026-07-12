"""Unit tests for api.engine.QueryEngine."""

from pathlib import Path
from unittest.mock import MagicMock

import duckdb
import pandas as pd

from api.engine import QueryEngine


def test_query_parquet_builds_like_and_in_filters():
    engine = QueryEngine(data_root=Path("/tmp/data"))
    mock_result = MagicMock()
    mock_result.fetchdf.return_value = pd.DataFrame([{"gene": "TP53"}])
    engine.conn = MagicMock()
    engine.conn.execute.return_value = mock_result

    rows = engine.query_parquet(
        "dataset/sample.csv.gz",
        filters={"gene": "TP%", "lineage": ["A", "B"]},
        order_by="gene",
        limit=25,
    )

    assert rows == [{"gene": "TP53"}]
    query, params = engine.conn.execute.call_args.args
    assert "LIKE ?" in query
    assert '"lineage" IN (?, ?)' in query
    assert params == ["TP%", "A", "B"]


def test_query_parquet_wraps_duckdb_ioerror():
    engine = QueryEngine(data_root=Path("/tmp/data"))
    engine.conn = MagicMock()
    engine.conn.execute.side_effect = duckdb.IOException("missing")

    try:
        engine.query_parquet("dataset/*.parquet")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError as exc:
        assert "Data files not found" in str(exc)


def test_count_returns_zero_on_ioerror():
    engine = QueryEngine(data_root=Path("/tmp/data"))
    engine.conn = MagicMock()
    engine.conn.execute.side_effect = duckdb.IOException("missing")

    assert engine.count("dataset/*.parquet", filters={"gene": "TP53"}) == 0
