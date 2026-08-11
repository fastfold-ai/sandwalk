"""Flat backward-compatible re-exports for the setup-wizard submodules.

See ``cli/_compat.py`` for why this exists. Imported via ``import *`` from
``cli/__init__.py`` so ``cli.<name>`` keeps working for every setup helper.
"""
# ruff: noqa: I001 — hand-packed imports (kept compact to fit the line-count cap)

from cli.setup.boltz_install import (
    _boltz_cli_version, _ensure_boltz_cli_installed_from_setup,
    _find_boltz_cli_path, _install_boltz_skill_from_setup, _prompt_install_boltz_stack,
)
from cli.setup.cloud_keys import _prompt_boltz_api_key, _prompt_fastfold_cloud_api_key
from cli.setup.compatible_backend import (
    _infer_openai_compatible_backend, _prompt_openai_compatible_backend,
    _resolve_openai_compatible_endpoint,
)
from cli.setup.compatible_profile import _find_compatible_profile_id_by_label, _prompt_setup_compatible_profile_id
from cli.setup.datasets_prompt import _prompt_install_datasets, _select_datasets_from_catalog
from cli.setup.discovery import (
    _extract_discovery_error_message, _ollama_tags_url_from_base,
    _openai_models_url_from_base, _read_http_error_body,
    _report_discovery_exception, _report_discovery_http_error,
    _truncate_discovery_detail,
)
from cli.setup.discovery_fetch import (
    _fetch_compatible_models_for_setup, _fetch_ollama_tags_for_setup, _fetch_openai_models_for_setup,
)
from cli.setup.keys import (
    _prompt_api_key, _prompt_masked_secret, _prompt_openai_api_key,
    _prompt_openai_api_key_with_default, _prompt_openai_compatible_api_key,
    _prompt_provider_api_key,
)
from cli.setup.mcp_prompt import _prompt_setup_mcps
from cli.setup.model_prompt import _prompt_compatible_model_for_setup
from cli.setup.openai_endpoint import (
    _compatible_backend_display_name, _compatible_default_endpoint,
    _compatible_install_url, _is_openai_managed_base_url,
    _normalize_compatible_backend_name, _normalize_openai_base_url,
)
from cli.setup.openai_endpoint_mode import _prompt_openai_endpoint_mode, _resolve_openai_base_url
from cli.setup.provider_key import _resolve_provider_key
from cli.setup.providers import _parse_provider_list, _prompt_setup_providers, _setup_provider_runtime_id
from cli.setup.sandbox_prompt import _prompt_setup_sandbox
from cli.setup.skills_install import _install_skill_sources, _provider_label_for_source, _skill_install_method_label
from cli.setup.skills_prompt import _prompt_install_skills
from cli.setup.skills_select import _select_skills_from_catalog, _select_suggested_sources
from cli.setup.wizard import setup_cmd
from cli.setup.wizard_steps import _clean_setup_option_defaults

__all__ = [
    "_boltz_cli_version", "_ensure_boltz_cli_installed_from_setup",
    "_find_boltz_cli_path", "_install_boltz_skill_from_setup", "_prompt_install_boltz_stack",
    "_prompt_boltz_api_key", "_prompt_fastfold_cloud_api_key",
    "_infer_openai_compatible_backend", "_prompt_openai_compatible_backend",
    "_resolve_openai_compatible_endpoint",
    "_find_compatible_profile_id_by_label", "_prompt_setup_compatible_profile_id",
    "_prompt_install_datasets", "_select_datasets_from_catalog",
    "_extract_discovery_error_message", "_ollama_tags_url_from_base",
    "_openai_models_url_from_base", "_read_http_error_body",
    "_report_discovery_exception", "_report_discovery_http_error", "_truncate_discovery_detail",
    "_fetch_compatible_models_for_setup", "_fetch_ollama_tags_for_setup", "_fetch_openai_models_for_setup",
    "_prompt_api_key", "_prompt_masked_secret", "_prompt_openai_api_key",
    "_prompt_openai_api_key_with_default", "_prompt_openai_compatible_api_key", "_prompt_provider_api_key",
    "_prompt_setup_mcps", "_prompt_compatible_model_for_setup",
    "_compatible_backend_display_name", "_compatible_default_endpoint",
    "_compatible_install_url", "_is_openai_managed_base_url",
    "_normalize_compatible_backend_name", "_normalize_openai_base_url",
    "_prompt_openai_endpoint_mode", "_resolve_openai_base_url",
    "_resolve_provider_key",
    "_parse_provider_list", "_prompt_setup_providers", "_setup_provider_runtime_id",
    "_prompt_setup_sandbox",
    "_install_skill_sources", "_provider_label_for_source", "_skill_install_method_label",
    "_prompt_install_skills",
    "_select_skills_from_catalog", "_select_suggested_sources",
    "setup_cmd", "_clean_setup_option_defaults",
]
