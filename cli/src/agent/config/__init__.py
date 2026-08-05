"""
Configuration management for Sandwalk.

Config is stored at ~/.sandwalk/config.json and manages:
- LLM provider settings (Anthropic, OpenAI, local models)
- Data directory paths (DepMap, PRISM, etc.)
- Output preferences
- Tool-specific settings

Legacy locations ``~/.fastfold-cli`` and ``~/.ct`` are migrated once on import
(copy-if-missing into ``~/.sandwalk``).

This is a package (not a single module) so each concern — defaults, API key
registry, OpenAI-compatible profile handling, secrets, tables — lives in its
own small file. ``Config.load`` / ``Config.save`` and the legacy-path rewriter
stay defined here (rather than in a submodule) because several tests
monkeypatch module-level globals like ``CONFIG_FILE`` directly on this
package; only code whose ``__globals__`` is this module observes that.
"""

from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env from current dir and project root
load_dotenv()
load_dotenv(Path(__file__).resolve().parents[4] / ".env")  # repo root

from . import io_helpers  # noqa: E402
from .api_keys import API_KEYS  # noqa: E402
from .constants import (  # noqa: E402
    _UNSET,
    ANTHROPIC_API_KEY_PATTERN,
    CONFIG_BACKUP_FILE,
    CONFIG_DIR,
    CONFIG_FILE,
    LEGACY_CONFIG_DIRS,
    LEGACY_CT_DIR,
    LEGACY_FASTFOLD_DIR,
    OPENAI_API_KEY_PATTERN,
    OPENAI_PROFILE_BACKENDS,
    VALID_LLM_PROVIDERS,
    logger,
)
from .core_identity import CoreIdentityMixin  # noqa: E402
from .core_mutate import CoreMutateMixin  # noqa: E402
from .defaults import AGENT_PROFILE_PRESETS, DEFAULTS  # noqa: E402
from .env_sync import (  # noqa: E402
    apply_env_overrides,
    env_var_mappings,
    listed_integration_env_vars,
    sync_process_env_from_config,
    sync_sandwalk_path_env,
    unset_process_env_for_config_keys,
)
from .legacy import migrate_tree as _migrate_tree  # noqa: E402
from .model_custom import ModelCustomMixin  # noqa: E402
from .model_favorites import ModelFavoritesMixin  # noqa: E402
from .model_hidden import ModelHiddenMixin  # noqa: E402
from .profile_backend_infer import ProfileBackendInferMixin  # noqa: E402
from .profile_bootstrap import ProfileBootstrapMixin  # noqa: E402
from .profile_crud import ProfileCrudMixin  # noqa: E402
from .profile_ensure import ProfileEnsureMixin  # noqa: E402
from .profile_heal import ProfileHealMixin  # noqa: E402
from .profile_record import ProfileRecordMixin  # noqa: E402
from .profile_seed import ProfileSeedMixin  # noqa: E402
from .providers import (  # noqa: E402
    OPENAI_COMPATIBLE_PROVIDERS,
    OPENAI_PROFILE_DEFAULTS,
    QWEN_CODING_BASE_URL,
    QWEN_PAYGO_BASE_URL,
    QWEN_TOKEN_PLAN_BASE_URL,
    normalize_qwen_base_url,
    qwen_base_url_candidates,
    resolve_qwen_base_url,
)
from .secrets_core import SecretsCoreMixin  # noqa: E402
from .secrets_preflight import SecretsPreflightMixin  # noqa: E402
from .tables import TablesMixin  # noqa: E402
from .validation import _validate_config  # noqa: E402


def _rewrite_legacy_config_paths(data: dict[str, Any]) -> None:
    """Rewrite config string values that still point at legacy home dirs."""
    old_roots = (str(LEGACY_CT_DIR), str(LEGACY_FASTFOLD_DIR))
    new_root = str(CONFIG_DIR)
    for key, val in list(data.items()):
        if not isinstance(val, str):
            continue
        for old in old_roots:
            if val == old or val.startswith(old + "/"):
                data[key] = new_root + val[len(old):]
                break


