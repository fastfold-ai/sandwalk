"""Bulk mocked tests for genomics.py and clinical.py entry points."""

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# ─── Genomics ───────────────────────────────────────────────────────────────


class TestGwasLookup:
    @patch("tools.genomics.request_json")
    def test_gwas_lookup_success(self, mock_request):
        from tools.genomics import gwas_lookup

        mock_request.side_effect = [
            (
                {
                    "_embedded": {
                        "singleNucleotidePolymorphisms": [{"rsId": "rs123"}],
                    }
                },
                None,
            ),
            (
                {
                    "_embedded": {
                        "associations": [
                            {
                                "pvalueMantissa": 5,
                                "pvalueExponent": -9,
                                "efoTraits": [{"trait": "Parkinson disease"}],
                                "loci": [{"strongestRiskAlleles": [{"riskAlleleName": "A"}]}],
                                "orPerCopyNum": 1.2,
                            }
                        ]
                    }
                },
                None,
            ),
        ]
        result = gwas_lookup(gene="SNCA", trait="Parkinson")
        assert result["n_associations"] >= 1
        assert "SNCA" in result["summary"]

    @patch("tools.genomics.request_json")
    def test_gwas_lookup_no_snps(self, mock_request):
        from tools.genomics import gwas_lookup

        mock_request.return_value = ({"_embedded": {"singleNucleotidePolymorphisms": []}}, None)
        result = gwas_lookup(gene="FAKEGENE")
        assert result["n_associations"] == 0

    @patch("tools.genomics.request_json")
    def test_gwas_lookup_api_error(self, mock_request):
        from tools.genomics import gwas_lookup

        mock_request.return_value = (None, "timeout")
        result = gwas_lookup(gene="TP53")
        assert "error" in result


class TestEqtlLookup:
    @patch("tools.genomics.request_json")
    def test_eqtl_lookup_success(self, mock_request):
        from tools.genomics import eqtl_lookup

        mock_request.side_effect = [
            (
                {"data": [{"gencodeId": "ENSG000001", "geneSymbol": "BRCA1", "description": "breast cancer 1"}]},
                None,
            ),
            (
                {
                    "data": [
                        {
                            "variantId": "1_123_A_G",
                            "snpId": "rs999",
                            "tissueSiteDetailId": "Brain_Cortex",
                            "pValue": 1e-8,
                            "nes": 0.5,
                            "chromosome": "17",
                            "pos": 123,
                            "geneSymbol": "BRCA1",
                        }
                    ]
                },
                None,
            ),
        ]
        result = eqtl_lookup(gene="BRCA1")
        assert result["n_eqtls"] == 1
        assert result["gene"] == "BRCA1"

    @patch("tools.genomics.request_json")
    def test_eqtl_lookup_gene_not_found(self, mock_request):
        from tools.genomics import eqtl_lookup

        mock_request.return_value = ({"data": []}, None)
        result = eqtl_lookup(gene="NOTREAL")
        assert "error" in result


class TestVariantAnnotate:
    @patch("tools.genomics.request")
    def test_variant_annotate_rsid(self, mock_request):
        from tools.genomics import variant_annotate

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = [
            {
                "id": "rs1042522",
                "input": "rs1042522",
                "most_severe_consequence": "missense_variant",
                "allele_string": "C/T",
                "transcript_consequences": [
                    {"gene_symbol": "TP53", "consequence_terms": ["missense_variant"]}
                ],
                "colocated_variants": [],
            }
        ]
        mock_request.return_value = (resp, None)
        result = variant_annotate(variant="rs1042522")
        assert "TP53" in result["summary"] or result.get("gene_symbol") == "TP53" or "missense" in result["summary"].lower()

    @patch("tools.genomics.request")
    def test_variant_annotate_bad_format(self, mock_request):
        from tools.genomics import variant_annotate

        resp = MagicMock()
        resp.status_code = 400
        mock_request.return_value = (resp, None)
        result = variant_annotate(variant="not-a-variant")
        assert "error" in result


class TestMendelianRandomization:
    @patch("tools.genomics.request_json")
    def test_mr_lookup_gene_not_found(self, mock_request):
        from tools.genomics import mendelian_randomization_lookup

        mock_request.return_value = ({"data": {"search": {"hits": []}}}, None)
        result = mendelian_randomization_lookup(gene="NOTREAL", disease="T2D")
        assert "error" in result
        assert "NOTREAL" in result["summary"] or "NOTREAL" in result["error"]


