"""Tests for tools.expression helper functions and mocked tool paths."""

import pandas as pd
import pytest
from unittest.mock import patch

from tools.expression import _get_default_gene_sets, pathway_enrichment


class TestGetDefaultGeneSets:
    def test_hallmark_collection(self):
        sets = _get_default_gene_sets("hallmark")
        assert isinstance(sets, dict)
        assert len(sets) > 0
        assert all(isinstance(genes, list) for genes in sets.values())

    def test_unknown_collection_returns_empty(self):
        sets = _get_default_gene_sets("nonexistent_collection_xyz")
        assert sets == {}


class TestPathwayEnrichment:
    @patch("tools._compound_resolver.resolve_compound", return_value="BRD-A123")
    @patch("data.loaders.load_l1000")
    def test_single_compound(self, mock_load, mock_resolve):
        mock_load.return_value = pd.DataFrame(
            {
                "TP53": [1.0, 2.0],
                "BRCA1": [0.5, -0.5],
                "MYC": [0.2, 0.3],
            },
            index=["BRD-A123", "BRD-B456"],
        )
        result = pathway_enrichment(compound_id="lenalidomide", pathways="hallmark")
        assert "error" not in result
        assert "summary" in result

    @patch("data.loaders.load_l1000")
    def test_compound_not_found(self, mock_load):
        mock_load.return_value = pd.DataFrame({"TP53": [1.0]}, index=["OTHER"])
        with patch("tools._compound_resolver.resolve_compound", return_value="MISSING"):
            result = pathway_enrichment(compound_id="unknown", pathways="hallmark")
        assert "summary" in result
