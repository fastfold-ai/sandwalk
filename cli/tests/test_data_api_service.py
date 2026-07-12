"""Data API tests that run without requiring /mnt2/bronze."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import gzip

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("duckdb")
from fastapi.testclient import TestClient

from api.engine import QueryEngine


@pytest.fixture
def client():
    with patch("api.app.engine") as mock_engine, patch("api.app.discover_datasets") as mock_discover:
        mock_engine.query_parquet = MagicMock(return_value=[])
        mock_discover.return_value = {
            "perturbatlas": {
                "description": "PerturbAtlas test",
                "format": "csv.gz",
                "n_files": 2,
                "total_size_mb": 0.1,
                "filterable": ["gene", "perturb_id"],
            }
        }
        from api.app import app

        yield TestClient(app), mock_engine


class TestApiRoutesNoRealData:
    def test_health_ok(self, client):
        test_client, _ = client
        resp = test_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert "perturbatlas" in resp.json()["datasets"]

    def test_schema_health_ok(self, client):
        test_client, _ = client
        with patch("api.app.validate_schema", return_value={"perturbatlas": {"status": "valid"}}):
            resp = test_client.get("/health/schema")
        assert resp.status_code == 200

    def test_schema_health_unhealthy(self, client):
        test_client, _ = client
        with patch("api.app.validate_schema", return_value={"perturbatlas": {"status": "invalid"}}):
            resp = test_client.get("/health/schema")
        assert resp.status_code == 503

    def test_datasets_list(self, client):
        test_client, _ = client
        resp = test_client.get("/datasets")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload[0]["name"] == "perturbatlas"
        assert "required_columns" in payload[0]

    def test_query_unknown_dataset_404(self, client):
        test_client, _ = client
        resp = test_client.post("/query", json={"dataset": "nope"})
        assert resp.status_code == 404

    def test_query_success(self, client):
        test_client, mock_engine = client
        mock_engine.query_parquet.return_value = [{"gene": "TP53", "log2FoldChange": 1.2}]
        resp = test_client.post("/query", json={"dataset": "perturbatlas", "gene": "TP53", "limit": 5})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_rows"] == 1
        assert body["data"][0]["gene"] == "TP53"

    def test_query_file_missing_503(self, client):
        test_client, mock_engine = client
        mock_engine.query_parquet.side_effect = FileNotFoundError("missing")
        resp = test_client.post("/query", json={"dataset": "perturbatlas"})
        assert resp.status_code == 503

    def test_query_bad_column_400(self, client):
        test_client, mock_engine = client
        mock_engine.query_parquet.side_effect = ValueError("bad column")
        resp = test_client.post("/query", json={"dataset": "perturbatlas"})
        assert resp.status_code == 400

    def test_gene_summary_happy_path(self, client):
        test_client, mock_engine = client
        mock_engine.query_parquet.return_value = [
            {"gene": "TP53", "log2FoldChange": -1.0, "padj": 0.01},
            {"gene": "TP53", "log2FoldChange": -0.5, "padj": 0.2},
        ]
        resp = test_client.get("/datasets/perturbatlas/gene/TP53")
        assert resp.status_code == 200
        assert resp.json()["n_perturbations"] == 2
        assert resp.json()["n_significant"] == 1

    def test_gene_summary_not_found(self, client):
        test_client, mock_engine = client
        mock_engine.query_parquet.return_value = []
        resp = test_client.get("/datasets/perturbatlas/gene/NOPE")
        assert resp.status_code == 404

    def test_compound_summary_uses_filterable_column(self, client):
        test_client, mock_engine = client
        mock_engine.query_parquet.return_value = [{"pert_name": "imatinib"}]
        with patch.dict(
            "api.app.DATASET_REGISTRY",
            {
                "perturbatlas": {
                    "path_pattern": "x/*.csv.gz",
                    "filterable": ["pert_name"],
                }
            },
            clear=True,
        ):
            resp = test_client.get("/datasets/perturbatlas/compound/imatinib")
        assert resp.status_code == 200


class TestQueryEngineLocalFiles:
    @pytest.fixture
    def local_data_root(self, tmp_path):
        root = tmp_path / "data"
        d = root / "perturbatlas" / "Homo sapiens" / "exp1"
        d.mkdir(parents=True, exist_ok=True)
        p = d / "degs.csv.gz"
        with gzip.open(p, "wt", encoding="utf-8") as f:
            f.write("gene,perturb_id,log2FoldChange,pvalue,padj\n")
            f.write("TP53,Perturb_1,-1.2,0.001,0.01\n")
            f.write("BRCA1,Perturb_2,0.8,0.02,0.1\n")
            f.write("TP53,Perturb_3,-0.7,0.03,0.2\n")
        return root

    def test_sample_columns(self, local_data_root):
        engine = QueryEngine(data_root=local_data_root)
        cols = engine.sample_columns("perturbatlas/Homo sapiens/*/degs.csv.gz")
        assert "gene" in cols
        assert "log2FoldChange" in cols

    def test_query_with_filters_and_limit(self, local_data_root):
        engine = QueryEngine(data_root=local_data_root)
        rows = engine.query_parquet(
            file_pattern="perturbatlas/Homo sapiens/*/degs.csv.gz",
            filters={"gene": "TP53"},
            limit=1,
        )
        assert len(rows) == 1
        assert rows[0]["gene"] == "TP53"

    def test_query_with_selected_columns(self, local_data_root):
        engine = QueryEngine(data_root=local_data_root)
        rows = engine.query_parquet(
            file_pattern="perturbatlas/Homo sapiens/*/degs.csv.gz",
            columns=["gene", "padj"],
            limit=2,
        )
        assert set(rows[0].keys()) == {"gene", "padj"}

    def test_count(self, local_data_root):
        engine = QueryEngine(data_root=local_data_root)
        n = engine.count("perturbatlas/Homo sapiens/*/degs.csv.gz", filters={"gene": "TP53"})
        assert n == 2

    def test_query_nonexistent_pattern_raises(self, local_data_root):
        engine = QueryEngine(data_root=local_data_root)
        with pytest.raises(FileNotFoundError):
            engine.query_parquet("missing/*.csv.gz", limit=1)