# ─── Clinical ─────────────────────────────────────────────────────────────────


def _prism_fixture():
    return pd.DataFrame(
        {
            "pert_name": ["cpd_A"] * 6 + ["cpd_B"] * 4,
            "pert_dose": [10.0] * 10,
            "ccle_name": ["LUNG1", "LUNG2", "LUNG3", "BREAST1", "BREAST2", "BREAST3"]
            + ["LUNG1", "LUNG2", "BREAST1", "BREAST2"],
            "LFC": [-1.0, -0.8, -0.2, -1.1, -0.9, 0.1, 0.0, 0.2, -0.1, 0.3],
        }
    )


def _model_fixture():
    return pd.DataFrame(
        {
            "CCLEName": ["LUNG1", "LUNG2", "LUNG3", "BREAST1", "BREAST2", "BREAST3"],
            "OncotreeLineage": ["Lung", "Lung", "Lung", "Breast", "Breast", "Breast"],
        }
    )


class TestIndicationMap:
    @patch("data.loaders.load_model_metadata")
    @patch("data.loaders.load_prism")
    def test_indication_map_single_compound(self, mock_prism, mock_model):
        from tools.clinical import indication_map

        mock_prism.return_value = _prism_fixture()
        mock_model.return_value = _model_fixture()
        result = indication_map(compound_id="cpd_A", min_response_rate=0.1)
        assert result["n_indications"] >= 1
        assert any(row["compound"] == "cpd_A" for row in result["indications"])

    @patch("data.loaders.load_model_metadata")
    @patch("data.loaders.load_prism")
    def test_indication_map_unknown_compound(self, mock_prism, mock_model):
        from tools.clinical import indication_map

        mock_prism.return_value = _prism_fixture()
        mock_model.return_value = _model_fixture()
        result = indication_map(compound_id="missing_cpd")
        assert result["n_indications"] == 0


class TestPopulationSize:
    @patch("data.loaders.load_model_metadata")
    @patch("data.loaders.load_prism")
    def test_population_size_estimates(self, mock_prism, mock_model):
        from tools.clinical import population_size

        mock_prism.return_value = _prism_fixture()
        mock_model.return_value = _model_fixture()
        result = population_size(compound_id="cpd_A", clinical_adjustment=0.10)
        assert "summary" in result
        assert result.get("populations") or result.get("estimates") or "cpd_A" in result["summary"]


class TestTcgaStratify:
    @patch("tools.clinical.request")
    def test_tcga_stratify_cached_gene(self, mock_request):
        from tools.clinical import tcga_stratify

        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": "application/json"}
        resp.json.return_value = {
            "RNA cancer specificity": "Low cancer specificity",
            "RNA cancer distribution": "Detected in several",
            "RNA tissue specificity": "Low tissue specificity",
            "RNA cancer sample": {
                "lung cancer": {"value": 12.0},
                "breast cancer": {"value": 2.0},
            },
            "Cancer prognostics - lung cancer (TCGA)": {
                "is_prognostic": True,
                "prognostic type": "unfavourable",
                "prognostic": "prognostic",
                "p_val": "0.01",
            },
        }
        mock_request.return_value = (resp, None)
        result = tcga_stratify(gene="CRBN")
        assert result["gene"] == "CRBN"
        assert len(result["cancer_expression"]) >= 1


class TestTrialSearch:
    @patch("tools.clinical.request_json")
    def test_trial_search_parses_studies(self, mock_request):
        from tools.clinical import trial_search

        mock_request.return_value = (
            {
                "studies": [
                    {
                        "protocolSection": {
                            "identificationModule": {"nctId": "NCT0001", "briefTitle": "Study A"},
                            "statusModule": {"overallStatus": "RECRUITING", "startDateStruct": {"date": "2024-01"}},
                            "designModule": {
                                "phases": ["PHASE2"],
                                "enrollmentInfo": {"count": 100},
                            },
                            "conditionsModule": {"conditions": ["Melanoma"]},
                            "armsInterventionsModule": {
                                "interventions": [{"type": "DRUG", "name": "DrugX"}]
                            },
                            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Acme"}},
                        }
                    }
                ]
            },
            None,
        )
        result = trial_search(query="melanoma BRAF")
        assert result["total_count"] == 1
        assert result["trials"][0]["nct_id"] == "NCT0001"

    @patch("tools.clinical.request_json")
    def test_trial_search_empty(self, mock_request):
        from tools.clinical import trial_search

        mock_request.return_value = ({"studies": []}, None)
        result = trial_search(query="nonexistent-xyz")
        assert "No clinical trials" in result["summary"]


