"""Unit tests for viability tools with mocked PRISM/DepMap data."""

from unittest.mock import patch

import pandas as pd
import pytest


def _prism_frame():
    rows = []
    for dose in [0.1, 1.0, 10.0]:
        for cell, lfc in [
            ("CELL_A", -0.8 if dose == 10.0 else -0.1),
            ("CELL_B", -0.9 if dose == 10.0 else -0.2),
            ("CELL_C", -0.85 if dose == 10.0 else -0.15),
            ("CELL_D", 0.1 if dose == 10.0 else 0.0),
        ]:
            rows.append(
                {
                    "pert_name": "cpd_A",
                    "pert_dose": dose,
                    "ccle_name": cell,
                    "LFC": lfc,
                }
            )
    return pd.DataFrame(rows)


def _model_metadata():
    return pd.DataFrame(
        {
            "CCLEName": ["CELL_A", "CELL_B", "CELL_C", "CELL_D"],
            "OncotreeLineage": ["Lung", "Lung", "Lung", "Breast"],
        }
    )


class TestViabilityDoseResponse:
    @patch("tools._compound_resolver.resolve_compound", side_effect=lambda x, **_: x)
    @patch("data.loaders.load_prism")
    def test_dose_response_summary(self, mock_prism, _mock_resolve):
        from tools.viability import dose_response

        mock_prism.return_value = _prism_frame()
        result = dose_response(compound_id="cpd_A", lfc_threshold=-0.5)

        assert "error" not in result
        assert result["compound"] == "cpd_A"
        assert result["n_cell_lines"] == 4
        assert len(result["dose_stats"]) == 3
        assert result["n_sensitive"] == 3
        assert result["ic50_um"] is not None
        assert "Dose-response" in result["summary"]

    @patch("tools._compound_resolver.resolve_compound", side_effect=lambda x, **_: x)
    @patch("data.loaders.load_prism")
    def test_compound_not_found(self, mock_prism, _mock_resolve):
        from tools.viability import dose_response

        mock_prism.return_value = _prism_frame()
        result = dose_response(compound_id="missing")

        assert "not found" in result["error"]

    @patch("tools._compound_resolver.resolve_compound")
    @patch("data.loaders.load_prism")
    def test_proxy_resolution_warning(self, mock_prism, mock_resolve):
        from tools.viability import dose_response

        mock_resolve.return_value = "cpd_A"
        mock_prism.return_value = _prism_frame()
        result = dose_response(compound_id="original_name")

        assert result["is_proxy"] is True
        assert result["original_query"] == "original_name"
        assert "proxy" in result["summary"].lower()


class TestViabilityTissueSelectivity:
    @patch("tools._compound_resolver.resolve_compound", side_effect=lambda x, **_: x)
    @patch("data.loaders.load_model_metadata")
    @patch("data.loaders.load_prism")
    def test_tissue_profiles(self, mock_prism, mock_model, _mock_resolve):
        from tools.viability import tissue_selectivity

        mock_prism.return_value = _prism_frame()
        mock_model.return_value = _model_metadata()
        result = tissue_selectivity(compound_id="cpd_A", dose=10.0)

        assert "error" not in result
        assert result["dose_um"] == 10.0
        assert len(result["tissue_profiles"]) >= 1
        lineages = {p["lineage"] for p in result["tissue_profiles"]}
        assert "Lung" in lineages
        assert "Tissue selectivity" in result["summary"]

    @patch("tools._compound_resolver.resolve_compound", side_effect=lambda x, **_: x)
    @patch("data.loaders.load_model_metadata")
    @patch("data.loaders.load_prism")
    def test_no_lineages_with_enough_cells(self, mock_prism, mock_model, _mock_resolve):
        from tools.viability import tissue_selectivity

        df = _prism_frame()
        df = df[df["ccle_name"] == "CELL_A"]
        mock_prism.return_value = df
        mock_model.return_value = _model_metadata()
        result = tissue_selectivity(compound_id="cpd_A", dose=10.0)

        assert result["tissue_profiles"] == []
        assert "No tissue selectivity" in result["summary"]


class TestViabilityCompareCompounds:
    @patch("tools.viability.dose_response")
    def test_compare_sorts_by_ic50(self, mock_dr):
        from tools.viability import compare_compounds

        mock_dr.side_effect = [
            {
                "ic50_um": 5.0,
                "n_sensitive": 2,
                "n_resistant": 1,
                "n_cell_lines": 3,
            },
            {
                "ic50_um": 1.0,
                "n_sensitive": 3,
                "n_resistant": 0,
                "n_cell_lines": 3,
            },
        ]
        result = compare_compounds(compound_ids=["cpd_slow", "cpd_fast"])

        assert len(result["comparison"]) == 2
        assert result["comparison"][0]["compound"] == "cpd_fast"
        assert "Compared 2 compounds" in result["summary"]

    @patch("tools.viability.dose_response")
    def test_compare_all_missing(self, mock_dr):
        from tools.viability import compare_compounds

        mock_dr.return_value = {"error": "not found"}
        result = compare_compounds(compound_ids=["x", "y"])

        assert result["comparison"] == []
        assert "No compounds found" in result["summary"]
