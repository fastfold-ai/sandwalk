"""Bulk tests for chemistry MMP, scaffold hop, and pharmacophore edge cases."""

import pytest
from pathlib import Path
from unittest.mock import patch

pytest.importorskip("rdkit")

from tools.chemistry import mmp_analysis, pharmacophore, scaffold_hop


class TestMmpAnalysis:
    def test_demo_dataset_default(self):
        result = mmp_analysis()
        assert "error" not in result
        assert result["n_compounds"] >= 2
        assert result["n_pairs"] > 0
        assert result["using_demo_data"] is True

    def test_csv_success(self, tmp_path):
        csv_path = tmp_path / "series.csv"
        csv_path.write_text(
            "smiles,activity,name\n"
            "c1ccc(C(=O)N)cc1,5.0,parent\n"
            "c1ccc(C(=O)N)cc1F,6.2,fluoro\n"
            "c1ccc(C(=O)N)cc1Cl,5.5,chloro\n",
            encoding="utf-8",
        )
        result = mmp_analysis(compounds_csv=str(csv_path))
        assert result["n_compounds"] == 3
        assert result["using_demo_data"] is False

    def test_csv_missing_smiles_column(self, tmp_path):
        csv_path = tmp_path / "bad.csv"
        csv_path.write_text("id,activity\n1,5.0\n", encoding="utf-8")
        result = mmp_analysis(compounds_csv=str(csv_path))
        assert "error" in result
        assert "SMILES" in result["error"]

    def test_csv_missing_activity_column(self, tmp_path):
        csv_path = tmp_path / "bad.csv"
        csv_path.write_text("smiles,potency\nc1ccccc1,5.0\n", encoding="utf-8")
        result = mmp_analysis(compounds_csv=str(csv_path), activity_col="activity")
        assert "error" in result
        assert "activity" in result["error"]

    def test_csv_read_error(self, tmp_path):
        missing = tmp_path / "missing.csv"
        result = mmp_analysis(compounds_csv=str(missing))
        assert "error" in result

    def test_insufficient_valid_compounds(self, tmp_path):
        csv_path = tmp_path / "one.csv"
        csv_path.write_text(
            "smiles,activity\nINVALID_SMILES,5.0\nalso_bad,6.0\n",
            encoding="utf-8",
        )
        result = mmp_analysis(compounds_csv=str(csv_path))
        assert "error" in result
        assert "at least 2" in result["error"].lower()


class TestScaffoldHop:
    def test_benzamide_detects_amide_and_phenyl(self):
        result = scaffold_hop(smiles="CC(=O)Nc1ccc(O)cc1")
        assert "error" not in result
        groups = {g["group"] for g in result["detected_functional_groups"]}
        assert "amide" in groups
        assert "phenyl" in groups
        assert len(result["bioisostere_suggestions"]) > 0

    def test_invalid_smiles(self):
        result = scaffold_hop(smiles="NOT_A_SMILES")
        assert "error" in result

    def test_pyridine_scaffold_replacements(self):
        result = scaffold_hop(smiles="c1ccncc1C(=O)N")
        assert "error" not in result
        assert result["murcko_scaffold"] != "N/A"
        assert isinstance(result["scaffold_replacements"], list)

    def test_low_fsp3_suggestion_for_flat_molecule(self):
        # Biphenyl is very flat (low Fsp3)
        result = scaffold_hop(smiles="c1ccc(-c2ccccc2)cc1")
        suggestions = result["property_context"]["suggestions_for_improvement"]
        assert any("Fsp3" in s for s in suggestions)

    @patch("tools.chemistry._extract_smiles", return_value="c1ccccc1O")
    def test_extract_smiles_used(self, _mock_extract):
        result = scaffold_hop(smiles="phenol")
        assert result["input_smiles"] == "c1ccccc1O"


class TestPharmacophoreEdgeCases:
    def test_fingerprints_method(self):
        smiles_list = ["c1ccccc1O", "c1ccccc1N", "c1ccc(O)cc1O"]
        result = pharmacophore(smiles_list=smiles_list, method="fingerprints")
        assert "consensus_score" in result
        assert result["method"] == "fingerprints"

    def test_invalid_smiles_in_list(self):
        result = pharmacophore(smiles_list=["c1ccccc1O", "BAD_SMILES", "c1ccccc1N"])
        assert result["n_compounds"] == 2
        assert "invalid_smiles" in result

    def test_single_compound_rejected(self):
        result = pharmacophore(smiles_list=["c1ccccc1O"])
        assert "error" in result

    def test_empty_list_rejected(self):
        result = pharmacophore(smiles_list=[])
        assert "error" in result

    def test_all_invalid_smiles(self):
        # Use strings that cannot be resolved to valid SMILES via compound resolver.
        result = pharmacophore(smiles_list=["INVALID1", "INVALID2"])
        assert "error" in result

    def test_common_features_conserved(self):
        # Three anilines share aromatic + HBD
        result = pharmacophore(
            smiles_list=["c1ccccc1N", "Nc1ccc(F)cc1", "Nc1ccc(Cl)cc1"],
            method="common_features",
        )
        feature_types = {f["type"] for f in result["common_features"]}
        assert "Aromatic" in feature_types or "HBD" in feature_types
