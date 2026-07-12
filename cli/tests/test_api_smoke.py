"""Optional live data-source smoke checks for schema drift detection.

These tests call real public databases (PubMed, OpenAlex, UniProt, etc.) and are
skipped by default. Enable with: RUN_DATA_SMOKE=1 (legacy: RUN_API_SMOKE=1).
"""

from __future__ import annotations

import pytest

from env_flags import env_flag

from tools.clinical import (
    competitive_landscape,
    endpoint_benchmark,
    trial_design_benchmark,
    trial_search,
)
from tools.data_api import chembl_advanced, opentargets_search, uniprot_lookup
from tools.genomics import coloc, gwas_lookup
from tools.intel import pipeline_watch
from tools.literature import openalex_search, pubmed_search
from tools.target import disease_association, druggability, expression_profile
from tools.translational import biomarker_readiness


_RUN_SMOKE = env_flag("RUN_DATA_SMOKE", "RUN_API_SMOKE", "CT_RUN_API_SMOKE")
_STRICT_SMOKE = env_flag("DATA_SMOKE_STRICT", "API_SMOKE_STRICT", "CT_API_SMOKE_STRICT")

pytestmark = [
    pytest.mark.data_smoke,
    pytest.mark.skipif(not _RUN_SMOKE, reason="Set RUN_DATA_SMOKE=1 to run live data source smoke tests"),
]


def _assert_no_signature_error(payload: dict):
    text = str(payload)
    assert "unexpected keyword argument 'json'" not in text
    assert "unexpected keyword argument 'data'" not in text


def _skip_if_non_strict_error(payload: dict):
    """Skip local smoke runs on live API errors.

    In strict mode (CI), any API/tool error should fail the job so we detect drift/outages.
    """
    if _STRICT_SMOKE:
        return
    if "error" in payload:
        pytest.skip(f"Live data smoke skipped in non-strict mode: {payload.get('error')}")


def _skip_if_provider_limited(payload: dict):
    """Skip provider-side quota exhaustion, which is not an API schema regression."""
    error = str(payload.get("error", "")).lower()
    if "429" in error or "rate limit exceeded" in error or "insufficient budget" in error:
        pytest.skip(f"Live data provider quota exhausted: {payload.get('error')}")


def _assert_live_result(payload: dict, *, allow_ctgov_block: bool = False):
    """Assert a live tool response is healthy, with optional CT.gov datacenter blocks."""
    _assert_no_signature_error(payload)
    if "error" not in payload:
        assert "summary" in payload
        return
    err = str(payload.get("error", "")).lower()
    if allow_ctgov_block and "403" in err and "clinicaltrials" in err:
        # ClinicalTrials.gov often returns 403 from cloud CI/datacenter IPs.
        return
    if _STRICT_SMOKE:
        assert "error" not in payload, payload.get("error")
    _skip_if_non_strict_error(payload)


def test_pubmed_search_smoke():
    result = pubmed_search("TP53 cancer", max_results=1)
    _assert_no_signature_error(result)
    _skip_if_non_strict_error(result)
    assert "error" not in result, result.get("error")
    assert isinstance(result.get("articles"), list)
    assert "summary" in result


def test_openalex_search_smoke():
    result = openalex_search("TP53 cancer", max_results=1)
    _assert_no_signature_error(result)
    _skip_if_provider_limited(result)
    _skip_if_non_strict_error(result)
    assert "error" not in result, result.get("error")
    assert isinstance(result.get("articles"), list)
    assert "summary" in result


def test_uniprot_lookup_smoke():
    result = uniprot_lookup("P04637")
    _assert_no_signature_error(result)
    _skip_if_non_strict_error(result)
    assert "error" not in result, result.get("error")
    assert result.get("accession") == "P04637"
    assert "summary" in result


def test_gwas_lookup_smoke():
    result = gwas_lookup(gene="SNCA", trait="Parkinson disease")
    _assert_no_signature_error(result)
    _skip_if_non_strict_error(result)
    assert "error" not in result, result.get("error")
    assert "summary" in result
    assert result.get("n_associations", 0) >= 1


def test_trial_search_smoke():
    result = trial_search(query="Parkinson disease")
    _assert_live_result(result, allow_ctgov_block=True)
    if "error" not in result:
        assert result.get("total_count", 0) >= 1


def test_chembl_target_activities_smoke():
    result = chembl_advanced(query="EGFR", search_type="target_activities")
    _assert_no_signature_error(result)
    _skip_if_non_strict_error(result)
    assert "error" not in result, result.get("error")
    assert "summary" in result
    assert "activity_statistics" in result


def test_coloc_smoke():
    result = coloc(gene="SNCA")
    _assert_no_signature_error(result)
    _skip_if_non_strict_error(result)
    assert "error" not in result, result.get("error")
    assert "summary" in result
    assert "n_colocalizations" in result


def test_target_druggability_smoke():
    result = druggability(gene="LRRK2")
    _assert_no_signature_error(result)
    _skip_if_non_strict_error(result)
    assert "error" not in result, result.get("error")
    assert "summary" in result
    assert "druggability_score" in result


def test_target_expression_profile_smoke():
    result = expression_profile(gene="SNCA", top_n=5)
    _assert_no_signature_error(result)
    _skip_if_non_strict_error(result)
    assert "error" not in result, result.get("error")
    assert "summary" in result
    assert isinstance(result.get("gtex_expression"), list)


def test_target_disease_association_smoke():
    result = disease_association(gene="PINK1", min_score=0.1)
    _assert_no_signature_error(result)
    _skip_if_non_strict_error(result)
    assert "error" not in result, result.get("error")
    assert "summary" in result
    assert "associations" in result


def test_opentargets_search_smoke():
    result = opentargets_search(query="LRRK2", entity_type="target")
    _assert_no_signature_error(result)
    _skip_if_non_strict_error(result)
    if "error" in result:
        # Search should resolve; detail GraphQL may drift independently.
        err = result["error"].lower()
        assert "search failed" not in err and "timed out" not in err, result.get("error")
        assert "detail query failed" in err, result.get("error")
    else:
        assert "summary" in result


def test_trial_design_benchmark_smoke():
    result = trial_design_benchmark(query="Parkinson disease", max_results=5)
    _assert_live_result(result, allow_ctgov_block=True)
    if "error" not in result:
        assert "top_primary_endpoints" in result


def test_endpoint_benchmark_smoke():
    result = endpoint_benchmark(query="ulcerative colitis", max_results=5)
    _assert_live_result(result, allow_ctgov_block=True)
    if "error" not in result:
        assert "endpoint_families" in result


def test_competitive_landscape_smoke():
    result = competitive_landscape(gene="IL23R", indication="ulcerative colitis")
    _assert_no_signature_error(result)
    _skip_if_non_strict_error(result)
    assert "error" not in result, result.get("error")
    assert "summary" in result


def test_pipeline_watch_smoke():
    result = pipeline_watch(query="LRRK2", indication="Parkinson disease", max_trials=5, max_papers=3)
    _assert_no_signature_error(result)
    _skip_if_non_strict_error(result)
    assert "error" not in result, result.get("error")
    assert "summary" in result
    assert "momentum_score" in result


def test_biomarker_readiness_smoke():
    result = biomarker_readiness(biomarker="PD-L1", indication="NSCLC", max_evidence=3)
    _assert_no_signature_error(result)
    _skip_if_non_strict_error(result)
    assert "error" not in result, result.get("error")
    assert "summary" in result
    assert "readiness_score" in result