_migrate_tree(LEGACY_CT_DIR, LEGACY_FASTFOLD_DIR, label="ct→fastfold-cli")
_migrate_tree(LEGACY_FASTFOLD_DIR, CONFIG_DIR, label="fastfold-cli→sandwalk")
_migrate_tree(LEGACY_CT_DIR, CONFIG_DIR, label="ct→sandwalk")


class Config(
    CoreIdentityMixin,
    CoreMutateMixin,
    ProfileEnsureMixin,
    ProfileSeedMixin,
    ProfileBootstrapMixin,
    ProfileHealMixin,
    ProfileCrudMixin,
    ProfileRecordMixin,
    ProfileBackendInferMixin,
    ModelHiddenMixin,
    ModelFavoritesMixin,
    ModelCustomMixin,
    SecretsCoreMixin,
    SecretsPreflightMixin,
    TablesMixin,
):
    """ct configuration manager."""

    @classmethod
    def load(cls) -> "Config":
        """Load config from disk, creating defaults if needed."""
        data, loaded_from_backup = io_helpers.read_config_with_backup(CONFIG_FILE, CONFIG_BACKUP_FILE)
        if loaded_from_backup:
            logger.warning("Recovered config from backup: %s", CONFIG_BACKUP_FILE)
            io_helpers.write_recovered_config(CONFIG_FILE, CONFIG_DIR, data)

        # Migrate legacy global output dir default to workspace-local output dir.
        _rewrite_legacy_config_paths(data)
        legacy_output_dirs = {
            str(LEGACY_FASTFOLD_DIR / "outputs"),
            str(LEGACY_CT_DIR / "outputs"),
            str(CONFIG_DIR / "outputs"),
        }
        if data.get("sandbox.output_dir") in legacy_output_dirs:
            data["sandbox.output_dir"] = str(Path.cwd() / "outputs")

        env_mappings = env_var_mappings(API_KEYS)
        apply_env_overrides(data, env_mappings)

        # Capture disk provider/model before profile heal mutates ``data`` in place.
        disk_provider = str(data.get("llm.provider") or "").strip().lower()
        disk_model = str(data.get("llm.model") or "").strip()

        cfg = cls(data)
        cfg._dirty_keys.clear()
        cfg._unset_keys.clear()
        cfg._migrate_catalog_defaults()
        # Track keys loaded from environment so they're masked in __repr__/logs
        import os as _os

        cfg._env_loaded_keys = {
            config_key for env_var, config_key in env_mappings.items()
            if _os.environ.get(env_var) and config_key in data
        }

        cls._persist_heal(cfg, "llm.provider", disk_provider)
        cls._persist_heal(cfg, "llm.model", disk_model)

        # Run validation and log warnings (never crash)
        issues = _validate_config(data)
        for issue in issues:
            logger.warning("Config validation: %s", issue)

        return cfg

    @staticmethod
    def _persist_heal(cfg: "Config", key: str, disk_value: str) -> None:
        """Persist a healed provider/model value if it changed during load()."""
        healed_value = str(cfg.get(key) or "").strip()
        if healed_value and healed_value != disk_value:
            try:
                cfg.set(key, healed_value)
                cfg.save()
            except OSError as exc:
                logger.warning("Failed to persist healed %s=%s: %s", key, healed_value, exc)

    def save(self) -> None:
        """Save config to disk."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        existing = io_helpers.read_existing_config(CONFIG_FILE)
        payload = io_helpers.merge_dirty(existing, self._data, self._dirty_keys, self._unset_keys)
        io_helpers.atomic_write_config(CONFIG_FILE, CONFIG_BACKUP_FILE, payload)
        self._data = payload
        self._dirty_keys.clear()
        self._unset_keys.clear()
