"""Additional mocked tests for uncovered genomics.py paths."""

from unittest.mock import MagicMock, patch

import pytest

from tools.genomics import (
    coloc,
    eqtl_lookup,
    gwas_lookup,
    mendelian_randomization_lookup,
    variant_annotate,
    variant_classify,
)


class TestGwasLookupExtended:
    def test_missing_gene_parameter(self):
        result = gwas_lookup(gene="", trait="Parkinson")
        assert "Missing required parameter" in result["error"]
        assert result["trait_filter"] == "Parkinson"

    @patch("tools.genomics.request_json")
    def test_trait_filter_applied(self, mock_request):
        mock_request.side_effect = [
            ({"_embedded": {"singleNucleotidePolymorphisms": [{"rsId": "rs1"}]}}, None),
            (
                {
                    "_embedded": {
                        "associations": [
                            {
                                "pvalueMantissa": 1,
                                "pvalueExponent": -10,
                                "efoTraits": [{"trait": "Type 2 diabetes"}],
                                "loci": [{"strongestRiskAlleles": [{"riskAlleleName": "A"}]}],
                            },
                            {
                                "pvalueMantissa": 1,
                                "pvalueExponent": -10,
                                "efoTraits": [{"trait": "Height"}],
                                "loci": [{"strongestRiskAlleles": [{"riskAlleleName": "G"}]}],
                            },
                        ]
                    }
                },
                None,
            ),
        ]
        result = gwas_lookup(gene="TCF7L2", trait="diabetes")
        assert result["n_associations"] == 1
        assert "diabetes" in result["associations"][0]["trait"].lower()

    @patch("tools.genomics.request_json")
    def test_snp_assoc_error_skips_snp(self, mock_request):
        mock_request.side_effect = [
            ({"_embedded": {"singleNucleotidePolymorphisms": [{"rsId": "rs1"}, {"rsId": "rs2"}]}}, None),
            (None, "timeout"),
            (
                {
                    "_embedded": {
                        "associations": [
                            {
                                "pvalueMantissa": 5,
                                "pvalueExponent": -9,
                                "efoTraits": [{"trait": "Trait A"}],
                                "loci": [],
                            }
                        ]
                    }
                },
                None,
            ),
        ]
        result = gwas_lookup(gene="APOE")
        assert result["n_associations"] == 1


class TestEqtlLookupExtended:
    @patch("tools.genomics.request_json")
    def test_eqtl_with_tissue_filter(self, mock_request):
        mock_request.side_effect = [
            (
                {"data": [{"gencodeId": "ENSG1", "geneSymbol": "BRCA1", "description": "breast cancer 1"}]},
                None,
            ),
            (
                {
                    "data": [
                        {
                            "variantId": "1_1_A_G",
                            "snpId": "rs1",
                            "tissueSiteDetailId": "Brain_Cortex",
                            "pValue": 1e-8,
                            "nes": 0.4,
                            "chromosome": "17",
                            "pos": 100,
                            "geneSymbol": "BRCA1",
                        }
                    ]
                },
                None,
            ),
        ]
        result = eqtl_lookup(gene="BRCA1", tissue="Brain_Cortex")
        assert result["n_eqtls"] == 1
        assert result["eqtls"][0]["tissue"] == "Brain_Cortex"
        eqtl_call = mock_request.call_args_list[1]
        assert eqtl_call.kwargs["params"]["tissueSiteDetailId"] == "Brain_Cortex"


