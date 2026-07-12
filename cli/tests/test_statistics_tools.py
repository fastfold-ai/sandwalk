"""Unit tests for statistics tools (no external data required)."""

import pytest

from tools.statistics import dose_response_fit, enrichment_test, survival_analysis


class TestDoseResponseFit:
    def test_requires_doses_and_responses(self):
        result = dose_response_fit()
        assert "error" in result
        assert "summary" in result

    def test_length_mismatch(self):
        result = dose_response_fit(doses=[1, 2, 3], responses=[1, 2])
        assert "Length mismatch" in result["error"]

    def test_too_few_points(self):
        result = dose_response_fit(doses=[1, 2, 3], responses=[100, 80, 50])
        assert "at least 4" in result["error"]

    def test_positive_dose_filter(self):
        result = dose_response_fit(
            doses=[0, 0, 0, 1],
            responses=[100, 90, 80, 50],
        )
        assert "positive dose" in result["error"]

    def test_hill_fit_returns_ic50(self):
        doses = [0.01, 0.1, 1.0, 10.0, 100.0]
        responses = [98.0, 95.0, 60.0, 15.0, 5.0]
        result = dose_response_fit(
            doses=doses,
            responses=responses,
            compound_name="test-cpd",
        )
        assert "error" not in result
        assert result["compound"] == "test-cpd"
        assert result["ic50"] > 0
        assert result["r_squared"] > 0.5
        assert result["quality"] in {"HIGH", "MEDIUM", "LOW", "POOR"}
        assert "IC50" in result["summary"]


class TestSurvivalAnalysis:
    def test_requires_times_and_events(self):
        result = survival_analysis()
        assert "error" in result

    def test_length_mismatch(self):
        result = survival_analysis(times=[1, 2, 3], events=[1])
        assert "Length mismatch" in result["error"]

    def test_too_few_observations(self):
        result = survival_analysis(times=[1, 2], events=[1, 0])
        assert "at least 3" in result["error"]

    def test_single_group_km(self):
        result = survival_analysis(
            times=[1, 2, 3, 4, 5, 6],
            events=[1, 0, 1, 0, 1, 0],
        )
        assert "error" not in result
        km = result["kaplan_meier"]
        assert km["n_total"] == 6
        assert km["n_events"] == 3
        assert km["survival"][0] == 1.0
        assert "Kaplan-Meier" in result["summary"]

    def test_two_group_log_rank(self):
        result = survival_analysis(
            times=[1, 2, 3, 4, 5, 6, 7, 8],
            events=[1, 1, 0, 1, 0, 1, 1, 0],
            groups=["A", "A", "A", "A", "B", "B", "B", "B"],
        )
        assert "error" not in result
        assert "A" in result["groups"]
        assert "B" in result["groups"]
        assert "log_rank" in result
        assert "p_value" in result["log_rank"]

    def test_group_length_mismatch(self):
        result = survival_analysis(
            times=[1, 2, 3, 4],
            events=[1, 0, 1, 0],
            groups=["A", "B"],
        )
        assert "groups" in result["error"]

    def test_single_group_label_rejected(self):
        result = survival_analysis(
            times=[1, 2, 3, 4],
            events=[1, 0, 1, 0],
            groups=["A", "A", "A", "A"],
        )
        assert "at least 2 groups" in result["error"]


class TestEnrichmentTest:
    def test_requires_gene_list(self):
        result = enrichment_test()
        assert "non-empty gene_list" in result["error"]

    def test_unknown_collection(self):
        result = enrichment_test(gene_list=["TP53"], gene_set="unknown_set")
        assert "Unknown gene set collection" in result["error"]

    def test_custom_gene_set_overlap(self):
        result = enrichment_test(
            gene_list=["TP53", "CDKN1A", "BAX"],
            gene_set={
                "p53_pathway": ["TP53", "CDKN1A", "MDM2", "BAX"],
                "unrelated": ["EGFR", "KRAS"],
            },
            background_size=100,
        )
        assert "error" not in result
        assert result["n_query_genes"] == 3
        assert result["n_significant"] >= 1
        assert result["enriched"][0]["overlap_count"] == 3
        assert "enrichment" in result["summary"].lower()

    def test_hallmark_fallback_sets(self):
        result = enrichment_test(gene_list=["TP53", "BAX", "CDKN1A"])
        assert "error" not in result
        assert result["n_gene_sets_tested"] >= 10
        assert any(r["overlap_count"] > 0 for r in result["enriched"])

    def test_no_overlap_returns_empty_enriched(self):
        result = enrichment_test(
            gene_list=["ZZZZZ1", "ZZZZZ2"],
            gene_set={"empty_overlap": ["AAAAA1", "AAAAA2"]},
        )
        assert result["enriched"] == []
        assert "No enrichment found" in result["summary"]
