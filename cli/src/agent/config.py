"""
Configuration management for ct.

Config is stored at ~/.fastfold-cli/config.json and manages:
- LLM provider settings (Anthropic, OpenAI, local models)
- Data directory paths (DepMap, PRISM, etc.)
- Output preferences
- Tool-specific settings
"""

import json
import os
import logging
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

# Load .env from current dir and project root
load_dotenv()
load_dotenv(Path(__file__).resolve().parents[3] / ".env")  # repo root

from rich.table import Table  # noqa: E402

CONFIG_DIR = Path.home() / ".fastfold-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"
CONFIG_BACKUP_FILE = CONFIG_DIR / "config.json.bak"
VALID_LLM_PROVIDERS = frozenset(
    {"anthropic", "openai", "xai", "google", "nvidia", "opencode"}
)

# First-party providers that speak the OpenAI-compatible protocol. Each routes
# through the OpenAI SDK / LangChain "openai:" path with a fixed base URL and its
# own API key. Set discover_models=true to fetch the live catalog from /v1/models
# when an API key is configured (used by OpenCode Go).
OPENAI_COMPATIBLE_PROVIDERS: dict[str, dict[str, str]] = {
    "xai": {
        "base_url": "https://api.x.ai/v1",
        "config_key": "llm.xai_api_key",
        "env_var": "XAI_API_KEY",
        "label": "xAI",
        "signup_url": "https://console.x.ai",
        "default_model": "grok-4.5",
    },
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "config_key": "llm.google_api_key",
        "env_var": "GEMINI_API_KEY",
        "label": "Google Gemini",
        "signup_url": "https://aistudio.google.com/apikey",
        "default_model": "gemini-3.5-flash",
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "config_key": "api.nvidia_api_key",
        "env_var": "NVIDIA_API_KEY",
        "label": "NVIDIA",
        "signup_url": "https://build.nvidia.com/settings/api-keys",
        "default_model": "nvidia/nemotron-3-ultra-550b-a55b",
    },
    "opencode": {
        "base_url": "https://opencode.ai/zen/v1",
        "config_key": "llm.opencode_api_key",
        "env_var": "OPENCODE_API_KEY",
        "label": "OpenCode Zen",
        "signup_url": "https://opencode.ai/zen",
        "default_model": "kimi-k2.7-code",
        "discover_models": "true",
    },
}
logger = logging.getLogger("config")
OPENAI_API_KEY_PATTERN = re.compile(r"^sk-[A-Za-z0-9_-]{6,}$")
ANTHROPIC_API_KEY_PATTERN = re.compile(r"^sk-ant-[A-Za-z0-9_-]{6,}$")
OPENAI_PROFILE_BACKENDS = frozenset(
    {"openai", "ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}
)
OPENAI_PROFILE_DEFAULTS = {
    "openai": {
        "label": "OpenAI Cloud",
        "base_url": "https://api.openai.com/v1",
        "discovery": ["v1_models"],
        "default_model": "gpt-5.5",
        "install_url": "https://platform.openai.com/api-keys",
    },
    "ollama": {
        "label": "Ollama Local",
        "base_url": "http://localhost:11434/v1",
        "discovery": ["ollama_tags", "v1_models"],
        "default_model": "llama3.1",
        "install_url": "https://github.com/ollama/ollama",
    },
    "unsloth": {
        "label": "Unsloth Local",
        "base_url": "http://localhost:8888/v1",
        "discovery": ["v1_models"],
        "default_model": "gpt-oss",
        "install_url": "https://github.com/unslothai/unsloth",
    },
    "omlx": {
        "label": "oMLX Local",
        "base_url": "http://localhost:8000/v1",
        "discovery": ["v1_models"],
        "default_model": "diffusiongemma-26B-A4B-it-4bit",
        "install_url": "https://github.com/jundot/omlx",
    },
    "ds4": {
        "label": "DS4 Local",
        "base_url": "http://localhost:8000/v1",
        "discovery": ["v1_models"],
        "default_model": "deepseek-v4-flash",
        "install_url": "https://github.com/antirez/ds4",
    },
    "llama_cpp": {
        "label": "llama.cpp Local",
        "base_url": "http://localhost:8080/v1",
        "discovery": ["v1_models"],
        "default_model": "llama3.1",
        "install_url": "https://github.com/ggml-org/llama.cpp",
    },
    "lm_studio": {
        "label": "LM Studio Local",
        "base_url": "http://localhost:1234/v1",
        "discovery": ["v1_models"],
        "default_model": "llama3.1",
        "install_url": "https://lmstudio.ai/docs/developer/openai-compat",
    },
    "other": {
        "label": "Custom Compatible Endpoint",
        "base_url": "http://localhost:11434/v1",
        "discovery": ["v1_models", "ollama_tags"],
        "default_model": "llama3.1",
        "install_url": "",
    },
}
_UNSET = object()

_LEGACY_DIR = Path.home() / ".ct"


def _migrate_legacy_config() -> None:
    """One-time migration: copy ~/.ct/ → ~/.fastfold-cli/ for existing users."""
    if not _LEGACY_DIR.exists():
        return
    import shutil
    # Walk legacy tree and copy any file not already present in new location
    for src in _LEGACY_DIR.rglob("*"):
        if not src.is_file():
            continue
        relative = src.relative_to(_LEGACY_DIR)
        dest = CONFIG_DIR / relative
        if dest.exists():
            continue
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            logger.info("Migrated %s → %s", src, dest)
        except Exception as exc:
            logger.warning("Could not migrate %s: %s", src, exc)


_migrate_legacy_config()

DEFAULTS = {
    "llm.provider": "anthropic",
    "llm.model": "claude-sonnet-4-5-20250929",
    "llm.anthropic_api_key": None,
    "llm.api_key": None,
    "llm.openai_api_key": None,
    "llm.xai_api_key": None,
    "llm.google_api_key": None,
    "llm.opencode_api_key": None,
    "llm.openai_compatible_api_key": None,
    "llm.openai_base_url": None,
    "llm.openai_compatible_backend": None,
    "llm.openai_profiles": None,
    "llm.openai_active_profile": None,
    "llm.openai_default_profile": None,
    "llm.hidden_models": [],
    "llm.custom_models": [],
    "llm.catalog_defaults_version": 0,
    "llm.temperature": 0.1,
    "agent.hidden_tools": [],

    "data.base": str(CONFIG_DIR / "data"),
    "data.depmap": None,
    "data.prism": None,
    "data.l1000": None,
    "data.msigdb": None,
    "data.alphafold": None,
    "data.string": None,
    "data.proteomics": None,

    "api.data_endpoint": None,
    "api.clue_key": None,
    "api.fastfold_cloud_key": None,
    "api.boltz_api_key": None,
    "api.nvidia_api_key": None,
    "api.tavily_api_key": None,
    "api.langsmith_api_key": None,
    "api.langsmith_project": None,
    "api.vercel_oidc_token": None,
    "mcp.tamarind_api_key": None,
    "mcp.neurosnap_api_key": None,
    "mcp.linear_api_key": None,
    "mcp.tamarind_tool_count": None,
    "mcp.neurosnap_tool_count": None,
    "mcp.latch_tool_count": None,
    "mcp.linear_tool_count": None,
    "mcp.tamarind_status_message": None,
    "mcp.neurosnap_status_message": None,
    "mcp.latch_status_message": None,
    "mcp.linear_status_message": None,
    "mcp.tamarind_access_token": None,
    "mcp.tamarind_refresh_token": None,
    "mcp.tamarind_token_expires_at": None,
    "mcp.tamarind_client_id": None,
    "mcp.tamarind_client_secret": None,
    "mcp.latch_access_token": None,
    "mcp.latch_refresh_token": None,
    "mcp.latch_token_expires_at": None,
    "mcp.latch_client_id": None,
    "mcp.latch_client_secret": None,
    "mcp.linear_access_token": None,
    "mcp.linear_refresh_token": None,
    "mcp.linear_token_expires_at": None,
    "mcp.linear_client_id": None,
    "mcp.linear_client_secret": None,
    "compute.modal_token_id": None,
    "compute.modal_token_secret": None,
    "notification.slack_bot_token": None,
    "notification.webhook_url": None,
    "notification.webhook_secret": None,
    "fastfold.subscription_tier": None,

    "output.format": "markdown",
    "output.verbose": False,
    "output.auto_publish_html_interactive": True,
    "output.auto_publish_html_batch": False,

    "ui.spinner": "benzene_breathing",
    "ui.mermaid.enabled": True,
    "ui.mermaid.ascii": False,
    "ui.mermaid.theme": "default",

    "models.deepternary": None,
    "models.boltz2": None,

    "api.ibm_rxn_key": None,
    "api.lens_key": None,

    "notification.sendgrid_api_key": None,
    "notification.from_email": None,
    "notification.auto_send": False,

    "compute.lambda_api_key": None,
    "compute.runpod_api_key": None,
    "compute.default_provider": "lambda",

    "sandbox.timeout": 30,
    "sandbox.output_dir": str(Path.cwd() / "outputs"),
    "sandbox.max_retries": 2,

    "agent.max_iterations": 3,
    # Tool-calling strategy for the deepagents runtime: "ptc" (Programmatic Tool
    # Calling, default — domain tools are injected as Python callables inside
    # run_python and the model invokes them in code, with only a compact catalog
    # + search_tools in context) or "native" (each domain tool exposed as its own
    # LangChain tool schema). PTC significantly reduces per-call input tokens and
    # removes the OpenAI tool-count ceiling. Set to "native" to restore per-tool
    # schemas.
    "agent.tool_mode": "ptc",
    # Tool-call rendering (deepagents runtime only). When True, the most recent
    # `agent.tool_trace_detail_limit` tool calls in a consecutive batch stay in
    # full detail (name, args, output) and older ones collapse progressively to a
    # one-line, still named "✓ name (Xs)" entry as newer calls complete — the
    # current/last call stays detailed while earlier ones compact away. Errors
    # always show in full. Set False to show every tool call fully verbose.
    "agent.group_tool_traces": True,
    # Trailing window: how many most-recent tool calls keep full detail before
    # older ones collapse to compact named lines. 1 = only the last call full.
    "agent.tool_trace_detail_limit": 1,
    "agent.enable_experimental_tools": False,
    "skills.allow_agent_install": False,
    "agent.observer_model": None,
    "agent.executor_max_retries": 2,
    "agent.executor_loop_limit": 50,
    "agent.observer_confidence_threshold": 0.8,
    "agent.synthesis_max_tokens": 8192,
    "agent.enforce_grounded_synthesis": True,
    "agent.enforce_claim_content_validation": True,
    "agent.confidence_scoring_enabled": True,
    "agent.min_step_success_rate": 0.5,
    "agent.require_key_evidence_section": True,
    "agent.allow_creative_hypotheses": True,
    "agent.max_hypotheses": 3,
    "agent.grounding_repair_retries": 1,
    "agent.log_evidence_store": True,
    "agent.memory_retrieval_enabled": True,
    "agent.memory_retrieval_limit": 3,
    "agent.verifier_model": None,
    "agent.verifier_provider": None,
    "agent.verifier_repair_retries": 1,
    "agent.quality_gate_enabled": True,
    "agent.quality_gate_strict": False,
    "agent.quality_gate_repair_retries": 1,
    "agent.quality_gate_repair_non_strict": False,
    "agent.quality_gate_min_next_steps": 2,
    "agent.quality_gate_max_next_steps": 3,
    "agent.synthesis_style": "standard",
    "agent.profile": "research",
    "agent.enable_claude_code_tool": False,
    "agent.parallel_default_count": 3,
    "agent.parallel_auto_suggest": True,
    "agent.parallel_max_threads": 5,
    "agent.background_watch_timeout_s": 7200,
    "agent.interrupt_drain_timeout_s": 10,
    "agent.planner_max_tools": 90,
    "agent.planner_compact_tool_descriptions": True,
    "agent.tool_health_enabled": True,
    "agent.tool_health_fail_threshold": 2,
    "agent.tool_health_failure_window_s": 1800,
    "agent.tool_health_suppress_seconds": 900,
    "agent.preflight_validation_enabled": True,
    "agent.skills.max_catalog_entries": 250,
    "agent.skills.max_active": 6,
    "agent.skills.max_prompt_chars": 120000,
    "agent.skills.catalog_description_chars": 140,
    "agent.skills.index_snippet_chars": 8000,

    "enterprise.enforce_policy": False,
    "enterprise.audit_enabled": True,
    "enterprise.audit_dir": str(Path.home() / ".fastfold-cli" / "audit"),
    "enterprise.blocked_tools": "",
    "enterprise.blocked_categories": "",
    "enterprise.require_tool_allowlist": False,
    "enterprise.tool_allowlist": "",
    "enterprise.max_cost_usd_per_query": 0.0,

    "knowledge.enable_substrate": True,
    "knowledge.auto_ingest_evidence": True,
    "knowledge.substrate_path": str(Path.home() / ".fastfold-cli" / "knowledge" / "substrate.json"),
    "knowledge.schema_monitor_enabled": False,

    "ops.base_dir": str(Path.home() / ".fastfold-cli" / "ops"),
    "install.uv_flavor": None,
}

AGENT_PROFILE_PRESETS = {
    "research": {
        "agent.enforce_grounded_synthesis": True,
        "agent.enforce_claim_content_validation": True,
        "agent.require_key_evidence_section": True,
        "agent.allow_creative_hypotheses": True,
        "agent.quality_gate_enabled": True,
        "agent.quality_gate_strict": False,
        "agent.quality_gate_repair_retries": 1,
        "agent.quality_gate_repair_non_strict": False,
        "agent.synthesis_style": "standard",
        "agent.memory_retrieval_enabled": True,
        "agent.enable_claude_code_tool": False,
        "enterprise.enforce_policy": False,
        "enterprise.blocked_tools": "",
        "enterprise.blocked_categories": "",
        "enterprise.require_tool_allowlist": False,
    },
    "enterprise": {
        "agent.enforce_grounded_synthesis": True,
        "agent.enforce_claim_content_validation": True,
        "agent.require_key_evidence_section": True,
        "agent.allow_creative_hypotheses": False,
        "agent.quality_gate_enabled": True,
        "agent.quality_gate_strict": True,
        "agent.quality_gate_repair_retries": 2,
        "agent.quality_gate_repair_non_strict": True,
        "agent.synthesis_style": "standard",
        "agent.memory_retrieval_enabled": True,
        "agent.enable_claude_code_tool": False,
        "enterprise.enforce_policy": True,
        "enterprise.blocked_tools": "shell.run,files.delete_file,claude.code",
        "enterprise.blocked_categories": "",
        "enterprise.require_tool_allowlist": False,
    },
    "pharma": {
        "agent.enforce_grounded_synthesis": True,
        "agent.enforce_claim_content_validation": True,
        "agent.require_key_evidence_section": True,
        "agent.allow_creative_hypotheses": False,
        "agent.quality_gate_enabled": True,
        "agent.quality_gate_strict": True,
        "agent.quality_gate_repair_retries": 2,
        "agent.quality_gate_repair_non_strict": True,
        "agent.quality_gate_min_next_steps": 3,
        "agent.quality_gate_max_next_steps": 3,
        "agent.synthesis_style": "pharma",
        "agent.memory_retrieval_enabled": True,
        "agent.enable_claude_code_tool": False,
        "enterprise.enforce_policy": False,
        "enterprise.blocked_tools": "",
        "enterprise.blocked_categories": "",
        "enterprise.require_tool_allowlist": False,
    },
}


API_KEYS = {
    "llm.anthropic_api_key": {
        "name": "Anthropic",
        "env_var": "ANTHROPIC_API_KEY",
        "description": "Anthropic/Claude model access (default provider)",
        "url": "https://console.anthropic.com/settings/keys",
        "free": False,
    },
    "llm.openai_api_key": {
        "name": "OpenAI",
        "env_var": "OPENAI_API_KEY",
        "description": "OpenAI model access (when llm.provider=openai)",
        "url": "https://platform.openai.com/api-keys",
        "free": False,
    },
    "llm.xai_api_key": {
        "name": "xAI",
        "provider_key": "xai",
        "env_var": "XAI_API_KEY",
        "description": "xAI Grok model access",
        "url": "https://console.x.ai",
        "free": False,
    },
    "llm.google_api_key": {
        "name": "Google Gemini",
        "provider_key": "google",
        "env_var": "GEMINI_API_KEY",
        "description": "Google Gemini (AI Studio) model access",
        "url": "https://aistudio.google.com/apikey",
        "free": True,
    },
    "llm.opencode_api_key": {
        "name": "OpenCode Zen",
        "provider_key": "opencode",
        "env_var": "OPENCODE_API_KEY",
        "description": "OpenCode Zen gateway for curated coding models (pay-as-you-go)",
        "url": "https://opencode.ai/zen",
        "free": False,
    },
    "llm.openai_compatible_api_key": {
        "name": "OpenAI-compatible",
        "env_var": "OPENAI_COMPATIBLE_API_KEY",
        "description": "Custom OpenAI-compatible endpoints (Ollama/Unsloth/oMLX/DS4/llama.cpp/LM Studio/proxy)",
        "url": "https://docs.ollama.com/api/introduction",
        "free": True,
    },
    "api.ibm_rxn_key": {
        "name": "IBM RXN",
        "env_var": "IBM_RXN_API_KEY",
        "description": "AI-powered retrosynthesis (chemistry.retrosynthesis)",
        "url": "https://rxn.res.ibm.com",
        "free": True,
    },
    "api.lens_key": {
        "name": "Lens.org",
        "env_var": "LENS_API_KEY",
        "description": "Patent search (literature.patent_search)",
        "url": "https://www.lens.org/lens/user/subscriptions",
        "free": True,
    },
    "api.fastfold_cloud_key": {
        "name": "Fastfold AI Cloud",
        "env_var": "FASTFOLD_API_KEY",
        "description": "Fastfold cloud skills and integrations",
        "url": "https://cloud.fastfold.ai/api-keys",
        "free": False,
    },
    "api.boltz_api_key": {
        "name": "Boltz",
        "env_var": "BOLTZ_API_KEY",
        "description": "Boltz structure/binding, design, and screening skills",
        "url": "https://api.boltz.bio/console",
        "free": False,
    },
    "api.nvidia_api_key": {
        "name": "NVIDIA",
        "provider_key": "nvidia",
        "env_var": "NVIDIA_API_KEY",
        "description": "NVIDIA model inference and NIM endpoints",
        "url": "https://build.nvidia.com/settings/api-keys",
        "free": False,
    },
    "api.tavily_api_key": {
        "name": "Tavily",
        "provider_key": "tavily",
        "env_var": "TAVILY_API_KEY",
        "description": "Web search for research workflows",
        "url": "https://app.tavily.com/home",
        "free": True,
    },
    "api.langsmith_api_key": {
        "name": "LangSmith",
        "provider_key": "langsmith",
        "env_var": "LANGSMITH_API_KEY",
        "description": "LangChain tracing and observability",
        "url": "https://smith.langchain.com/settings",
        "free": True,
    },
    "api.langsmith_project": {
        "name": "LangSmith Project",
        "provider_key": "langsmith",
        "env_var": "LANGSMITH_PROJECT",
        "description": "LangSmith tracing project",
        "url": "https://smith.langchain.com/settings",
        "free": True,
        "secret": False,
    },
    "api.vercel_oidc_token": {
        "name": "Vercel OIDC Token",
        "provider_key": "skills-sh",
        "env_var": "VERCEL_OIDC_TOKEN",
        "description": "skills.sh auth token provided by Vercel OIDC Federation",
        "url": "https://vercel.com/dashboard",
        "free": True,
    },
    "compute.modal_token_id": {
        "name": "Modal Token ID",
        "provider_key": "modal",
        "env_var": "MODAL_TOKEN_ID",
        "description": "Modal runtime credential ID",
        "url": "https://modal.com/settings/tokens",
        "free": True,
        "secret": False,
    },
    "compute.modal_token_secret": {
        "name": "Modal Token Secret",
        "provider_key": "modal",
        "env_var": "MODAL_TOKEN_SECRET",
        "description": "Modal runtime credential secret",
        "url": "https://modal.com/settings/tokens",
        "free": True,
    },
    "notification.slack_bot_token": {
        "name": "Slack",
        "provider_key": "slack",
        "env_var": "SLACK_BOT_TOKEN",
        "description": "Slack reports and agent notifications",
        "url": "https://api.slack.com/apps",
        "free": True,
    },
    "notification.webhook_url": {
        "name": "Custom Webhook URL",
        "provider_key": "custom-webhook",
        "env_var": "FASTFOLD_WEBHOOK_URL",
        "description": "Completion event webhook destination",
        "url": "",
        "free": True,
        "secret": False,
    },
    "notification.webhook_secret": {
        "name": "Custom Webhook Secret",
        "provider_key": "custom-webhook",
        "env_var": "FASTFOLD_WEBHOOK_SECRET",
        "description": "Completion webhook signing secret",
        "url": "",
        "free": True,
    },
    "notification.sendgrid_api_key": {
        "name": "SendGrid",
        "env_var": "SENDGRID_API_KEY",
        "description": "Email sending (notification.send_email)",
        "url": "https://sendgrid.com",
        "free": True,
    },
    "compute.lambda_api_key": {
        "name": "Lambda Labs",
        "env_var": "LAMBDA_API_KEY",
        "description": "GPU compute jobs (compute.submit_job)",
        "url": "https://cloud.lambdalabs.com",
        "free": False,
    },
    "compute.runpod_api_key": {
        "name": "RunPod",
        "env_var": "RUNPOD_API_KEY",
        "description": "GPU compute jobs (compute.submit_job)",
        "url": "https://www.runpod.io",
        "free": False,
    },
    "mcp.tamarind_api_key": {
        "name": "Tamarind Bio",
        "provider_key": "tamarind",
        "env_var": "TAMARIND_API_KEY",
        "description": "Tamarind MCP API key (x-api-key) for protein design / structure jobs",
        "url": "https://app.tamarind.bio",
        "free": False,
    },
    "mcp.neurosnap_api_key": {
        "name": "Neurosnap",
        "provider_key": "neurosnap",
        "env_var": "NEUROSNAP_API_KEY",
        "description": "Neurosnap MCP API key (Bearer) for computational biology jobs",
        "url": "https://neurosnap.ai/overview?view=api",
        "free": True,
    },
    "mcp.linear_api_key": {
        "name": "Linear",
        "provider_key": "linear",
        "env_var": "LINEAR_API_KEY",
        "description": "Linear MCP API key (Bearer) for issues and projects",
        "url": "https://linear.app/settings/account/security",
        "free": True,
    },
}


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
    known_keys = set(DEFAULTS.keys())
    for key in config_dict:
        if key not in known_keys:
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


class Config:
    """ct configuration manager."""

    @staticmethod
    def _normalize_openai_base_url(value: Any) -> Optional[str]:
        """Normalize OpenAI-compatible base URLs for consistent comparisons."""
        text = Config._normalized_secret(value)
        if not text:
            return None
        return text.rstrip("/")

    @staticmethod
    def _normalize_compatible_backend_name(value: Any) -> str:
        """Normalize backend aliases to canonical compatible backend ids."""
        text = str(value or "").strip().lower()
        aliases = {
            "ollama": "ollama",
            "unsloth": "unsloth",
            "omlx": "omlx",
            "ds4": "ds4",
            "deepseek": "ds4",
            "deepseek-v4": "ds4",
            "deepseek_4": "ds4",
            "llama.cpp": "llama_cpp",
            "llama_cpp": "llama_cpp",
            "llama-cpp": "llama_cpp",
            "llamacpp": "llama_cpp",
            "lmstudio": "lm_studio",
            "lm_studio": "lm_studio",
            "lm-studio": "lm_studio",
            "lm studio": "lm_studio",
            "custom": "other",
            "generic": "other",
            "other": "other",
            "openai": "openai",
        }
        return aliases.get(text, text)

    @staticmethod
    def infer_openai_compatible_backend(base_url: Optional[str], api_key: Optional[str] = None) -> str:
        """Infer OpenAI-compatible backend type from endpoint and key hints."""
        endpoint = str(base_url or "").strip().lower()
        secret = str(api_key or "").strip().lower()
        if secret.startswith("sk-unsloth-") or "8888" in endpoint:
            return "unsloth"
        if (
            secret.startswith("dsv4-")
            or secret.startswith("sk-ds4-")
            or "deepseek-v4" in endpoint
            or "deepseek4" in endpoint
            or "ds4" in endpoint
        ):
            return "ds4"
        if "1234" in endpoint or "lmstudio" in endpoint or "lm-studio" in endpoint:
            return "lm_studio"
        if (
            "8080" in endpoint
            or "llama.cpp" in endpoint
            or "llama-cpp" in endpoint
            or "llamacpp" in endpoint
        ):
            return "llama_cpp"
        if secret.startswith("sk-omlx-") or "omlx" in endpoint:
            return "omlx"
        if "11434" in endpoint or "ollama" in endpoint:
            return "ollama"
        # Keep legacy 8000-port inference for oMLX profiles without explicit hints.
        if "8000" in endpoint:
            return "omlx"
        return "other"

    @staticmethod
    def _infer_backend_from_model_name(model_id: Optional[str]) -> Optional[str]:
        """Infer backend from model id hints when endpoint is unavailable."""
        model_name = str(model_id or "").strip().lower()
        if not model_name:
            return None
        if (
            "deepseek-v4" in model_name
            or model_name.startswith("deepseek-v4")
            or model_name.startswith("ds4")
        ):
            return "ds4"
        if "omlx" in model_name:
            return "omlx"
        if "unsloth" in model_name:
            return "unsloth"
        if model_name.startswith("llama") or model_name.startswith("qwen") or model_name.startswith("phi"):
            return "ollama"
        return None

    @staticmethod
    def _looks_like_anthropic_model(model_id: Optional[str]) -> bool:
        """Best-effort check for Anthropic model identifiers."""
        value = str(model_id or "").strip().lower()
        return value.startswith("claude-")

    @staticmethod
    def _looks_like_openai_cloud_model(model_id: Optional[str]) -> bool:
        """Best-effort check for OpenAI cloud model identifiers."""
        value = str(model_id or "").strip().lower()
        if not value:
            return False
        if value.startswith("gpt-oss"):
            return False
        return (
            value.startswith("gpt-4")
            or value.startswith("gpt-5")
            or value.startswith("o1")
            or value.startswith("o3")
            or value.startswith("chatgpt")
        )

    @staticmethod
    def _slugify_profile_id(value: str) -> str:
        """Create stable profile IDs from labels."""
        normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
        return normalized or "profile"

    @classmethod
    def _unique_profile_id(cls, base_id: str, existing: dict[str, dict]) -> str:
        """Return a unique profile id using numeric suffixes when required."""
        candidate = cls._slugify_profile_id(base_id)
        if candidate not in existing:
            return candidate
        idx = 2
        while f"{candidate}_{idx}" in existing:
            idx += 1
        return f"{candidate}_{idx}"

    @classmethod
    def _normalize_discovery_sequence(cls, backend: str, value: Any) -> list[str]:
        """Normalize model discovery strategies for profile records."""
        allowed = {"v1_models", "ollama_tags"}
        if isinstance(value, list):
            parsed = [str(item or "").strip().lower() for item in value]
            filtered = [item for item in parsed if item in allowed]
            if filtered:
                deduped: list[str] = []
                for item in filtered:
                    if item not in deduped:
                        deduped.append(item)
                return deduped
        default_seq = OPENAI_PROFILE_DEFAULTS.get(backend, OPENAI_PROFILE_DEFAULTS["other"]).get("discovery", [])
        return [str(item) for item in default_seq]

    @classmethod
    def _normalize_profile_record(cls, profile_id: str, raw: Any) -> dict[str, Any]:
        """Normalize an OpenAI profile record with backend defaults."""
        payload = raw if isinstance(raw, dict) else {}
        backend = cls._normalize_compatible_backend_name(payload.get("backend"))
        if backend not in OPENAI_PROFILE_BACKENDS:
            backend = cls.infer_openai_compatible_backend(payload.get("base_url"), payload.get("api_key"))
        if profile_id == "openai_cloud":
            backend = "openai"

        defaults = OPENAI_PROFILE_DEFAULTS.get(backend, OPENAI_PROFILE_DEFAULTS["other"])

        label_raw = str(payload.get("label") or "").strip()
        label = label_raw or str(defaults.get("label") or "OpenAI Profile")

        base_url = cls._normalize_openai_base_url(payload.get("base_url")) or str(defaults.get("base_url") or "")
        if backend == "openai":
            if not cls._is_openai_managed_base_url(base_url):
                base_url = str(OPENAI_PROFILE_DEFAULTS["openai"]["base_url"])
        else:
            if cls._is_openai_managed_base_url(base_url):
                base_url = str(defaults.get("base_url") or OPENAI_PROFILE_DEFAULTS["other"]["base_url"])

        default_model_raw = str(payload.get("default_model") or "").strip()
        default_model = default_model_raw or str(defaults.get("default_model") or "")

        return {
            "label": label,
            "backend": backend,
            "base_url": base_url.rstrip("/"),
            "api_key": cls._normalized_secret(payload.get("api_key")),
            "discovery": cls._normalize_discovery_sequence(backend, payload.get("discovery")),
            "default_model": default_model,
        }

    @classmethod
    def _ensure_openai_profiles_data(
        cls,
        data: dict[str, Any],
        *,
        apply_legacy_compat: bool = True,
    ) -> tuple[dict[str, dict[str, Any]], str, str]:
        """Ensure profile schema exists and migrate legacy OpenAI-compatible fields."""
        profiles: dict[str, dict[str, Any]] = {}
        raw_profiles = data.get("llm.openai_profiles")
        if isinstance(raw_profiles, dict):
            for raw_profile_id, raw_profile in raw_profiles.items():
                profile_id = cls._slugify_profile_id(raw_profile_id)
                profile_id = cls._unique_profile_id(profile_id, profiles)
                profiles[profile_id] = cls._normalize_profile_record(profile_id, raw_profile)

        # Always keep a cloud profile available.
        if "openai_cloud" not in profiles:
            profiles["openai_cloud"] = cls._normalize_profile_record(
                "openai_cloud",
                {
                    "label": "OpenAI Cloud",
                    "backend": "openai",
                    "base_url": OPENAI_PROFILE_DEFAULTS["openai"]["base_url"],
                    "api_key": cls._normalized_secret(data.get("llm.openai_api_key")),
                    "default_model": OPENAI_PROFILE_DEFAULTS["openai"]["default_model"],
                    "discovery": OPENAI_PROFILE_DEFAULTS["openai"]["discovery"],
                },
            )
        else:
            openai_key = cls._normalized_secret(data.get("llm.openai_api_key"))
            if openai_key and not profiles["openai_cloud"].get("api_key"):
                profiles["openai_cloud"]["api_key"] = openai_key

        # Migrate legacy single-slot compatible configuration into profiles.
        legacy_base_url = cls._normalize_openai_base_url(data.get("llm.openai_base_url"))
        legacy_backend = cls._normalize_compatible_backend_name(
            data.get("llm.openai_compatible_backend")
        )
        legacy_key = cls._normalized_secret(data.get("llm.openai_compatible_api_key"))
        if legacy_backend not in OPENAI_PROFILE_BACKENDS:
            legacy_backend = cls.infer_openai_compatible_backend(legacy_base_url, legacy_key)
        if apply_legacy_compat and legacy_base_url and not cls._is_openai_managed_base_url(legacy_base_url):
            profile_match_id = None
            for existing_id, existing_profile in profiles.items():
                existing_url = cls._normalize_openai_base_url(existing_profile.get("base_url"))
                if existing_profile.get("backend") != "openai" and existing_url == legacy_base_url:
                    profile_match_id = existing_id
                    break
            if not profile_match_id:
                base_candidate = f"{legacy_backend or 'compatible'}_profile"
                profile_match_id = cls._unique_profile_id(base_candidate, profiles)
                profiles[profile_match_id] = cls._normalize_profile_record(
                    profile_match_id,
                    {
                        "label": str(
                            OPENAI_PROFILE_DEFAULTS.get(legacy_backend, OPENAI_PROFILE_DEFAULTS["other"]).get("label")
                            or "Compatible Endpoint"
                        ),
                        "backend": legacy_backend,
                        "base_url": legacy_base_url,
                        "api_key": legacy_key,
                        "default_model": data.get("llm.model"),
                    },
                )
            else:
                updated = dict(profiles[profile_match_id])
                if legacy_backend and legacy_backend in OPENAI_PROFILE_BACKENDS:
                    updated["backend"] = legacy_backend
                if legacy_key:
                    updated["api_key"] = legacy_key
                updated["base_url"] = legacy_base_url
                profiles[profile_match_id] = cls._normalize_profile_record(profile_match_id, updated)
            if "llm.openai_active_profile" not in data and str(data.get("llm.provider") or "").strip().lower() == "openai":
                data["llm.openai_active_profile"] = profile_match_id

        # Bootstrap compatible profile from legacy key/model hints when endpoint
        # is missing but users likely intended an OpenAI-compatible provider.
        has_compatible_profiles = any(
            str(profile.get("backend") or "").strip().lower() != "openai"
            for profile in profiles.values()
        )
        configured_model = str(data.get("llm.model") or "").strip()
        provider_raw = str(data.get("llm.provider") or "").strip().lower()
        if apply_legacy_compat and not has_compatible_profiles and legacy_key:
            bootstrap_backend = (
                legacy_backend
                if legacy_backend in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}
                else "other"
            )
            inferred_model_backend = cls._infer_backend_from_model_name(configured_model)
            if inferred_model_backend:
                bootstrap_backend = inferred_model_backend
            bootstrap_defaults = OPENAI_PROFILE_DEFAULTS.get(bootstrap_backend, OPENAI_PROFILE_DEFAULTS["other"])
            bootstrap_id = cls._unique_profile_id(f"{bootstrap_backend}_legacy", profiles)
            profiles[bootstrap_id] = cls._normalize_profile_record(
                bootstrap_id,
                {
                    "label": str(bootstrap_defaults.get("label") or "Compatible Endpoint"),
                    "backend": bootstrap_backend,
                    "base_url": str(bootstrap_defaults.get("base_url") or "http://localhost:11434/v1"),
                    "api_key": legacy_key,
                    "default_model": configured_model,
                    "discovery": bootstrap_defaults.get("discovery"),
                },
            )
            if (
                "llm.openai_active_profile" not in data
                or provider_raw == "openai"
                or (configured_model and not cls._looks_like_anthropic_model(configured_model))
            ):
                data["llm.openai_active_profile"] = bootstrap_id

        default_profile = cls._slugify_profile_id(str(data.get("llm.openai_default_profile") or "").strip())
        if default_profile not in profiles:
            default_profile = "openai_cloud"

        active_profile = cls._slugify_profile_id(str(data.get("llm.openai_active_profile") or "").strip())
        if active_profile not in profiles:
            active_profile = default_profile
            if legacy_base_url and not cls._is_openai_managed_base_url(legacy_base_url):
                for existing_id, existing_profile in profiles.items():
                    if cls._normalize_openai_base_url(existing_profile.get("base_url")) == legacy_base_url:
                        active_profile = existing_id
                        break

        # Heal provider/model mismatch: if provider says Anthropic but model
        # clearly targets a compatible backend, prefer openai provider.
        compatible_profile_ids = [
            profile_id
            for profile_id, profile in profiles.items()
            if str(profile.get("backend") or "").strip().lower() != "openai"
        ]
        if (
            provider_raw == "anthropic"
            and configured_model
            and not cls._looks_like_anthropic_model(configured_model)
            and compatible_profile_ids
        ):
            data["llm.provider"] = "openai"
            if active_profile == "openai_cloud":
                model_match_profile = None
                for profile_id in compatible_profile_ids:
                    model_hint = str((profiles.get(profile_id) or {}).get("default_model") or "").strip()
                    if model_hint == configured_model:
                        model_match_profile = profile_id
                        break
                active_profile = model_match_profile or compatible_profile_ids[0]

        # Heal cloud-model/local-backend mismatch (e.g. GPT-5 + Ollama endpoint).
        active_profile_data = profiles.get(active_profile) if isinstance(profiles, dict) else None
        active_backend = str((active_profile_data or {}).get("backend") or "").strip().lower()
        local_compatible_backends = {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio"}
        if (
            provider_raw == "openai"
            and active_backend in local_compatible_backends
            and cls._looks_like_openai_cloud_model(configured_model)
        ):
            fallback_model = (
                str((active_profile_data or {}).get("default_model") or "").strip()
                or str(
                    OPENAI_PROFILE_DEFAULTS.get(active_backend, OPENAI_PROFILE_DEFAULTS["other"]).get(
                        "default_model"
                    )
                    or "llama3.1"
                ).strip()
            )
            if fallback_model and fallback_model != configured_model:
                data["llm.model"] = fallback_model

        data["llm.openai_profiles"] = profiles
        data["llm.openai_active_profile"] = active_profile
        data["llm.openai_default_profile"] = default_profile

        cls._project_active_profile_to_legacy_data(data)
        return profiles, active_profile, default_profile

    @classmethod
    def _project_active_profile_to_legacy_data(cls, data: dict[str, Any]) -> None:
        """Mirror the active OpenAI profile back into legacy flat keys."""
        profiles = data.get("llm.openai_profiles")
        if not isinstance(profiles, dict):
            return
        active_profile_id = str(data.get("llm.openai_active_profile") or "").strip()
        active = profiles.get(active_profile_id)
        if not isinstance(active, dict):
            return

        backend = cls._normalize_compatible_backend_name(active.get("backend"))
        base_url = cls._normalize_openai_base_url(active.get("base_url"))
        api_key = cls._normalized_secret(active.get("api_key"))

        if backend == "openai":
            data["llm.openai_base_url"] = None
            data["llm.openai_compatible_backend"] = None
            if api_key and "llm.openai_api_key" not in data:
                data["llm.openai_api_key"] = api_key
        else:
            data["llm.openai_base_url"] = base_url
            data["llm.openai_compatible_backend"] = backend or "other"
            if api_key:
                data["llm.openai_compatible_api_key"] = api_key

    def _sync_openai_profile_projection(self, *, apply_legacy_compat: bool = True) -> None:
        """Refresh legacy OpenAI-compatible fields after profile updates."""
        self._ensure_openai_profiles_data(
            self._data,
            apply_legacy_compat=apply_legacy_compat,
        )
        self._dirty_keys.update(
            {
                "llm.openai_profiles",
                "llm.openai_active_profile",
                "llm.openai_default_profile",
                "llm.openai_api_key",
                "llm.openai_base_url",
                "llm.openai_compatible_backend",
                "llm.openai_compatible_api_key",
            }
        )
        self._unset_keys.difference_update(
            {
                "llm.openai_profiles",
                "llm.openai_active_profile",
                "llm.openai_default_profile",
                "llm.openai_api_key",
                "llm.openai_base_url",
                "llm.openai_compatible_backend",
                "llm.openai_compatible_api_key",
            }
        )

    def openai_profiles(self, *, include_cloud: bool = True) -> dict[str, dict[str, Any]]:
        """Return configured OpenAI/OpenAI-compatible profiles."""
        profiles, _, _ = self._ensure_openai_profiles_data(self._data)
        if include_cloud:
            return {profile_id: dict(profile) for profile_id, profile in profiles.items()}
        return {
            profile_id: dict(profile)
            for profile_id, profile in profiles.items()
            if str(profile.get("backend") or "").strip().lower() != "openai"
        }

    def active_openai_profile_id(self) -> str:
        """Return active OpenAI profile id."""
        _, active_profile_id, _ = self._ensure_openai_profiles_data(self._data)
        return active_profile_id

    def compatible_openai_profile_ids(self) -> list[str]:
        """Return configured non-cloud OpenAI-compatible profile ids."""
        profiles = self.openai_profiles(include_cloud=False)
        return sorted(profiles.keys())

    def default_openai_profile_id(self) -> str:
        """Return default OpenAI profile id."""
        _, _, default_profile_id = self._ensure_openai_profiles_data(self._data)
        return default_profile_id

    def get_openai_profile(self, profile_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Return an OpenAI profile by id (or active profile when omitted)."""
        profiles, active_profile_id, _ = self._ensure_openai_profiles_data(self._data)
        selected_profile_id = self._slugify_profile_id(profile_id or active_profile_id)
        profile = profiles.get(selected_profile_id)
        if not profile:
            return None
        return {"id": selected_profile_id, **dict(profile)}

    def set_openai_active_profile(self, profile_id: str) -> None:
        """Set active OpenAI profile and sync legacy projection fields."""
        profiles, _, _ = self._ensure_openai_profiles_data(self._data)
        selected_profile_id = self._slugify_profile_id(profile_id)
        if selected_profile_id not in profiles:
            raise ValueError(f"Unknown OpenAI profile '{profile_id}'.")
        self._data["llm.openai_active_profile"] = selected_profile_id
        self._sync_openai_profile_projection(apply_legacy_compat=False)

    def set_openai_default_profile(self, profile_id: str) -> None:
        """Set default OpenAI profile used for future selections."""
        profiles, _, _ = self._ensure_openai_profiles_data(self._data)
        selected_profile_id = self._slugify_profile_id(profile_id)
        if selected_profile_id not in profiles:
            raise ValueError(f"Unknown OpenAI profile '{profile_id}'.")
        self._data["llm.openai_default_profile"] = selected_profile_id
        self._sync_openai_profile_projection(apply_legacy_compat=False)

    def upsert_openai_profile(
        self,
        *,
        profile_id: Optional[str] = None,
        label: Optional[str] = None,
        backend: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Any = _UNSET,
        default_model: Optional[str] = None,
        discovery: Optional[list[str]] = None,
        set_active: bool = False,
        set_default: bool = False,
    ) -> str:
        """Create or update an OpenAI profile and return its profile id."""
        profiles, active_profile_id, default_profile_id = self._ensure_openai_profiles_data(self._data)
        requested_backend = str(backend or "").strip().lower()
        if requested_backend and requested_backend not in OPENAI_PROFILE_BACKENDS:
            raise ValueError(f"Unsupported OpenAI profile backend '{backend}'.")

        if profile_id:
            resolved_profile_id = self._slugify_profile_id(profile_id)
            existing = dict(profiles.get(resolved_profile_id) or {})
        else:
            inferred_backend = requested_backend or "other"
            base_candidate = label or f"{inferred_backend}_profile"
            resolved_profile_id = self._unique_profile_id(base_candidate, profiles)
            existing = {}

        payload = dict(existing)
        if requested_backend:
            payload["backend"] = requested_backend
        if label is not None:
            payload["label"] = str(label).strip()
        if base_url is not None:
            payload["base_url"] = base_url
        if default_model is not None:
            payload["default_model"] = str(default_model).strip()
        if discovery is not None:
            payload["discovery"] = list(discovery)
        if api_key is not _UNSET:
            payload["api_key"] = self._normalized_secret(api_key)

        if not payload.get("backend"):
            payload["backend"] = self.infer_openai_compatible_backend(
                payload.get("base_url"),
                payload.get("api_key"),
            )

        normalized = self._normalize_profile_record(resolved_profile_id, payload)
        profiles[resolved_profile_id] = normalized
        self._data["llm.openai_profiles"] = profiles

        if set_default:
            self._data["llm.openai_default_profile"] = resolved_profile_id
        elif default_profile_id not in profiles:
            self._data["llm.openai_default_profile"] = resolved_profile_id

        if set_active:
            self._data["llm.openai_active_profile"] = resolved_profile_id
        elif active_profile_id not in profiles:
            self._data["llm.openai_active_profile"] = resolved_profile_id

        self._sync_openai_profile_projection(apply_legacy_compat=False)
        return resolved_profile_id

    def remove_openai_profile(self, profile_id: str) -> bool:
        """Remove an OpenAI-compatible profile (cloud profile is protected)."""
        profiles, active_profile_id, default_profile_id = self._ensure_openai_profiles_data(self._data)
        selected_profile_id = self._slugify_profile_id(profile_id)
        if selected_profile_id == "openai_cloud":
            return False
        if selected_profile_id not in profiles:
            return False
        profiles.pop(selected_profile_id, None)
        self._data["llm.openai_profiles"] = profiles
        if self._slugify_profile_id(active_profile_id) == selected_profile_id:
            self._data["llm.openai_active_profile"] = self._slugify_profile_id(default_profile_id or "openai_cloud")
        if self._slugify_profile_id(default_profile_id) == selected_profile_id:
            self._data["llm.openai_default_profile"] = "openai_cloud"
        self._sync_openai_profile_projection(apply_legacy_compat=False)
        return True

    def hidden_models(self) -> list[str]:
        """Return model IDs hidden from agent model selection."""
        raw = self.get("llm.hidden_models", [])
        if not isinstance(raw, list):
            return []
        return sorted(
            {
                str(item).strip()
                for item in raw
                if str(item or "").strip()
            }
        )

    def is_model_hidden(self, model_id: str) -> bool:
        target = str(model_id or "").strip()
        if not target:
            return False
        return target in set(self.hidden_models())

    def set_model_hidden(self, model_id: str, hidden: bool) -> list[str]:
        """Hide or show a model ID for agent use. Returns the updated hidden list."""
        target = str(model_id or "").strip()
        if not target:
            raise ValueError("model_id is required.")
        current = set(self.hidden_models())
        if hidden:
            current.add(target)
        else:
            current.discard(target)
        next_list = sorted(current)
        self.set("llm.hidden_models", next_list)
        return next_list

    def _migrate_catalog_defaults(self) -> None:
        """Seed newly default-disabled catalog models into hidden_models once."""
        from agent.model_catalog import (
            CATALOG_DEFAULTS_VERSION,
            DEFAULT_DISABLED_MODELS,
        )

        try:
            current_version = int(self.get("llm.catalog_defaults_version", 0) or 0)
        except (TypeError, ValueError):
            current_version = 0
        if current_version >= CATALOG_DEFAULTS_VERSION:
            return

        hidden = set(self.hidden_models())
        hidden.update(DEFAULT_DISABLED_MODELS)
        self.set("llm.hidden_models", sorted(hidden))
        self.set("llm.catalog_defaults_version", CATALOG_DEFAULTS_VERSION)
        try:
            self.save()
        except Exception as exc:  # pragma: no cover - best-effort persistence
            logger.warning("Failed to persist catalog defaults migration: %s", exc)

    def hidden_tools(self) -> list[str]:
        """Return tool IDs disabled from agent tool discovery/calls."""
        raw = self.get("agent.hidden_tools", [])
        if not isinstance(raw, list):
            return []
        return sorted(
            {str(item).strip() for item in raw if str(item or "").strip()}
        )

    def is_tool_hidden(self, tool_id: str) -> bool:
        target = str(tool_id or "").strip()
        if not target:
            return False
        return target in set(self.hidden_tools())

    def set_tool_hidden(self, tool_id: str, hidden: bool) -> list[str]:
        """Enable/disable a tool for agent use. Returns the updated hidden list."""
        target = str(tool_id or "").strip()
        if not target:
            raise ValueError("tool_id is required.")
        current = set(self.hidden_tools())
        if hidden:
            current.add(target)
        else:
            current.discard(target)
        next_list = sorted(current)
        self.set("agent.hidden_tools", next_list)
        return next_list

    def custom_models(self) -> list[dict[str, str]]:
        """Return user-added cloud model IDs (provider + id), normalized."""
        raw = self.get("llm.custom_models", [])
        if not isinstance(raw, list):
            return []
        items: list[dict[str, str]] = []
        seen: set[str] = set()
        for entry in raw:
            if isinstance(entry, str):
                model_id = entry.strip()
                provider = "openai"
                label = model_id
            elif isinstance(entry, dict):
                model_id = str(entry.get("id") or "").strip()
                provider = str(entry.get("provider") or "openai").strip().lower() or "openai"
                label = str(entry.get("label") or model_id).strip() or model_id
            else:
                continue
            if not model_id or model_id in seen:
                continue
            if provider not in VALID_LLM_PROVIDERS:
                provider = "openai"
            seen.add(model_id)
            items.append({"id": model_id, "provider": provider, "label": label})
        return items

    def add_custom_model(
        self,
        *,
        model_id: str,
        provider: str = "openai",
        label: str | None = None,
    ) -> dict[str, str]:
        """Add a custom cloud model ID. Raises ValueError on invalid/duplicate."""
        target = str(model_id or "").strip()
        if not target:
            raise ValueError("model_id is required.")
        provider_norm = str(provider or "openai").strip().lower() or "openai"
        if provider_norm not in VALID_LLM_PROVIDERS:
            raise ValueError(
                f"Unsupported provider '{provider}'. Use one of: {', '.join(sorted(VALID_LLM_PROVIDERS))}."
            )
        from agent.model_catalog import cloud_catalog_models

        catalog_ids = {item["id"] for item in cloud_catalog_models()}
        if target in catalog_ids:
            raise ValueError(f"Model '{target}' is already in the built-in catalog.")
        existing = self.custom_models()
        if any(item["id"] == target for item in existing):
            raise ValueError(f"Custom model '{target}' already exists.")
        record = {
            "id": target,
            "provider": provider_norm,
            "label": str(label or target).strip() or target,
        }
        next_list = [*existing, record]
        self.set("llm.custom_models", next_list)
        return record

    def remove_custom_model(self, model_id: str) -> bool:
        """Remove a custom cloud model. Returns True if something was removed."""
        target = str(model_id or "").strip()
        if not target:
            raise ValueError("model_id is required.")
        existing = self.custom_models()
        next_list = [item for item in existing if item["id"] != target]
        if len(next_list) == len(existing):
            return False
        self.set("llm.custom_models", next_list)
        # Also un-hide if it was toggled off.
        hidden = set(self.hidden_models())
        if target in hidden:
            hidden.discard(target)
            self.set("llm.hidden_models", sorted(hidden))
        return True

    def __init__(self, data: dict = None):
        self._data = data or {}
        self._ensure_openai_profiles_data(self._data)
        self._env_loaded_keys: set[str] = set()
        # Track mutations so save() only applies intentional changes.
        self._dirty_keys: set[str] = set(self._data.keys())
        self._unset_keys: set[str] = set()

    def __repr__(self) -> str:
        """Safe repr that masks API keys and secrets."""
        safe = {}
        for k, v in self._data.items():
            if k == "llm.openai_profiles" and isinstance(v, dict):
                masked_profiles: dict[str, Any] = {}
                for profile_id, profile in v.items():
                    if not isinstance(profile, dict):
                        masked_profiles[str(profile_id)] = profile
                        continue
                    profile_copy = dict(profile)
                    profile_secret = self._normalized_secret(profile_copy.get("api_key"))
                    if profile_secret:
                        profile_copy["api_key"] = (
                            profile_secret[:4] + "..." if len(profile_secret) > 4 else "***"
                        )
                    masked_profiles[str(profile_id)] = profile_copy
                safe[k] = masked_profiles
                continue
            if ("api_key" in k or "secret" in k or k.startswith("api.")) and v:
                safe[k] = str(v)[:4] + "..." if len(str(v)) > 4 else "***"
            else:
                safe[k] = v
        return f"Config({safe})"

    @classmethod
    def load(cls) -> "Config":
        """Load config from disk, creating defaults if needed."""
        loaded_from_backup = False
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    logger.warning(
                        "Invalid config format in %s (expected JSON object), ignoring file",
                        CONFIG_FILE,
                    )
                    data = {}
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to read config file %s: %s", CONFIG_FILE, exc)
                data = {}
        else:
            data = {}

        # Recovery path: if primary is unreadable/empty, try the last backup.
        if not data and CONFIG_BACKUP_FILE.exists():
            try:
                with open(CONFIG_BACKUP_FILE) as f:
                    backup_data = json.load(f)
                if isinstance(backup_data, dict):
                    data = backup_data
                    loaded_from_backup = True
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to read config backup %s: %s", CONFIG_BACKUP_FILE, exc)

        if loaded_from_backup:
            logger.warning("Recovered config from backup: %s", CONFIG_BACKUP_FILE)
            try:
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                with open(CONFIG_FILE, "w") as f:
                    json.dump(data, f, indent=2)
            except OSError as exc:
                logger.warning("Failed to restore recovered config to %s: %s", CONFIG_FILE, exc)

        # Migrate legacy global output dir default to workspace-local output dir.
        legacy_output_dirs = {
            str(Path.home() / ".fastfold-cli" / "outputs"),
            str(Path.home() / ".ct" / "outputs"),
        }
        if data.get("sandbox.output_dir") in legacy_output_dirs:
            data["sandbox.output_dir"] = str(Path.cwd() / "outputs")

        # Check environment variables
        env_mappings = {
            str(info["env_var"]): config_key
            for config_key, info in API_KEYS.items()
        }
        env_mappings.update({
            "ANTHROPIC_API_KEY": "llm.anthropic_api_key",
            "OPENAI_API_KEY": "llm.openai_api_key",
            "XAI_API_KEY": "llm.xai_api_key",
            "GEMINI_API_KEY": "llm.google_api_key",
            "OPENCODE_API_KEY": "llm.opencode_api_key",
            "OPENAI_COMPATIBLE_API_KEY": "llm.openai_compatible_api_key",
            "OPENAI_BASE_URL": "llm.openai_base_url",
            "CT_DATA_DIR": "data.base",
            "CT_LLM_PROVIDER": "llm.provider",
            "CT_LLM_MODEL": "llm.model",
            "IBM_RXN_API_KEY": "api.ibm_rxn_key",
            "LENS_API_KEY": "api.lens_key",
            "FASTFOLD_API_KEY": "api.fastfold_cloud_key",
            "BOLTZ_API_KEY": "api.boltz_api_key",
            "SENDGRID_API_KEY": "notification.sendgrid_api_key",
            "LAMBDA_API_KEY": "compute.lambda_api_key",
            "RUNPOD_API_KEY": "compute.runpod_api_key",
            "CT_DATA_ENDPOINT": "api.data_endpoint",
            "CLUE_API_KEY": "api.clue_key",
        })
        for env_var, config_key in env_mappings.items():
            val = os.environ.get(env_var)
            if val and config_key not in data:
                data[config_key] = val

        cfg = cls(data)
        cfg._dirty_keys.clear()
        cfg._unset_keys.clear()
        cfg._migrate_catalog_defaults()
        # Track keys loaded from environment so they're masked in __repr__/logs
        cfg._env_loaded_keys = {
            config_key for env_var, config_key in env_mappings.items()
            if os.environ.get(env_var) and config_key in data
        }

        # Run validation and log warnings (never crash)
        issues = _validate_config(data)
        for issue in issues:
            logger.warning("Config validation: %s", issue)

        return cfg

    def validate(self) -> list[str]:
        """Run schema validation on current config data. Returns list of issues."""
        return _validate_config(self._data)

    def save(self):
        """Save config to disk."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        # Merge against latest on disk and apply only explicit mutations.
        # This prevents stale in-memory config instances from wiping keys.
        existing: dict[str, Any] = {}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    parsed = json.load(f)
                if isinstance(parsed, dict):
                    existing = parsed
            except (json.JSONDecodeError, OSError):
                existing = {}

        if self._dirty_keys or self._unset_keys:
            merged = dict(existing)
            for key in self._dirty_keys:
                if key in self._data:
                    merged[key] = self._data[key]
            for key in self._unset_keys:
                merged.pop(key, None)
            payload = merged
        else:
            payload = dict(self._data)

        tmp = CONFIG_FILE.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump(payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, CONFIG_FILE)

        # Keep a latest-known-good backup for recovery from partial/corrupt writes.
        try:
            with open(CONFIG_BACKUP_FILE, "w") as f:
                json.dump(payload, f, indent=2)
        except OSError:
            pass

        self._data = payload
        self._dirty_keys.clear()
        self._unset_keys.clear()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value, falling back to defaults."""
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any):
        """Set a config value."""
        if key == "agent.profile":
            profile = str(value).strip().lower()
            if profile not in AGENT_PROFILE_PRESETS:
                valid = ", ".join(sorted(AGENT_PROFILE_PRESETS.keys()))
                raise ValueError(
                    f"Invalid agent.profile '{value}'. Valid profiles: {valid}"
                )
            for preset_key, preset_val in AGENT_PROFILE_PRESETS[profile].items():
                self._data[preset_key] = preset_val
            self._data["agent.profile"] = profile
            return

        if key == "llm.openai_active_profile":
            self.set_openai_active_profile(str(value or ""))
            return

        if key == "llm.openai_default_profile":
            self.set_openai_default_profile(str(value or ""))
            return

        if key == "llm.openai_profiles":
            parsed_value = value
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    try:
                        parsed_value = json.loads(stripped)
                    except Exception as exc:
                        raise ValueError("llm.openai_profiles must be valid JSON object.") from exc
            if not isinstance(parsed_value, dict):
                raise ValueError("llm.openai_profiles must be a JSON object.")
            self._data[key] = parsed_value
            self._dirty_keys.add(key)
            self._unset_keys.discard(key)
            self._sync_openai_profile_projection(apply_legacy_compat=False)
            return

        # Type coercion
        if key in DEFAULTS and DEFAULTS[key] is not None:
            expected_type = type(DEFAULTS[key])
            if expected_type is bool:
                value = value.lower() in ("true", "1", "yes") if isinstance(value, str) else bool(value)
            elif expected_type is float:
                value = float(value)
            elif expected_type is int:
                value = int(value)

        if key in {
            "llm.anthropic_api_key",
            "llm.api_key",
            "llm.openai_api_key",
            "llm.openai_compatible_api_key",
        }:
            value = self._normalized_secret(value)
            issue = self.validate_llm_api_key(
                key,
                value,
                openai_base_url=self.get("llm.openai_base_url"),
            )
            if issue:
                raise ValueError(issue)

        if key in {
            "llm.openai_base_url",
            "llm.openai_compatible_backend",
            "llm.openai_compatible_api_key",
        }:
            if key == "llm.openai_base_url":
                value = self._normalize_openai_base_url(value)
            elif key == "llm.openai_compatible_backend":
                value = self._normalize_compatible_backend_name(value) or None
            self._data[key] = value
            self._dirty_keys.add(key)
            self._unset_keys.discard(key)
            self._sync_openai_profile_projection(apply_legacy_compat=True)
            return

        self._data[key] = value
        self._dirty_keys.add(key)
        self._unset_keys.discard(key)

        if key == "llm.openai_api_key":
            profiles, _, _ = self._ensure_openai_profiles_data(self._data)
            cloud = dict(profiles.get("openai_cloud") or {})
            cloud["backend"] = "openai"
            cloud["label"] = cloud.get("label") or OPENAI_PROFILE_DEFAULTS["openai"]["label"]
            cloud["base_url"] = cloud.get("base_url") or OPENAI_PROFILE_DEFAULTS["openai"]["base_url"]
            cloud["api_key"] = self._normalized_secret(value)
            profiles["openai_cloud"] = self._normalize_profile_record("openai_cloud", cloud)
            self._data["llm.openai_profiles"] = profiles
            self._sync_openai_profile_projection(apply_legacy_compat=False)

    def unset(self, key: str) -> None:
        """Remove a config key override, falling back to defaults/env."""
        if key in {"llm.openai_active_profile", "llm.openai_default_profile", "llm.openai_profiles"}:
            if key == "llm.openai_profiles":
                self._data.pop("llm.openai_profiles", None)
                self._data.pop("llm.openai_active_profile", None)
                self._data.pop("llm.openai_default_profile", None)
            else:
                self._data.pop(key, None)
            self._dirty_keys.discard("llm.openai_profiles")
            self._dirty_keys.discard("llm.openai_active_profile")
            self._dirty_keys.discard("llm.openai_default_profile")
            self._unset_keys.update(
                {
                    "llm.openai_profiles",
                    "llm.openai_active_profile",
                    "llm.openai_default_profile",
                }
            )
            self._ensure_openai_profiles_data(self._data)
            self._sync_openai_profile_projection(apply_legacy_compat=False)
            return

        if key in {
            "llm.openai_base_url",
            "llm.openai_compatible_backend",
            "llm.openai_compatible_api_key",
        }:
            self._data.pop(key, None)
            self._dirty_keys.discard(key)
            self._unset_keys.add(key)
            self._sync_openai_profile_projection(apply_legacy_compat=True)
            return

        if key == "llm.openai_api_key":
            profiles, _, _ = self._ensure_openai_profiles_data(self._data)
            cloud = dict(profiles.get("openai_cloud") or {})
            cloud["api_key"] = None
            profiles["openai_cloud"] = self._normalize_profile_record("openai_cloud", cloud)
            self._data["llm.openai_profiles"] = profiles

        self._data.pop(key, None)
        self._dirty_keys.discard(key)
        self._unset_keys.add(key)

    @staticmethod
    def _normalized_secret(value: Any) -> Optional[str]:
        """Normalize secret-like values; blank/whitespace becomes None."""
        if value is None:
            return None
        text = str(value)
        # Strip ANSI escape sequences that can leak from terminal control input.
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        # Remove non-printable control characters (e.g. ^C bytes).
        text = "".join(ch for ch in text if ch.isprintable())
        text = text.strip()
        return text or None

    @classmethod
    def validate_llm_api_key(
        cls,
        config_key: str,
        value: Any,
        *,
        openai_base_url: Optional[str] = None,
    ) -> Optional[str]:
        """Validate provider API keys; return issue message, else None."""
        normalized = cls._normalized_secret(value)
        if normalized is None:
            return None

        if config_key == "llm.openai_api_key":
            if not cls._is_openai_managed_base_url(openai_base_url):
                return None
            if normalized.startswith("sk-ant-"):
                return (
                    "Invalid OpenAI API key format: looks like an Anthropic key ('sk-ant-...'). "
                    "Use an OpenAI key starting with 'sk-' (typically 'sk-proj-...')."
                )
            if not OPENAI_API_KEY_PATTERN.match(normalized):
                return (
                    "Invalid OpenAI API key format. Expected prefix 'sk-' "
                    "(typically 'sk-proj-...')."
                )
            return None

        if config_key == "llm.openai_compatible_api_key":
            # Compatibility endpoints frequently use placeholder or custom keys.
            return None

        if config_key in {"llm.anthropic_api_key", "llm.api_key"}:
            if not ANTHROPIC_API_KEY_PATTERN.match(normalized):
                return (
                    "Invalid Anthropic API key format. Expected prefix 'sk-ant-'."
                )

        return None

    @staticmethod
    def _secret_preview(value: Any) -> str:
        """Return a masked preview for secret-like values."""
        normalized = Config._normalized_secret(value)
        if not normalized:
            return "—"
        if len(normalized) <= 8:
            return "***"
        if len(normalized) <= 14:
            return f"{normalized[:4]}...{normalized[-2:]}"
        return f"{normalized[:8]}...{normalized[-4:]}"

    def llm_api_key(self, provider: Optional[str] = None) -> Optional[str]:
        """Get the best API key for the selected provider."""
        provider = (provider or self.get("llm.provider", "anthropic")).lower()
        if provider in OPENAI_COMPATIBLE_PROVIDERS:
            meta = OPENAI_COMPATIBLE_PROVIDERS[provider]
            env_key = self._normalized_secret(os.environ.get(meta["env_var"]))
            if env_key:
                return env_key
            return self._normalized_secret(self.get(meta["config_key"]))
        if provider == "openai":
            profile = self.get_openai_profile()
            backend = str((profile or {}).get("backend") or "").strip().lower()
            profile_key = self._normalized_secret((profile or {}).get("api_key"))
            if backend and backend != "openai":
                env_key = self._normalized_secret(os.environ.get("OPENAI_COMPATIBLE_API_KEY"))
                if env_key:
                    return env_key
                return self._normalized_secret(
                    profile_key
                    or self.get("llm.openai_compatible_api_key")
                    or self.get("llm.openai_api_key")
                )
            env_openai_key = self._normalized_secret(os.environ.get("OPENAI_API_KEY"))
            if env_openai_key:
                return env_openai_key
            return self._normalized_secret(self.get("llm.openai_api_key"))
        # Backward compatibility: legacy llm.api_key is Anthropic-only fallback.
        return self._normalized_secret(
            self.get("llm.anthropic_api_key") or self.get("llm.api_key")
        )

    def llm_provider_base_url(self, provider: Optional[str] = None) -> Optional[str]:
        """Fixed base URL for first-party OpenAI-compatible providers (xai/google)."""
        provider = (provider or self.get("llm.provider", "anthropic")).lower()
        meta = OPENAI_COMPATIBLE_PROVIDERS.get(provider)
        return meta["base_url"] if meta else None

    def llm_openai_base_url(self) -> Optional[str]:
        """Return normalized OpenAI-compatible base URL, if configured."""
        env_override = self._normalize_openai_base_url(os.environ.get("OPENAI_BASE_URL"))
        if env_override:
            if self._is_openai_managed_base_url(env_override):
                return None
            return env_override

        profile = self.get_openai_profile()
        backend = str((profile or {}).get("backend") or "").strip().lower()
        if backend and backend != "openai":
            profile_base_url = self._normalize_openai_base_url((profile or {}).get("base_url"))
            if profile_base_url:
                return profile_base_url

        value = self._normalize_openai_base_url(self.get("llm.openai_base_url"))
        if not value or self._is_openai_managed_base_url(value):
            return None
        return value

    @staticmethod
    def _is_local_openai_base_url(base_url: Optional[str]) -> bool:
        """Heuristic: localhost OpenAI-compatible endpoints can skip API keys."""
        if not base_url:
            return False
        try:
            parsed = urlparse(str(base_url).strip())
        except Exception:
            return False
        host = (parsed.hostname or "").strip().lower()
        return host in {"localhost", "127.0.0.1", "::1"}

    @staticmethod
    def _is_openai_managed_base_url(base_url: Optional[str]) -> bool:
        """Return True when base URL points to OpenAI-managed API hosts."""
        if not base_url:
            return True
        try:
            parsed = urlparse(str(base_url).strip())
        except Exception:
            return False
        host = (parsed.hostname or "").strip().lower()
        if not host:
            return False
        return host == "api.openai.com" or host.endswith(".openai.com")

    @staticmethod
    def compatible_backend_install_url(backend: Optional[str]) -> str:
        """Return install/reference URL for a compatible backend template."""
        backend_type = str(backend or "").strip().lower()
        if backend_type in {"other", "custom"}:
            return ""
        defaults = OPENAI_PROFILE_DEFAULTS.get(backend_type, {})
        return str(defaults.get("install_url") or "")

    def llm_preflight_issue(self) -> Optional[str]:
        """Return a human-readable LLM config issue, or None when ready."""
        provider_raw = self.get("llm.provider", "anthropic")
        provider = str(provider_raw or "").strip().lower()
        if not provider:
            return "llm.provider is empty. Set it with: fastfold config set llm.provider anthropic"

        if provider not in VALID_LLM_PROVIDERS:
            valid = ", ".join(sorted(VALID_LLM_PROVIDERS))
            return (
                f"Unsupported llm.provider '{provider}'. "
                f"Valid providers: {valid}. Set it with: fastfold config set llm.provider <provider>"
            )

        provider_key = self.llm_api_key(provider)
        if provider_key:
            if provider == "openai" and str(provider_key).startswith("sk-ant-"):
                return (
                    "Configured OpenAI key appears to be an Anthropic key (starts with 'sk-ant-'). "
                    "Set a valid OpenAI key with:\n"
                    "  fastfold config set llm.openai_api_key <key>"
                )
            return None

        if provider in OPENAI_COMPATIBLE_PROVIDERS:
            meta = OPENAI_COMPATIBLE_PROVIDERS[provider]
            return (
                f"{meta['label']} API key not configured. Add it in Dashboard → "
                f"Models → API Keys, set {meta['env_var']}, or run:\n"
                f"  fastfold config set {meta['config_key']} <key>"
            )

        # Azure AI Foundry: Foundry-specific env vars are valid Anthropic auth
        if provider == "anthropic" and (
            os.environ.get("ANTHROPIC_FOUNDRY_API_KEY")
            or os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE")
        ):
            return None

        if provider == "openai":
            base_url = self.llm_openai_base_url()
            compat_key = self._normalized_secret(self.get("llm.openai_compatible_api_key"))
            if base_url and not self._is_openai_managed_base_url(base_url):
                # For compatible endpoints, key may be optional or custom.
                if compat_key:
                    return None
                return None
            if self._is_local_openai_base_url(base_url):
                return None
            return (
                "OpenAI API key not configured. Set OPENAI_API_KEY or run:\n"
                "  fastfold config set llm.openai_api_key <key>"
            )

        return (
            "Anthropic API key not configured. Set ANTHROPIC_API_KEY or run:\n"
            "  fastfold config set llm.anthropic_api_key <key>\n"
            "Legacy fallback (still supported): llm.api_key\n"
            "For Azure AI Foundry: set ANTHROPIC_FOUNDRY_API_KEY and "
            "ANTHROPIC_FOUNDRY_RESOURCE"
        )

    def keys_table(self) -> Table:
        """Render API key status as a rich table."""
        table = Table(title="API Keys", caption="Set: fastfold config set <key> <value>  |  Or: export ENV_VAR=<value>")
        table.add_column("Service", style="bold")
        table.add_column("Status")
        table.add_column("Preview", style="magenta dim")
        table.add_column("Unlocks", style="dim")
        table.add_column("Config Key", style="cyan dim")
        table.add_column("Sign Up", style="dim")

        profiles = self.openai_profiles(include_cloud=True)
        active_profile = self.get_openai_profile()
        active_profile_id = str((active_profile or {}).get("id") or "").strip()
        active_profile_label = str((active_profile or {}).get("label") or "").strip()
        active_profile_backend = str((active_profile or {}).get("backend") or "").strip().lower()
        active_profile_endpoint = self._normalize_openai_base_url((active_profile or {}).get("base_url")) or "—"
        compatible_profiles = {
            profile_id: profile
            for profile_id, profile in profiles.items()
            if str(profile.get("backend") or "").strip().lower() != "openai"
        }

        for config_key, info in API_KEYS.items():
            if config_key == "llm.anthropic_api_key":
                val = self.llm_api_key("anthropic")
                # Mark legacy-only usage clearly.
                if (
                    not self._normalized_secret(self.get("llm.anthropic_api_key"))
                    and self._normalized_secret(self.get("llm.api_key"))
                ):
                    status = "[yellow]configured (legacy llm.api_key)[/yellow]"
                else:
                    status = "[green]configured[/green]" if val else "[red]not set[/red]"
            elif config_key == "llm.openai_api_key":
                val = self._normalized_secret(
                    os.environ.get("OPENAI_API_KEY")
                    or self.get("llm.openai_api_key")
                    or (profiles.get("openai_cloud") or {}).get("api_key")
                )
                status = "[green]configured[/green]" if val else "[red]not set[/red]"
                if active_profile_backend == "openai":
                    status = f"{status} [dim](active: {active_profile_label or 'OpenAI Cloud'})[/dim]"
            elif config_key == "llm.openai_compatible_api_key":
                profile_rows: list[tuple[str, str, str, str, str]] = []
                for profile_id, profile in sorted(
                    compatible_profiles.items(),
                    key=lambda item: str(item[1].get("label") or item[0]).strip().lower(),
                ):
                    profile_label = str(profile.get("label") or profile_id).strip()
                    profile_backend = str(profile.get("backend") or "other").strip().lower()
                    profile_endpoint = self._normalize_openai_base_url(profile.get("base_url")) or "—"
                    profile_key = self._normalized_secret(profile.get("api_key"))
                    profile_install_url = self.compatible_backend_install_url(profile_backend)
                    profile_status = (
                        "[green]configured[/green]"
                        if profile_key
                        else "[red]not set[/red]"
                    )
                    if profile_id == active_profile_id:
                        profile_status = f"{profile_status} [dim](active)[/dim]"
                    profile_rows.append(
                        (
                            f"OpenAI-compatible: {profile_label}",
                            profile_status,
                            self._secret_preview(profile_key),
                            f"{profile_backend} endpoint ({profile_endpoint})",
                            profile_install_url,
                        )
                    )

                if active_profile_backend != "openai":
                    val = self._normalized_secret(
                        os.environ.get("OPENAI_COMPATIBLE_API_KEY")
                        or (active_profile or {}).get("api_key")
                        or self.get("llm.openai_compatible_api_key")
                    )
                    status = "[green]configured[/green]" if val else "[red]not set[/red]"
                    status = (
                        f"{status} [dim](active: {active_profile_label or active_profile_id}, "
                        f"endpoint: {active_profile_endpoint})[/dim]"
                    )
                else:
                    compatible_keys = [
                        self._normalized_secret(profile.get("api_key"))
                        for profile in compatible_profiles.values()
                    ]
                    compatible_keys = [key for key in compatible_keys if key]
                    val = compatible_keys[0] if compatible_keys else None
                    profile_count = len(compatible_profiles)
                    count_label = f"{profile_count} profile" if profile_count == 1 else f"{profile_count} profiles"
                    status = "[green]configured[/green]" if val else "[red]not set[/red]"
                    status = f"{status} [dim]({count_label}, active: {active_profile_label or 'OpenAI Cloud'})[/dim]"
            else:
                val = self._normalized_secret(self.get(config_key))
                status = "[green]configured[/green]" if val else "[red]not set[/red]"

            free_tag = " (free)" if info["free"] else ""
            table.add_row(
                info["name"],
                status,
                self._secret_preview(val),
                info["description"],
                config_key,
                info["url"] + free_tag,
            )

            if config_key == "llm.openai_compatible_api_key" and profile_rows:
                for (
                    profile_service,
                    profile_status,
                    profile_preview,
                    profile_unlocks,
                    profile_install_url,
                ) in profile_rows:
                    table.add_row(
                        profile_service,
                        profile_status,
                        profile_preview,
                        profile_unlocks,
                        "llm.openai_profiles.<id>.api_key",
                        profile_install_url + free_tag if profile_install_url else "—",
                    )

        return table

    def to_table(self) -> Table:
        """Render config as a rich table."""
        table = Table(title="ct Configuration")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Source", style="dim")

        all_keys = sorted(set(list(DEFAULTS.keys()) + list(self._data.keys())))
        for key in all_keys:
            if key in self._data:
                val = self._data[key]
                source = "config"
            elif key in DEFAULTS:
                val = DEFAULTS[key]
                source = "default"
            else:
                continue

            # Mask sensitive values (API keys, secrets)
            display_val = str(val)
            is_sensitive = "api_key" in key or "secret" in key or key.startswith("api.")
            if is_sensitive and val and len(str(val)) > 8:
                display_val = str(val)[:4] + "..." + str(val)[-4:]

            table.add_row(key, display_val, source)

        return table
