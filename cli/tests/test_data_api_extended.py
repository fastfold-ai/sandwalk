"""Extended mocked tests for data_api helpers and literature API wrappers."""

from unittest.mock import MagicMock, patch

import httpx
import pandas as pd
import pytest

from tools.data_api import (
    _extract_species_phrases,
    _keyword_fallback_query,
    _normalize_drug_query,
    _normalize_gene_name,
    _query_has_non_human_hints,
    depmap_search,
    opentargets_search,
    uniprot_lookup,
)
from tools.literature import _normalize_pubmed_query, _simplify_query, chembl_query, pubmed_search


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=resp
        )
    return resp


class TestDataApiHelpers:
    def test_normalize_gene_name_strips_prefix_and_uppercases(self):
        assert _normalize_gene_name("gene brca1") == "BRCA1"
        assert _normalize_gene_name("  tp53 ") == "TP53"

    def test_normalize_drug_query_strips_noise(self):
        assert _normalize_drug_query("fda-approved imatinib") == "imatinib"
        assert _normalize_drug_query("the drug compound aspirin") == "aspirin"

    def test_keyword_fallback_query_removes_stopwords(self):
        q = _keyword_fallback_query("look up secreted protein for helminth parasite")
        assert "look" not in q.split()
        assert "secreted" in q

    def test_query_has_non_human_hints(self):
        assert _query_has_non_human_hints("helminth secreted protein") is True
        assert _query_has_non_human_hints("BRCA1 tumor suppressor") is False

    def test_extract_species_phrases(self):
        phrases = _extract_species_phrases("Secreted proteins from Fasciola hepatica liver fluke")
        assert "Fasciola hepatica" in phrases

    def test_normalize_pubmed_query_uppercases_booleans(self):
        assert "AND" in _normalize_pubmed_query("tp53 and cancer")
        assert '"tp53 and cancer"' in _normalize_pubmed_query('"tp53 and cancer"')

    def test_simplify_query_generates_shorter_queries(self):
        long_q = "one two three four five six seven eight nine"
        shorter = _simplify_query(long_q)
        assert len(shorter) >= 1
        assert len(shorter[0].split()) < len(long_q.split())


class TestDepmapSearchExtended:
    @patch("data.loaders.load_mutations")
    def test_mutations_dataset_local(self, mock_mut):
        mock_mut.return_value = pd.DataFrame(
            {"TP53": [1, 0, 1, 0]},
            index=["L1", "L2", "L3", "L4"],
        )

        result = depmap_search(gene="tp53", dataset="mutations")
        assert "error" not in result
        assert result["dataset"] == "mutations"
        assert result["n_mutated"] == 2
        assert result["gene"] == "TP53"

    @patch("data.loaders.load_crispr")
    def test_gene_variant_hyphen_match(self, mock_crispr):
        mock_crispr.return_value = pd.DataFrame(
            {"CD274": [-0.8, -0.6]},
            index=["L1", "L2"],
        )

        result = depmap_search(gene="CD-274", dataset="crispr")
        assert result["gene"] == "CD274"
        assert "summary" in result

    @patch("data.loaders.load_crispr", side_effect=FileNotFoundError)
    @patch("tools.data_api._http_get")
    def test_cmp_api_non_200(self, mock_get, _mock_crispr):
        mock_get.return_value = _mock_response(503, {})

        result = depmap_search(gene="BRCA1", dataset="crispr")
        assert "error" in result
        assert "503" in result["error"]

    @patch("data.loaders.load_crispr", side_effect=ImportError)
    @patch("tools.data_api._http_get")
    def test_cmp_no_results(self, mock_get, _mock_crispr):
        mock_get.return_value = _mock_response(200, {"data": []})

        result = depmap_search(gene="NOTREALGENE", dataset="crispr")
        assert "error" in result


