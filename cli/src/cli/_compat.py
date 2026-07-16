"""Flat backward-compatible re-exports (non-setup modules).

Historically all of ``cli.py`` lived in one module, so tests and scripts
import helpers directly off ``cli`` (e.g. ``cli.execute_upgrade``,
``cli.Session``). This module restores that flat namespace via ``import *``
from ``cli/__init__.py``; see ``cli/setup/_compat.py`` for the setup-wizard
half of the namespace.
"""
# ruff: noqa: I001 — hand-packed imports (kept compact to fit the line-count cap)

from agent.session import Session
from ui.terminal import SLASH_COMMANDS, InteractiveTerminal

from cli.agents_api import (
    _agents_api_get_json, _agents_api_request_json, _download_binary,
    _normalize_share_id, _parse_unix_timestamp, _resolve_agents_api_base_url,
    _safe_workspace_relative_path,
)
from cli.banner import print_banner
from cli.banner_support import (
    _count_installed_claude_skills, _get_cached_skills_update_safe,
    _get_loaded_tool_count_hint, _has_fastfold_skills_installed,
    _installed_claude_skill_names, _random_command_tip_markup,
    _random_news_item_markup, _start_skills_update_check,
)
from cli.config import config_get, config_set, config_show, config_unset, config_validate, keys_cmd
from cli.doctor import doctor_cmd
from cli.fork import fork_cmd
from cli.interactive import run_interactive
from cli.run_query import run_query
from cli.skills import add_skill_cmd, add_skills_cmd, skill_add, skill_install
from cli.skills_manage import skill_delete, skill_find, skill_info_cmd, skill_remove, skill_upgrade
from cli.subscription import (
    _format_plan_label, _resolve_fastfold_subscription_tier,
    _resolve_fastfold_subscription_tier_local,
)
from cli.trace_helpers import (
    _latest_report_path, _latest_trace_path, _print_trace_diagnostics_table,
    _resolve_trace_path, _run_step_command, _trace_has_issues,
)
from cli.upgrade import _maybe_offer_fastfold_skills_install_after_upgrade, execute_upgrade
from cli.version_check import (
    _get_cached_upgrade_available_version, _normalize_upgrade_flavor,
    _parse_semver_triplet, _start_upgrade_check_refresh, build_upgrade_command,
    fetch_pypi_latest_version, get_upgrade_available_version, is_newer_version,
    resolve_upgrade_flavor,
)

__all__ = [
    "Session", "SLASH_COMMANDS", "InteractiveTerminal",
    "_agents_api_get_json", "_agents_api_request_json", "_download_binary",
    "_normalize_share_id", "_parse_unix_timestamp", "_resolve_agents_api_base_url",
    "_safe_workspace_relative_path", "print_banner",
    "_count_installed_claude_skills", "_get_cached_skills_update_safe",
    "_get_loaded_tool_count_hint", "_has_fastfold_skills_installed",
    "_installed_claude_skill_names", "_random_command_tip_markup",
    "_random_news_item_markup", "_start_skills_update_check",
    "config_get", "config_set", "config_show", "config_unset", "config_validate", "keys_cmd",
    "doctor_cmd", "fork_cmd", "run_interactive", "run_query",
    "add_skill_cmd", "add_skills_cmd", "skill_add", "skill_install",
    "skill_delete", "skill_find", "skill_info_cmd", "skill_remove", "skill_upgrade",
    "_format_plan_label", "_resolve_fastfold_subscription_tier",
    "_resolve_fastfold_subscription_tier_local",
    "_latest_report_path", "_latest_trace_path", "_print_trace_diagnostics_table",
    "_resolve_trace_path", "_run_step_command", "_trace_has_issues",
    "_maybe_offer_fastfold_skills_install_after_upgrade", "execute_upgrade",
    "_get_cached_upgrade_available_version", "_normalize_upgrade_flavor",
    "_parse_semver_triplet", "_start_upgrade_check_refresh", "build_upgrade_command",
    "fetch_pypi_latest_version", "get_upgrade_available_version", "is_newer_version",
    "resolve_upgrade_flavor",
]
