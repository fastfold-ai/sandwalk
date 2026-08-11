"""
GPU compute tools: list providers, estimate costs, submit jobs, check status.

PLACEHOLDER IMPLEMENTATION: Provider listings and pricing come from a static JSON
file bundled with ct. Prices may be outdated. submit_job and job_status make real
API calls when dry_run=False, but list_providers and estimate_cost use static data.
A real implementation would query live provider APIs for current pricing.

Split across compute_providers.py, compute_jobs.py, and compute_status.py
(+ compute_common.py for shared provider-data helpers); re-exported here
for backward compatibility.
"""

import time

from tools.compute_common import (
    _find_cheapest_gpu,
    _load_providers,
    _provider_api_key_config,
    _provider_info,
    _providers_data,
    _request_json,
    _resolve_provider,
)
from tools.compute_jobs import submit_job
from tools.compute_providers import estimate_cost, list_providers
from tools.compute_status import job_status

__all__ = [
    "list_providers",
    "estimate_cost",
    "submit_job",
    "job_status",
    "_load_providers",
    "_provider_info",
    "_provider_api_key_config",
    "_resolve_provider",
    "_request_json",
    "_find_cheapest_gpu",
    "_providers_data",
    "time",
]