class TestTrialDesignBenchmark:
    @patch("tools.clinical.request_json")
    def test_trial_design_benchmark_requires_query(self, mock_request):
        from tools.clinical import trial_design_benchmark

        result = trial_design_benchmark(query="  ")
        assert "error" in result
        mock_request.assert_not_called()

    @patch("tools.clinical.request_json")
    def test_trial_design_benchmark_summary(self, mock_request):
        from tools.clinical import trial_design_benchmark

        mock_request.return_value = (
            {
                "studies": [
                    {
                        "protocolSection": {
                            "identificationModule": {"nctId": "NCT0002", "briefTitle": "Benchmark trial"},
                            "statusModule": {"overallStatus": "COMPLETED"},
                            "designModule": {
                                "phases": ["PHASE3"],
                                "enrollmentInfo": {"count": 200},
                                "designInfo": {
                                    "allocation": "RANDOMIZED",
                                    "interventionModel": "PARALLEL",
                                    "maskingInfo": {"masking": "DOUBLE"},
                                },
                            },
                            "conditionsModule": {"conditions": ["NSCLC"]},
                            "armsInterventionsModule": {
                                "interventions": [{"type": "DRUG", "name": "DrugY"}]
                            },
                            "outcomesModule": {
                                "primaryOutcomes": [{"measure": "Overall Survival"}],
                            },
                            "eligibilityModule": {"eligibilityCriteria": "ECOG 0-1"},
                            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "PharmaCo"}},
                        }
                    }
                ]
            },
            None,
        )
        result = trial_design_benchmark(query="NSCLC EGFR", phase="PHASE3")
        assert "summary" in result
        assert result.get("n_trials", 0) >= 1 or result.get("trials")


class TestEndpointBenchmark:
    @patch("tools.clinical.request_json")
    def test_endpoint_benchmark(self, mock_request):
        from tools.clinical import endpoint_benchmark

        mock_request.return_value = (
            {
                "studies": [
                    {
                        "protocolSection": {
                            "identificationModule": {"nctId": "NCT0003", "briefTitle": "Endpoint study"},
                            "statusModule": {"overallStatus": "RECRUITING"},
                            "designModule": {"phases": ["PHASE2"]},
                            "outcomesModule": {
                                "primaryOutcomes": [{"measure": "Progression-Free Survival"}],
                                "secondaryOutcomes": [{"measure": "ORR"}],
                            },
                            "conditionsModule": {"conditions": ["Breast cancer"]},
                        }
                    }
                ]
            },
            None,
        )
        result = endpoint_benchmark(query="breast cancer CDK4")
        assert "summary" in result


class TestCompetitiveLandscape:
    @patch("tools.clinical.request_json")
    @patch("tools.clinical.trial_search")
    def test_competitive_landscape_aggregates(self, mock_trial_search, mock_request):
        from tools.clinical import competitive_landscape

        mock_trial_search.return_value = {
            "total_count": 2,
            "phase_distribution": {"PHASE2": 1},
            "status_distribution": {"RECRUITING": 2},
            "trials": [{"nct_id": "NCT1", "title": "Trial"}],
        }
        mock_request.side_effect = [
            ({"targets": [{"organism": "Homo sapiens", "target_type": "SINGLE PROTEIN", "target_chembl_id": "CHEMBL1"}]}, None),
            ({"activities": [{"molecule_chembl_id": "CHEMBL123", "standard_type": "IC50", "standard_value": "10"}]}, None),
            ({"data": {"target": {"approvedDrugs": {"count": 1, "rows": []}}}}, None),
        ]
        result = competitive_landscape(gene="BRAF", indication="melanoma")
        assert result["gene"] == "BRAF"
        assert "trials" in result
