"""Mocked unit tests for the FastAPI data query service."""

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("api.app.engine") as mock_engine:
        mock_engine.query_parquet = MagicMock(return_value=[])
        with patch("api.app.discover_datasets") as mock_discover:
            mock_discover.return_value = {
                "perturbatlas": {
                    "description": "PerturbAtlas test",
                    "format": "csv.gz",
                    "n_files": 2,
                    "total_size_mb": 10.0,
                    "filterable": ["gene", "perturb_id"],
                }
            }
            from api.app import app

            yield TestClient(app), mock_engine, mock_discover


class TestHealthEndpoints:
    def test_health_ok(self, client):
        test_client, _, _ = client
        resp = test_client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["n_datasets"] == 1
        assert "perturbatlas" in body["datasets"]

    def test_schema_health_ok(self, client):
        test_client, mock_engine, _ = client
        with patch("api.app.validate_schema") as mock_validate:
            mock_validate.return_value = {
                "perturbatlas": {"status": "valid"},
            }
            resp = test_client.get("/health/schema")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_schema_health_unhealthy(self, client):
        test_client, _, _ = client
        with patch("api.app.validate_schema") as mock_validate:
            mock_validate.return_value = {
                "perturbatlas": {"status": "invalid"},
            }
            resp = test_client.get("/health/schema")
        assert resp.status_code == 503
        assert resp.json()["status"] == "unhealthy"


class TestDatasetsEndpoint:
    def test_list_datasets(self, client):
        test_client, _, _ = client
        resp = test_client.get("/datasets")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "perturbatlas"
        assert data[0]["n_files"] == 2


class TestQueryEndpoint:
    def test_query_success(self, client):
        test_client, mock_engine, _ = client
        mock_engine.query_parquet.return_value = [
            {"gene": "TP53", "log2FoldChange": 1.2},
        ]
        resp = test_client.post(
            "/query",
            json={"dataset": "perturbatlas", "gene": "TP53", "limit": 10},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["dataset"] == "perturbatlas"
        assert body["total_rows"] == 1
        assert body["data"][0]["gene"] == "TP53"

    def test_query_unknown_dataset(self, client):
        test_client, _, _ = client
        resp = test_client.post("/query", json={"dataset": "nonexistent"})
        assert resp.status_code == 404

    def test_query_file_not_found(self, client):
        test_client, mock_engine, _ = client
        mock_engine.query_parquet.side_effect = FileNotFoundError("missing")
        resp = test_client.post("/query", json={"dataset": "perturbatlas"})
        assert resp.status_code == 503

    def test_query_value_error(self, client):
        test_client, mock_engine, _ = client
        mock_engine.query_parquet.side_effect = ValueError("bad filter")
        resp = test_client.post("/query", json={"dataset": "perturbatlas"})
        assert resp.status_code == 400

    def test_query_compound_filter_uses_filterable_column(self, client):
        test_client, mock_engine, _ = client
        with patch("api.app.DATASET_REGISTRY", {
            "chembl": {
                "path_pattern": "chembl/*.parquet",
                "filterable": ["molecule_chembl_id"],
            }
        }):
            resp = test_client.post(
                "/query",
                json={"dataset": "chembl", "compound": "CHEMBL25"},
            )
        assert resp.status_code == 200
        call_kwargs = mock_engine.query_parquet.call_args.kwargs
        assert call_kwargs["filters"]["molecule_chembl_id"] == "CHEMBL25"

    def test_query_compound_filter_falls_back_to_compound_column(self, client):
        test_client, mock_engine, _ = client
        with patch("api.app.DATASET_REGISTRY", {
            "custom": {
                "path_pattern": "custom/*.parquet",
                "filterable": ["gene"],
            }
        }):
            resp = test_client.post(
                "/query",
                json={"dataset": "custom", "compound": "cmpd-x"},
            )
        assert resp.status_code == 200
        call_kwargs = mock_engine.query_parquet.call_args.kwargs
        assert call_kwargs["filters"]["compound"] == "cmpd-x"


class TestGeneSummary:
    def test_gene_summary_success(self, client):
        test_client, mock_engine, _ = client
        mock_engine.query_parquet.return_value = [
            {"gene": "TP53", "log2FoldChange": 2.0, "padj": 0.01},
            {"gene": "TP53", "log2FoldChange": -1.0, "padj": 0.2},
        ]
        resp = test_client.get("/datasets/perturbatlas/gene/TP53")
        assert resp.status_code == 200
        body = resp.json()
        assert body["gene"] == "TP53"
        assert body["n_perturbations"] == 2
        assert body["n_significant"] == 1

    def test_gene_summary_not_found(self, client):
        test_client, mock_engine, _ = client
        mock_engine.query_parquet.return_value = []
        resp = test_client.get("/datasets/perturbatlas/gene/MISSING")
        assert resp.status_code == 404

    def test_gene_summary_unknown_dataset(self, client):
        test_client, _, _ = client
        resp = test_client.get("/datasets/unknown/gene/TP53")
        assert resp.status_code == 404

    def test_gene_summary_file_not_found(self, client):
        test_client, mock_engine, _ = client
        mock_engine.query_parquet.side_effect = FileNotFoundError("missing")
        resp = test_client.get("/datasets/perturbatlas/gene/TP53")
        assert resp.status_code == 503


class TestCompoundSummary:
    def test_compound_summary_unknown_dataset(self, client):
        test_client, _, _ = client
        resp = test_client.get("/datasets/unknown/compound/aspirin")
        assert resp.status_code == 404

    def test_compound_summary_success(self, client):
        test_client, mock_engine, _ = client
        mock_engine.query_parquet.return_value = [{"compound": "aspirin"}]
        resp = test_client.get("/datasets/perturbatlas/compound/aspirin")
        assert resp.status_code == 200
        assert resp.json()["n_records"] == 1

    def test_compound_summary_not_found(self, client):
        test_client, mock_engine, _ = client
        mock_engine.query_parquet.return_value = []
        resp = test_client.get("/datasets/perturbatlas/compound/missing")
        assert resp.status_code == 404

    def test_compound_summary_value_error(self, client):
        test_client, mock_engine, _ = client
        mock_engine.query_parquet.side_effect = ValueError("bad column")
        resp = test_client.get("/datasets/perturbatlas/compound/aspirin")
        assert resp.status_code == 400

    def test_compound_summary_file_not_found(self, client):
        test_client, mock_engine, _ = client
        mock_engine.query_parquet.side_effect = FileNotFoundError("missing")
        resp = test_client.get("/datasets/perturbatlas/compound/aspirin")
        assert resp.status_code == 503
