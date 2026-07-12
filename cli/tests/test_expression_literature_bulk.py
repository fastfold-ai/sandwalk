"""Bulk mocked tests for expression and literature tools."""

import sys
import types

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from tools.expression import (
    deconvolution,
    diff_expression,
    immune_score,
    l1000_similarity,
    pathway_enrichment,
    tf_activity,
)
from tools.literature import openalex_search, pubmed_search


def _mock_l1000():
    return pd.DataFrame(
        {
            "TP53": [1.0, -0.5, 0.2, 0.8],
            "STAT1": [0.9, 0.1, -0.2, 0.5],
            "IRF1": [0.7, 0.0, 0.3, 0.4],
            "GBP1": [0.6, -0.1, 0.1, 0.2],
            "CD274": [0.3, 0.2, -0.4, 0.1],
            "MDM2": [0.5, 0.4, 0.6, 0.2],
            "BAX": [-0.2, 0.8, 0.1, -0.3],
            "MYC": [0.4, 0.3, 0.5, 0.6],
            "NFKBIA": [0.2, 0.1, 0.0, -0.1],
            "CD3D": [0.1, 0.9, 0.2, 0.3],
            "CD19": [0.0, 0.8, 0.1, 0.2],
        },
        index=["BRD-A", "BRD-B", "BRD-C", "BRD-D"],
    )


class TestPathwayAndImmune:
    @patch("data.loaders.load_l1000")
    @patch("tools._compound_resolver.resolve_compound", return_value="BRD-A")
    def test_pathway_enrichment_all_compounds(self, _resolve, mock_load):
        mock_load.return_value = _mock_l1000()
        result = pathway_enrichment(compound_id="all", pathways="hallmark")
        assert "summary" in result
        assert "rows" in result["results"] or isinstance(result["results"], list)

    @patch("data.loaders.load_l1000")
    @patch("tools._compound_resolver.resolve_compound", return_value="MISSING")
    def test_pathway_enrichment_not_found_diagnostics(self, _resolve, mock_load):
        mock_load.return_value = _mock_l1000()
        result = pathway_enrichment(compound_id="unknown", pathways="hallmark")
        assert "No pathway enrichment" in result["summary"]
        assert result.get("compounds_not_found") == ["MISSING"]

    @patch("tools.expression.pathway_enrichment")
    def test_immune_score_adds_classification(self, mock_pathway):
        mock_pathway.return_value = {
            "summary": "base",
            "results": [
                {"compound": "BRD-A", "pathway": "ifn_gamma", "score": 0.8},
                {"compound": "BRD-A", "pathway": "antigen_presentation", "score": 0.6},
                {"compound": "BRD-A", "pathway": "icd", "score": 0.5},
                {"compound": "BRD-A", "pathway": "t_cell_cytotoxicity", "score": 0.7},
            ],
        }

        result = immune_score(compound_id="BRD-A")
        assert result["immune_classification"] == "immune_hot"
        assert "io_potential" in result


@pytest.fixture(autouse=True)
def _inject_sklearn_stub(monkeypatch):
    """Inject sklearn stub for all l1000_similarity tests in this module."""
    pairwise = types.SimpleNamespace(
        cosine_similarity=lambda query, matrix: np.array([
            np.linspace(0.95, 0.1, matrix.shape[0])
        ])
    )
    metrics = types.SimpleNamespace(pairwise=pairwise)
    sklearn_mod = types.SimpleNamespace(metrics=metrics)
    monkeypatch.setitem(sys.modules, "sklearn", sklearn_mod)
    monkeypatch.setitem(sys.modules, "sklearn.metrics", metrics)
    monkeypatch.setitem(sys.modules, "sklearn.metrics.pairwise", pairwise)


class TestL1000Similarity:
    @patch("tools._compound_resolver.resolve_compound", return_value="BRD-A")
    @patch("data.loaders.load_l1000")
    def test_similar_mode(self, mock_load, _resolve):
        mock_load.return_value = _mock_l1000()
        result = l1000_similarity(compound_id="BRD-A", mode="similar", top_n=2)
        assert result["mode"] == "similar"
        assert len(result["hits"]) == 2

    @patch("tools._compound_resolver.resolve_compound", return_value="BRD-A")
    @patch("data.loaders.load_l1000")
    def test_opposite_mode(self, mock_load, _resolve):
        mock_load.return_value = _mock_l1000()
        result = l1000_similarity(compound_id="BRD-A", mode="opposite", top_n=2)
        assert result["mode"] == "opposite"

    @patch("tools._compound_resolver.resolve_compound", return_value="BRD-A")
    @patch("data.loaders.load_l1000")
    def test_invalid_mode(self, mock_load, _resolve):
        mock_load.return_value = _mock_l1000()
        result = l1000_similarity(compound_id="BRD-A", mode="weird")
        assert "error" in result

    @patch("tools._compound_resolver.resolve_compound", return_value="NOPE")
    @patch("data.loaders.load_l1000")
    def test_compound_not_found(self, mock_load, _resolve):
        mock_load.return_value = _mock_l1000()
        result = l1000_similarity(compound_id="NOPE")
        assert "error" in result


