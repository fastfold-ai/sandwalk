"""Config schema validation (types, ranges, interdependencies, unknown keys)."""

from __future__ import annotations

import re

from .defaults import DEFAULTS

# Custom (non-catalog) MCP servers store OAuth/headers/health under dynamic keys
# written by agent_server.mcp_service.custom_server / custom_headers / health_cache.
# These cannot be enumerated in DEFAULTS because the server id is a UUID.
_CUSTOM_MCP_KEY_RE = re.compile(
    r"^mcp\.custom_.+_("
    r"headers|access_token|refresh_token|token_expires_at|"
    r"token_endpoint|oauth_resource|"
    r"client_id|client_secret|tool_count|status_message"
    r")$"
)


def _is_known_config_key(key: str) -> bool:
    """True when *key* is a static DEFAULTS entry or a known dynamic MCP key."""
    if key in DEFAULTS:
        return True
    return bool(_CUSTOM_MCP_KEY_RE.match(key))


def _validate_config(config_dict: dict) -> list[str]:
    """Validate a config dict and return a list of warning/error messages.

    Checks:
    - Type correctness (numeric, bool, string)
    - Range validity (positive integers, minimums)
    - Interdependency warnings (pharma + quality_gate_strict)
    - Unknown keys (possible typos)
    """
    warnings: list[str] = []

    # --- Unknown keys ---
    for key in config_dict:
        if not _is_known_config_key(key):
            warnings.append(f"Unknown config key '{key}' (possible typo)")

    # --- Type checks ---
    for key, value in config_dict.items():
        if key not in DEFAULTS or value is None:
            continue
        default = DEFAULTS[key]
        if default is None:
            continue

        expected_type = type(default)
        if expected_type is bool:
            if not isinstance(value, bool):
                warnings.append(
                    f"Type error: '{key}' should be bool, got {type(value).__name__} ({value!r})"
                )
        elif expected_type is int:
            if not isinstance(value, (int, float)):
                warnings.append(
                    f"Type error: '{key}' should be int, got {type(value).__name__} ({value!r})"
                )
        elif expected_type is float:
            if not isinstance(value, (int, float)):
                warnings.append(
                    f"Type error: '{key}' should be float, got {type(value).__name__} ({value!r})"
                )
        elif expected_type is str:
            if not isinstance(value, str):
                warnings.append(
                    f"Type error: '{key}' should be str, got {type(value).__name__} ({value!r})"
                )

    # --- Range checks ---
    def _check_positive_int(key: str, label: str):
        val = config_dict.get(key)
        if val is not None and isinstance(val, (int, float)) and val <= 0:
            warnings.append(f"Range error: '{key}' ({label}) must be > 0, got {val}")

    def _check_min(key: str, minimum: int, label: str):
        val = config_dict.get(key)
        if val is not None and isinstance(val, (int, float)) and val < minimum:
            warnings.append(
                f"Range error: '{key}' ({label}) must be >= {minimum}, got {val}"
            )

    _check_positive_int("agent.max_iterations", "max iterations")
    _check_positive_int("agent.executor_max_retries", "executor max retries")
    _check_positive_int("agent.executor_loop_limit", "executor loop limit")
    _check_positive_int("agent.parallel_max_threads", "parallel max threads")
    _check_positive_int("agent.background_watch_timeout_s", "background watch timeout")
    _check_positive_int("agent.interrupt_drain_timeout_s", "interrupt drain timeout")
    _check_positive_int("agent.skills.max_catalog_entries", "skills catalog entries")
    _check_positive_int("agent.skills.max_active", "active skills")
    _check_positive_int("agent.skills.max_prompt_chars", "skills prompt character budget")
    _check_positive_int("agent.skills.catalog_description_chars", "skills catalog description chars")
    _check_positive_int("agent.skills.index_snippet_chars", "skills index snippet chars")
    _check_min("agent.synthesis_max_tokens", 512, "synthesis max tokens")
    _check_min("sandbox.timeout", 1, "sandbox timeout")

    backend = str(config_dict.get("sandbox.backend") or "builtin").strip().lower()
    if backend not in {"builtin", "modal"}:
        warnings.append(
            "Invalid sandbox.backend (expected 'builtin' or 'modal'): "
            f"{config_dict.get('sandbox.backend')!r}"
        )
    cli_sandbox = config_dict.get("agent.cli_sandbox")
    if cli_sandbox is not None and str(cli_sandbox).strip() != "":
        cli_backend = str(cli_sandbox).strip().lower()
        if cli_backend not in {"builtin", "modal"}:
            warnings.append(
                "Invalid agent.cli_sandbox (expected 'builtin' or 'modal'): "
                f"{cli_sandbox!r}"
            )
    compute_type = str(config_dict.get("sandbox.compute_type") or "cpu").strip().lower()
    if compute_type not in {"cpu", "gpu"}:
        warnings.append(
            "Invalid sandbox.compute_type (expected 'cpu' or 'gpu'): "
            f"{config_dict.get('sandbox.compute_type')!r}"
        )
    _check_min("sandbox.idle_ttl_seconds", 60, "sandbox idle TTL")
    _check_min("sandbox.cpu_cores", 0.25, "sandbox CPU cores")
    _check_min("sandbox.ram_gb", 0.5, "sandbox RAM GB")

    # --- Interdependency checks ---
    profile = config_dict.get("agent.profile")
    if profile == "pharma":
        qg_strict = config_dict.get(
            "agent.quality_gate_strict",
            DEFAULTS.get("agent.quality_gate_strict"),
        )
        if qg_strict is False or qg_strict == 0:
            warnings.append(
                "Interdependency warning: profile is 'pharma' but "
                "agent.quality_gate_strict is false (recommended: true)"
            )

    return warnings