class TestMendelianRandomizationExtended:
    @patch("tools.genomics.request_json")
    def test_mr_lookup_with_efo_disease_id(self, mock_request):
        mock_request.side_effect = [
            (
                {
                    "data": {
                        "search": {
                            "hits": [
                                {"id": "ENSG000001", "entity": "target", "name": "PCSK9", "description": ""}
                            ]
                        }
                    }
                },
                None,
            ),
            (
                {
                    "data": {
                        "target": {
                            "approvedSymbol": "PCSK9",
                            "approvedName": "PCSK9",
                            "associatedDiseases": {
                                "rows": [
                                    {
                                        "score": 0.8,
                                        "datasourceScores": [{"id": "gwas_credible_sets", "score": 0.7}],
                                    }
                                ]
                            },
                            "evidences": {
                                "count": 1,
                                "rows": [
                                    {
                                        "datasourceId": "gwas_credible_sets",
                                        "datatypeId": "genetic_association",
                                        "score": 0.7,
                                        "resourceScore": 0.6,
                                        "studyId": "GCST001",
                                        "variantRsId": "rs123",
                                        "credibleSet": {
                                            "studyLocusId": "loc1",
                                            "study": {"id": "study1", "studyType": "gwas"},
                                            "variant": {"id": "1_123_A_G", "rsIds": ["rs123"]},
                                            "pValueMantissa": 5,
                                            "pValueExponent": -9,
                                            "beta": 0.2,
                                            "finemappingMethod": "suie",
                                        },
                                    }
                                ],
                            },
                        },
                        "disease": {"id": "EFO_0000389", "name": "Coronary artery disease"},
                    }
                },
                None,
            ),
        ]
        result = mendelian_randomization_lookup(gene="PCSK9", disease="EFO_0000389")
        assert result["gene"] == "PCSK9"
        assert result["disease_id"] == "EFO_0000389"
        assert result["total_evidence_count"] == 1
        assert len(result["gwas_credible_sets"]) == 1
        assert result["max_l2g_score"] == 0.7

    @patch("tools.genomics.request_json")
    def test_mr_graphql_errors(self, mock_request):
        mock_request.side_effect = [
            (
                {
                    "data": {
                        "search": {
                            "hits": [{"id": "ENSG1", "entity": "target", "name": "APOE"}]
                        }
                    }
                },
                None,
            ),
            (
                {
                    "data": {
                        "search": {
                            "hits": [
                                {
                                    "id": "EFO_0000249",
                                    "entity": "disease",
                                    "name": "Alzheimer disease",
                                }
                            ]
                        }
                    }
                },
                None,
            ),
            (
                {
                    "data": {},
                    "errors": [{"message": "Invalid efo id"}],
                },
                None,
            ),
        ]
        result = mendelian_randomization_lookup(gene="APOE", disease="Alzheimer")
        assert "GraphQL errors" in result["error"]


class TestVariantAnnotateExtended:
    @patch("tools.genomics.request")
    def test_variant_annotate_hgvs(self, mock_request):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = [
            {
                "id": "17:7675088:C:T",
                "input": "17:g.7675088C>T",
                "most_severe_consequence": "missense_variant",
                "allele_string": "C/T",
                "transcript_consequences": [
                    {"gene_symbol": "TP53", "consequence_terms": ["missense_variant"]}
                ],
                "colocated_variants": [],
            }
        ]
        mock_request.return_value = (resp, None)
        result = variant_annotate(variant="17:g.7675088C>T")
        assert "TP53" in result["summary"] or result.get("gene_symbol") == "TP53"


class TestVariantClassify:
    @patch("tools.code._generate_and_execute_code")
    def test_variant_classify_delegates(self, mock_exec):
        mock_exec.return_value = {"summary": "classified 12 variants"}
        session = MagicMock()
        result = variant_classify(goal="Filter VAF > 0.05", _session=session)
        assert result["summary"] == "classified 12 variants"
        mock_exec.assert_called_once()
        prompt = mock_exec.call_args.kwargs["system_prompt_template"]
        assert "variant" in prompt.lower()


class TestColocExtended:
    @patch("tools.genomics.request")
    def test_coloc_httpx_missing(self, mock_request):
        with patch.dict("sys.modules", {"httpx": None}):
            with patch(
                "builtins.__import__",
                side_effect=lambda name, *args, **kwargs: (_ for _ in ()).throw(ImportError(name)),
            ):
                result = coloc(gene="SNCA")
        assert "httpx required" in result["summary"]

    @patch("tools.genomics.request")
    def test_coloc_ensembl_resolve_failure(self, mock_request):
        resp = MagicMock(status_code=404)
        mock_request.return_value = (resp, "not found")
        result = coloc(gene="NOTREAL")
        assert "not found" in result["summary"].lower() or "error" in result
