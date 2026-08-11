"""
Deployment readiness checks for fastfold.

Used by `sandwalk doctor`, interactive `/doctor`, and the local agent `/v1/doctor` API.

Split into sibling modules to stay under the file-length cap. A few functions
that are patched directly in tests (``_check_api_connectivity``,
``_locate_boltz_cli_path``, ``_boltz_cli_version``, ``run_checks_core``,
``run_checks``) are called by their callers through ``import agent.doctor as
_doctor`` so the patched attribute on this package is always what runs,
regardless of which submodule defines the caller.
"""

from __future__ import annotations

from pathlib import Path  # noqa: F401 — re-exported so `patch("agent.doctor.Path.home")` resolves

from agent.doctor.checks_boltz import (
    _boltz_cli_version,
    _check_boltz_cli,
    _locate_boltz_cli_path,
)
from agent.doctor.checks_connectivity import _check_api_connectivity, _check_tool_health
from agent.doctor.checks_data import _check_data_availability, _check_downloads_dir
from agent.doctor.checks_environment import _check_environment
from agent.doctor.checks_mcp import _check_mcp_servers
from agent.doctor.checks_runtime import _check_python_runtime, _check_sandbox_backend
from agent.doctor.formatting import to_report, to_table
from agent.doctor.model_provider_probe import _check_model_providers
from agent.doctor.models import DoctorCheck, _normalize_check, _status_markup
from agent.doctor.run_checks import run_checks
from agent.doctor.summary import _configured_llm_summary, has_errors, has_warnings, run_checks_core

__all__ = [
    "DoctorCheck",
    "has_errors",
    "has_warnings",
    "run_checks",
    "run_checks_core",
    "to_report",
    "to_table",
]
