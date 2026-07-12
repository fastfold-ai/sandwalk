"""Tests for tools._compound_resolver compound ID resolution."""

from unittest.mock import MagicMock, mock_open, patch

import pandas as pd
import pytest

import tools._compound_resolver as cr


@pytest.fixture(autouse=True)
def reset_compound_resolver_caches():
    cr._yu_smiles = None
    cr._prot_to_yu = None
    cr._yu_to_prot = None
    cr._tanimoto_search.cache_clear()
    yield
    cr._yu_smiles = None
    cr._prot_to_yu = None
    cr._yu_to_prot = None
    cr._tanimoto_search.cache_clear()


class TestResolveToSmiles:
    def test_invalid_input_raises(self):
        with pytest.raises(ValueError, match="Invalid input"):
            cr.resolve_to_smiles(None)
        with pytest.raises(ValueError, match="Empty input"):
            cr.resolve_to_smiles("   ")

    def test_smiles_heuristic_without_rdkit(self):
        with patch.dict("sys.modules", {"rdkit": None, "rdkit.Chem": None}):
            with patch("builtins.__import__", side_effect=ImportError("no rdkit")):
                result = cr.resolve_to_smiles("CC(=O)Oc1ccccc1C(=O)O")
        assert result == "CC(=O)Oc1ccccc1C(=O)O"

    @patch("tools.chemistry.pubchem_lookup")
    @patch("rdkit.Chem.MolFromSmiles", return_value=None)
    def test_pubchem_lookup_success(self, _mock_mol, mock_pubchem):
        mock_pubchem.return_value = {"properties": {"canonical_smiles": "CCO"}}
        assert cr.resolve_to_smiles("ethanol") == "CCO"
        mock_pubchem.assert_called_once_with("ethanol", query_type="name")

    @patch("tools.literature.chembl_query")
    @patch("tools.chemistry.pubchem_lookup", side_effect=Exception("pubchem down"))
    @patch("rdkit.Chem.MolFromSmiles", return_value=None)
    def test_chembl_fallback(self, _mock_mol, _mock_pubchem, mock_chembl):
        mock_chembl.return_value = {"molecules": [{"smiles": "CCN"}]}
        assert cr.resolve_to_smiles("ethylamine") == "CCN"

    @patch("tools.literature.chembl_query", side_effect=Exception("chembl down"))
    @patch("tools.chemistry.pubchem_lookup", side_effect=Exception("pubchem down"))
    @patch("rdkit.Chem.MolFromSmiles", return_value=None)
    def test_all_lookups_fail(self, _mock_mol, _pubchem, _chembl):
        with pytest.raises(ValueError, match="Could not resolve"):
            cr.resolve_to_smiles("unknown_drug_xyz")

    @patch("tools.chemistry.pubchem_lookup")
    def test_rdkit_valid_smiles_passthrough(self, mock_pubchem):
        mock_mol = MagicMock()
        with patch.dict("sys.modules", {"rdkit": MagicMock(), "rdkit.Chem": MagicMock()}):
            with patch("rdkit.Chem.MolFromSmiles", return_value=mock_mol):
                assert cr.resolve_to_smiles("c1ccccc1") == "c1ccccc1"
        mock_pubchem.assert_not_called()


class TestLoadYuSmiles:
    def test_load_from_csv(self, tmp_path, monkeypatch):
        csv_path = tmp_path / "all_compounds_smiles.csv"
        csv_path.write_text("compound,smiles\nYU123456,CCO\nYU654321,CCN\n")
        monkeypatch.setattr(cr, "_SMILES_CSV", str(csv_path))

        mapping = cr._load_yu_smiles()
        assert mapping["YU123456"] == "CCO"
        assert mapping["YU654321"] == "CCN"
        assert cr._load_yu_smiles() is mapping

    def test_missing_csv_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cr, "_SMILES_CSV", str(tmp_path / "missing.csv"))
        assert cr._load_yu_smiles() == {}


class TestProtMapping:
    def test_load_prot_mapping(self, tmp_path, monkeypatch):
        csv_path = tmp_path / "proteomics_to_yu_mapping.csv"
        csv_path.write_text("cmpd_id,yu_id\nCmpd18, YU123456\n")
        monkeypatch.setattr(cr, "_PROT_MAPPING_CSV", str(csv_path))

        prot_to_yu, yu_to_prot = cr._load_prot_mapping()
        assert prot_to_yu["Cmpd18"] == " YU123456"
        assert yu_to_prot[" YU123456"] == "Cmpd18"


