"""Agent file-access policy: workspace-scoped (default) vs full filesystem.

Value lives in config under ``agent.file_access`` and is mirrored into the
process env (``SANDWALK_AGENT_FILE_ACCESS``) per agent turn so shell/sandbox
guards can read it without a config load in hot paths.
"""

from __future__ import annotations

import os

FILE_ACCESS_ENV = "SANDWALK_AGENT_FILE_ACCESS"

PROJECT = "project"
FULL = "full"
_ALLOWED = frozenset({PROJECT, FULL})


def normalize_file_access(value: str | None, *, default: str = PROJECT) -> str:
    key = str(value or "").strip().lower() or default
    return key if key in _ALLOWED else default


def file_access_from_env() -> str:
    return normalize_file_access(os.environ.get(FILE_ACCESS_ENV))


def full_file_access_enabled() -> bool:
    return file_access_from_env() == FULL
