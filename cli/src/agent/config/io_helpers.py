"""Pure file-IO helpers backing ``Config.load()`` / ``Config.save()``.

Kept parameter-driven (no module-level path globals) so callers in
``agent.config.__init__`` can pass the current, possibly monkeypatched,
``CONFIG_FILE`` / ``CONFIG_BACKUP_FILE`` / ``CONFIG_DIR`` values explicitly.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

_logger = logging.getLogger("config")


def read_config_with_backup(config_file: Path, backup_file: Path) -> tuple[dict, bool]:
    """Read the primary config file, recovering from the backup if needed."""
    data: dict[str, Any] = {}
    if config_file.exists():
        try:
            with open(config_file) as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data = loaded
            else:
                _logger.warning(
                    "Invalid config format in %s (expected JSON object), ignoring file",
                    config_file,
                )
        except (json.JSONDecodeError, OSError) as exc:
            _logger.warning("Failed to read config file %s: %s", config_file, exc)

    if data or not backup_file.exists():
        return data, False

    try:
        with open(backup_file) as f:
            backup_data = json.load(f)
        if isinstance(backup_data, dict):
            return backup_data, True
    except (json.JSONDecodeError, OSError) as exc:
        _logger.warning("Failed to read config backup %s: %s", backup_file, exc)
    return data, False


def write_recovered_config(config_file: Path, config_dir: Path, data: dict) -> None:
    """Persist a backup-recovered config back to the primary file."""
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w") as f:
            json.dump(data, f, indent=2)
    except OSError as exc:
        _logger.warning("Failed to restore recovered config to %s: %s", config_file, exc)


def read_existing_config(config_file: Path) -> dict:
    """Read the current on-disk config, tolerating missing/corrupt files."""
    if not config_file.exists():
        return {}
    try:
        with open(config_file) as f:
            parsed = json.load(f)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def merge_dirty(
    existing: dict, data: dict, dirty_keys: set[str], unset_keys: set[str]
) -> dict:
    """Merge only intentionally mutated keys onto the latest on-disk config."""
    if not dirty_keys and not unset_keys:
        return dict(data)
    merged = dict(existing)
    for key in dirty_keys:
        if key in data:
            merged[key] = data[key]
    for key in unset_keys:
        merged.pop(key, None)
    return merged


def atomic_write_config(config_file: Path, backup_file: Path, payload: dict) -> None:
    """Atomically write ``payload`` to ``config_file`` and refresh the backup copy."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    # Unique tmp name avoids races when two writers use the same .json.tmp.
    tmp = config_file.with_name(f"{config_file.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w") as f:
            json.dump(payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, config_file)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass

    try:
        with open(backup_file, "w") as f:
            json.dump(payload, f, indent=2)
    except OSError:
        pass
