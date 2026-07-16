"""
Clinical translation tools: indication mapping, patient population sizing, TCGA
stratification, clinical trial search/benchmarking, and competitive intelligence.

References crews-glue-discovery/scripts/patient_population_sizing.py and tcga_stratification.py
for data sources and scoring logic.

Split across tools/clinical_population.py (indication_map/population_size),
tools/clinical_tcga.py (tcga_stratify), tools/clinical_trials.py (trial_search/
trial_design_benchmark/endpoint_benchmark), and tools/clinical_competitive.py
(competitive_landscape); re-exported here for backward compatibility. This module
is the canonical patch target for tests (e.g. ``patch("tools.clinical.request_json")``);
submodules access shared helpers and cross-cluster tools indirectly via
``from tools import clinical as _clinical`` so that such patches take effect
regardless of which submodule performs the call.
"""

from tools.clinical_competitive import competitive_landscape
from tools.clinical_population import (
    LINEAGE_TO_CANCER,
    US_INCIDENCE,
    indication_map,
    population_size,
)
from tools.clinical_tcga import tcga_stratify
from tools.clinical_trials import (
    _CTGOV_HEADERS,
    _CTGOV_STUDIES_URL,
    _normalize_phase_token,
    endpoint_benchmark,
    trial_design_benchmark,
    trial_search,
)
from tools.http_client import request, request_json

__all__ = [
    "request",
    "request_json",
    "US_INCIDENCE",
    "LINEAGE_TO_CANCER",
    "indication_map",
    "population_size",
    "tcga_stratify",
    "_CTGOV_STUDIES_URL",
    "_CTGOV_HEADERS",
    "_normalize_phase_token",
    "trial_search",
    "trial_design_benchmark",
    "endpoint_benchmark",
    "competitive_landscape",
]