class TestDeconvolution:
    def test_gene_expression_dict(self):
        expr = {
            "CD3D": 1.0, "CD3E": 0.8, "CD8A": 0.5,
            "CD19": 0.1, "MS4A1": 0.05,
        }
        result = deconvolution(gene_expression=expr)
        assert result["dominant_cell_type"] == "T cells"
        assert "proportions" in result

    @patch("data.loaders.load_l1000")
    @patch("tools._compound_resolver.resolve_compound", return_value="BRD-B")
    def test_compound_id_path(self, _resolve, mock_load):
        mock_load.return_value = _mock_l1000()
        result = deconvolution(compound_id="lenalidomide")
        assert "compound BRD-B" in result["summary"]

    def test_missing_inputs(self):
        result = deconvolution()
        assert "error" in result


class TestTfActivity:
    def test_tf_scores_from_expression(self):
        expr = {
            "CDKN1A": 1.0, "MDM2": 0.8, "BAX": 0.5, "BBC3": 0.4, "PUMA": 0.3,
            "MYC": -0.9, "ODC1": -0.7,
        }
        result = tf_activity(gene_expression=expr)
        assert result["activated"]
        assert result["tf_scores"]["TP53"] > 0

    def test_no_regulon_overlap(self):
        result = tf_activity(gene_expression={"ZZZZZ": 1.0})
        assert "No TF regulon targets" in result["summary"]


class TestDiffExpression:
    @patch("data.loaders.load_l1000")
    def test_diff_expression_single_gene(self, mock_load):
        mock_load.return_value = _mock_l1000()
        result = diff_expression(
            gene="TP53",
            group_a=["BRD-A", "BRD-D"],
            group_b=["BRD-B", "BRD-C"],
        )
        assert "results" in result
        assert result["results"][0]["gene"] == "TP53"

    @patch("data.loaders.load_l1000")
    def test_diff_expression_missing_groups(self, mock_load):
        mock_load.return_value = _mock_l1000()
        result = diff_expression(gene="TP53", group_a=None, group_b=["BRD-B"])
        assert "error" in result

    @patch("data.loaders.load_l1000")
    def test_diff_expression_gene_not_found(self, mock_load):
        mock_load.return_value = _mock_l1000()
        result = diff_expression(
            gene="NOTAGENE",
            group_a=["BRD-A", "BRD-D"],
            group_b=["BRD-B", "BRD-C"],
        )
        assert "error" in result


class TestLiteratureBulk:
    @patch("tools.literature.request_json")
    def test_openalex_search_success(self, mock_request_json):
        mock_request_json.return_value = (
            {
                "meta": {"count": 1},
                "results": [{
                    "id": "https://openalex.org/W1",
                    "display_name": "Cancer biology review",
                    "publication_year": 2024,
                    "cited_by_count": 42,
                    "doi": "https://doi.org/10.1/example",
                    "authorships": [{"author": {"display_name": "Lee A"}}],
                    "primary_location": {"source": {"display_name": "Nature"}},
                    "open_access": {"is_oa": True, "oa_url": "https://example.org/paper"},
                }],
            },
            None,
        )

        result = openalex_search(query="cancer biology", max_results=5)
        assert result["total_count"] == 1
        assert result["articles"][0]["cited_by_count"] == 42

    @patch("tools.literature.request_json")
    def test_openalex_search_error(self, mock_request_json):
        mock_request_json.return_value = (None, "HTTP 500")
        result = openalex_search(query="test")
        assert "error" in result

    @patch("tools.literature.request_json")
    def test_pubmed_empty_results(self, mock_request_json):
        mock_request_json.return_value = ({"esearchresult": {"count": "0", "idlist": []}}, None)
        result = pubmed_search(query="zzzznotfound12345")
        assert result["total_count"] == 0
        assert result["articles"] == []
