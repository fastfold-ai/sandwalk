"""Paths, logger, and regex constants shared across the config package."""

import logging
import re
from pathlib import Path

CONFIG_DIR = Path.home() / ".sandwalk"
CONFIG_FILE = CONFIG_DIR / "config.json"
CONFIG_BACKUP_FILE = CONFIG_DIR / "config.json.bak"
# Previous install locations — kept for one-time migration and allowlists.
LEGACY_FASTFOLD_DIR = Path.home() / ".fastfold-cli"
LEGACY_CT_DIR = Path.home() / ".ct"
LEGACY_CONFIG_DIRS = (LEGACY_FASTFOLD_DIR, LEGACY_CT_DIR)
VALID_LLM_PROVIDERS = frozenset(
    {
        "anthropic",
        "openai",
        "xai",
        "google",
        "moonshot",
        "nvidia",
        "opencode",
        "deepseek",
        "minimax",
        "mistral",
        "qwen",
        "together",
        "openrouter",
        "bedrock",
        "cerebras",
        "groq",
        "fireworks",
        "meta",
    }
)

logger = logging.getLogger("config")
OPENAI_API_KEY_PATTERN = re.compile(r"^sk-[A-Za-z0-9_-]{6,}$")
ANTHROPIC_API_KEY_PATTERN = re.compile(r"^sk-ant-[A-Za-z0-9_-]{6,}$")
OPENAI_PROFILE_BACKENDS = frozenset(
    {"openai", "ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}
)
_UNSET = object()