class TestTanimotoSearch:
    def test_returns_none_without_rdkit(self):
        with patch.dict("sys.modules", {"rdkit": None}):
            with patch("builtins.__import__", side_effect=ImportError("no rdkit")):
                result = cr._tanimoto_search("CCO", frozenset({"YU123456"}))
        assert result is None

    @patch("rdkit.DataStructs.TanimotoSimilarity", side_effect=[0.9, 0.4])
    @patch("rdkit.Chem.AllChem.GetMorganFingerprintAsBitVect", return_value=MagicMock())
    @patch("rdkit.Chem.MolFromSmiles")
    def test_finds_best_match(self, mock_mol, _mock_fp, _mock_sim, tmp_path, monkeypatch):
        csv_path = tmp_path / "smiles.csv"
        csv_path.write_text("compound,smiles\nYU111111,CCO\nYU222222,CCN\n")
        monkeypatch.setattr(cr, "_SMILES_CSV", str(csv_path))
        mock_mol.return_value = MagicMock()

        result = cr._tanimoto_search("CCO", frozenset({"YU111111"}))
        assert result == ("YU111111", 0.9)

    @patch("rdkit.Chem.MolFromSmiles", return_value=None)
    def test_invalid_query_smiles(self, _mock_mol, tmp_path, monkeypatch):
        csv_path = tmp_path / "smiles.csv"
        csv_path.write_text("compound,smiles\nYU111111,CCO\n")
        monkeypatch.setattr(cr, "_SMILES_CSV", str(csv_path))
        assert cr._tanimoto_search("bad", frozenset({"YU111111"})) is None


class TestResolveCompound:
    @patch("data.loaders.load_l1000")
    def test_l1000_compound_name_index(self, mock_l1000):
        mock_l1000.return_value = pd.DataFrame(
            {"gene1": [1.0]},
            index=["Lenalidomide"],
        )
        assert cr.resolve_compound("lenalidomide", dataset="l1000") == "Lenalidomide"

    @patch("data.loaders.load_l1000")
    def test_l1000_partial_name_match(self, mock_l1000):
        mock_l1000.return_value = pd.DataFrame({"g": [1.0]}, index=["pomalidomide_10uM"])
        assert cr.resolve_compound("pomalidomide", dataset="l1000") == "pomalidomide_10uM"

    def test_yu_code_passthrough_prism(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cr, "_PROT_MAPPING_CSV", str(tmp_path / "missing.csv"))
        assert cr.resolve_compound("YU123456", dataset="prism") == "YU123456"

    def test_cmpd_to_yu_for_prism(self, tmp_path, monkeypatch):
        mapping = tmp_path / "map.csv"
        mapping.write_text("cmpd_id,yu_id\nCmpd18,YU123456\n")
        monkeypatch.setattr(cr, "_PROT_MAPPING_CSV", str(mapping))
        assert cr.resolve_compound("Cmpd18_B10", dataset="prism") == "YU123456"

    @patch("tools._compound_resolver._tanimoto_search", return_value=("YU123456", 0.9))
    @patch("tools._compound_resolver._get_dataset_compounds", return_value={"YU123456"})
    @patch("tools._compound_resolver.resolve_to_smiles", return_value="CCO")
    def test_drug_name_resolves_via_tanimoto(self, _smi, _cands, _tan):
        assert cr.resolve_compound("ethanol", dataset="prism") == "YU123456"

    @patch("tools._compound_resolver._tanimoto_search", return_value=("YU123456", 0.3))
    @patch("tools._compound_resolver._get_dataset_compounds", return_value={"YU123456"})
    @patch("tools._compound_resolver.resolve_to_smiles", return_value="CCO")
    def test_low_similarity_returns_original(self, _smi, _cands, _tan):
        assert cr.resolve_compound("ethanol", dataset="prism") == "ethanol"

    @patch("tools._compound_resolver.resolve_to_smiles", side_effect=ValueError("nope"))
    def test_unresolved_smiles_returns_original(self, _smi):
        assert cr.resolve_compound("mystery_drug", dataset="prism") == "mystery_drug"

    @patch("data.loaders.load_proteomics")
    def test_yu_to_proteomics_column(self, mock_prot, tmp_path, monkeypatch):
        mapping = tmp_path / "map.csv"
        mapping.write_text("cmpd_id,yu_id\nCmpd18,YU123456\n")
        monkeypatch.setattr(cr, "_PROT_MAPPING_CSV", str(mapping))
        mock_prot.return_value = pd.DataFrame({"Cmpd18_B10": [1.0]}, index=["TP53"])
        assert cr.resolve_proteomics_id("YU123456") == "Cmpd18_B10"


class TestGetDatasetCompounds:
    @patch("data.loaders.load_prism")
    def test_prism_compounds(self, mock_prism):
        mock_prism.return_value = pd.DataFrame({"pert_name": ["YU111111", "YU222222"]})
        assert cr._get_dataset_compounds("prism") == {"YU111111", "YU222222"}

    @patch("data.loaders.load_l1000")
    def test_l1000_compounds(self, mock_l1000):
        mock_l1000.return_value = pd.DataFrame({"g": [1.0, 2.0]}, index=["YU111111", "YU222222"])
        assert cr._get_dataset_compounds("l1000") == {"YU111111", "YU222222"}

    def test_proteomics_uses_mapping(self, tmp_path, monkeypatch):
        mapping = tmp_path / "map.csv"
        mapping.write_text("cmpd_id,yu_id\nCmpd18,YU123456\n")
        monkeypatch.setattr(cr, "_PROT_MAPPING_CSV", str(mapping))
        assert cr._get_dataset_compounds("proteomics") == {"YU123456"}