class TestOpenTargetsExtended:
    @patch("tools.data_api._http_post")
    def test_search_http_error(self, mock_post):
        mock_post.side_effect = httpx.HTTPError("connection reset")

        result = opentargets_search(query="TP53", entity_type="target")
        assert "error" in result

    @patch("tools.data_api._http_post")
    def test_detail_timeout(self, mock_post):
        search_resp = _mock_response(200, {
            "data": {
                "search": {
                    "total": 1,
                    "hits": [{"id": "ENSG1", "entity": "target", "name": "TP53"}],
                }
            }
        })
        mock_post.side_effect = [search_resp, httpx.TimeoutException("timeout")]

        result = opentargets_search(query="TP53", entity_type="target")
        assert "error" in result
        assert "timed out" in result["error"].lower()

    @patch("tools.data_api._http_post")
    def test_drug_query_normalization(self, mock_post):
        search_resp = _mock_response(200, {
            "data": {
                "search": {
                    "total": 1,
                    "hits": [{"id": "CHEMBL941", "entity": "drug", "name": "imatinib"}],
                }
            }
        })
        detail_resp = _mock_response(200, {
            "data": {
                "drug": {
                    "id": "CHEMBL941",
                    "name": "imatinib",
                    "drugType": "Small molecule",
                    "maximumClinicalTrialPhase": 4,
                    "hasBeenWithdrawn": False,
                    "description": "",
                    "mechanismsOfAction": {"rows": []},
                    "indications": {"count": 0, "rows": []},
                }
            }
        })
        mock_post.side_effect = [search_resp, detail_resp]

        result = opentargets_search(query="fda approved imatinib", entity_type="drug")
        assert result["entity_type"] == "drug"
        assert result["name"] == "imatinib"


class TestUniProtExtended:
    @patch("tools.data_api._http_get")
    def test_organism_taxid_filter_in_search(self, mock_get):
        mock_get.return_value = _mock_response(200, {"results": []})

        result = uniprot_lookup(query="kinase", organism="10090")
        assert "error" in result
        search_calls = [
            c for c in mock_get.call_args_list
            if "search" in str(c.args[0])
        ]
        assert search_calls
        query_param = search_calls[0].kwargs.get("params", {}).get("query", "")
        assert "organism_id:10090" in query_param

    @patch("tools.data_api._http_get")
    def test_search_http_failure(self, mock_get):
        mock_get.return_value = _mock_response(500, {})

        result = uniprot_lookup(query="BRCA1")
        assert "error" in result

    @patch("tools.data_api._http_get")
    def test_gene_symbol_search_with_mouse_organism(self, mock_get):
        mock_get.return_value = _mock_response(200, {
            "results": [{
                "primaryAccession": "P38398",
                "genes": [{"geneName": {"value": "Brca1"}, "synonyms": []}],
                "proteinDescription": {
                    "recommendedName": {"fullName": {"value": "Breast cancer type 1"}}
                },
                "sequence": {"length": 100},
                "comments": [],
                "features": [],
                "uniProtKBCrossReferences": [],
                "keywords": [],
            }]
        })

        result = uniprot_lookup(query="Brca1", organism="mouse")
        assert "summary" in result
        assert result["accession"] == "P38398"


