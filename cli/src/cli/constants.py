"""Shared constants used across cli command modules."""

import re

from agent.config import CONFIG_DIR

FASTFOLD_CLOUD_API_KEYS_URL = "https://cloud.fastfold.ai/api-keys"
BOLTZ_API_KEYS_URL = "https://api.boltz.bio/console"
BOLTZ_SKILL_SOURCE = "fastfold-ai/skills@skills/boltz"
BOLTZ_INSTALL_SCRIPT = "set -euo pipefail; curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"
SETUP_PROVIDER_ORDER = (
    "openai",
    "anthropic",
    "xai",
    "google",
    "nvidia",
    "opencode",
    "openai_compatible",
)
UV_INSTALL_FLAVORS = frozenset({"all", "win_build"})
UV_UPGRADE_PYTHON_VERSION = "3.11"
PYPI_PROJECT_JSON_URL = "https://pypi.org/pypi/sandwalk/json"
_SEMVER_TRIPLET_PATTERN = re.compile(r"^\s*v?(\d+)\.(\d+)\.(\d+)")
_UPGRADE_CACHE_PATH = CONFIG_DIR / "cache" / "upgrade-version.json"
_UPGRADE_CACHE_MAX_AGE_S = 60 * 60 * 6
_BANNER_TOOL_COUNT_HINT = 192

_FASTFOLD_CORE_SKILL_NAMES = {
    "boltz",
    "fold",
    "protein_design_boltzgen",
    "md_openmm_calvados",
    "md_openmmdl",
    "slack_report",
}