class TestPubmedSearchExtended:
    @patch("tools.literature.request_json")
    def test_pubmed_search_success(self, mock_request_json):
        mock_request_json.side_effect = [
            ({"esearchresult": {"count": "2", "idlist": ["1", "2"]}}, None),
            ({
                "result": {
                    "uids": ["1", "2"],
                    "1": {
                        "title": "TP53 in cancer",
                        "authors": [{"name": "Smith J"}],
                        "source": "Nature",
                        "pubdate": "2024",
                        "articleids": [{"idtype": "doi", "value": "10.1/tp53"}],
                    },
                    "2": {
                        "title": "Second paper",
                        "authors": [],
                        "source": "Cell",
                        "pubdate": "2023",
                        "articleids": [],
                    },
                }
            }, None),
        ]

        result = pubmed_search(query="tp53 and cancer", max_results=5)
        assert "error" not in result
        assert result["total_count"] == 2
        assert len(result["articles"]) == 2
        assert result["articles"][0]["doi"] == "10.1/tp53"

    @patch("tools.literature.request_json")
    def test_pubmed_search_simplified_fallback(self, mock_request_json):
        long_query = "one two three four five six seven eight nine ten"

        def _side_effect(method, url, **kwargs):
            term = kwargs.get("params", {}).get("term", "")
            if term == _normalize_pubmed_query(long_query):
                return ({"esearchresult": {"count": "0", "idlist": []}}, None)
            if term == _normalize_pubmed_query("one two three four five"):
                return ({"esearchresult": {"count": "1", "idlist": ["99"]}}, None)
            if "id" in kwargs.get("params", {}):
                return ({
                    "result": {
                        "uids": ["99"],
                        "99": {
                            "title": "Fallback hit",
                            "authors": [],
                            "source": "J",
                            "pubdate": "2024",
                            "articleids": [],
                        },
                    }
                }, None)
            return ({"esearchresult": {"count": "0", "idlist": []}}, None)

        mock_request_json.side_effect = _side_effect
        result = pubmed_search(query=long_query)
        assert result["total_count"] == 1
        assert "simplified" in result["summary"]

    @patch("tools.literature.request_json")
    def test_pubmed_search_request_error(self, mock_request_json):
        mock_request_json.return_value = (None, "HTTP 503")

        result = pubmed_search(query="aspirin")
        assert "error" in result


class TestChemblQueryExtended:
    @patch("tools.literature.request_json")
    def test_chembl_target_search(self, mock_request_json):
        mock_request_json.return_value = (
            {
                "targets": [{
                    "target_chembl_id": "CHEMBL203",
                    "pref_name": "EGFR",
                    "organism": "Homo sapiens",
                    "target_type": "SINGLE PROTEIN",
                }]
            },
            None,
        )

        result = chembl_query(query="EGFR", query_type="target")
        assert result["targets"][0]["chembl_id"] == "CHEMBL203"

    @patch("tools.literature.request_json")
    def test_chembl_activity_by_compound_name(self, mock_request_json):
        mock_request_json.side_effect = [
            ({"molecules": [{"molecule_chembl_id": "CHEMBL941"}]}, None),
            ({
                "activities": [{
                    "molecule_chembl_id": "CHEMBL941",
                    "molecule_pref_name": "IMATINIB",
                    "target_chembl_id": "CHEMBL1862",
                    "target_pref_name": "ABL1",
                    "standard_type": "IC50",
                    "standard_value": "100",
                    "standard_units": "nM",
                    "pchembl_value": "7.0",
                    "assay_type": "B",
                    "assay_description": "Kinase assay",
                }]
            }, None),
        ]

        result = chembl_query(query="imatinib", query_type="activity")
        assert len(result["activities"]) == 1
        assert result["chembl_id"] == "CHEMBL941"

    @patch("tools.literature.request_json")
    def test_chembl_similarity_search(self, mock_request_json):
        mock_request_json.return_value = (
            {
                "molecules": [{
                    "molecule_chembl_id": "CHEMBL2",
                    "pref_name": "ANALOG",
                    "similarity": 85,
                    "molecule_structures": {"canonical_smiles": "CCO"},
                }]
            },
            None,
        )

        result = chembl_query(query="CC(=O)O", query_type="similarity")
        assert result["hits"][0]["similarity"] == 85

    @patch("tools.literature.request_json")
    def test_chembl_unknown_query_type(self, mock_request_json):
        result = chembl_query(query="aspirin", query_type="bogus_type")
        assert "error" in result
        mock_request_json.assert_not_called()

    @patch("tools.literature.request_json")
    def test_chembl_request_error(self, mock_request_json):
        mock_request_json.return_value = (None, "timeout")

        result = chembl_query(query="aspirin", query_type="molecule")
        assert "error" in result

    @patch("tools.literature.request_json")
    def test_chembl_drug_alias_maps_to_molecule(self, mock_request_json):
        mock_request_json.return_value = (
            {"molecules": [{"molecule_chembl_id": "CHEMBL1", "pref_name": "DRUG", "molecule_type": "Small molecule", "max_phase": 4, "molecule_properties": {}, "molecule_structures": {}}]},
            None,
        )

        result = chembl_query(query="aspirin", query_type="drug")
        assert "molecules" in result
