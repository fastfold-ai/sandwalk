"""Measure on-disk usage under ~/.sandwalk for the Storage settings page.

This is a package so sizing/inventory helpers, category specs, the database
probe, and the ``StorageService`` report assembly can live in their own
modules. Import from ``agent_server.storage_service`` as before — this
module re-exports the public API.

``shutil``, ``subprocess``, and ``Config`` stay bound at this package-root
level so tests that monkeypatch ``agent_server.storage_service.shutil.<x>``,
``...subprocess.<x>``, and ``...Config.load`` keep working, and so
``_python_env_category``/``get_report`` can look up patched helpers
(``resolve_python_env_root``, ``list_installed_packages``,
``_path_size_bytes``, ``_python_env_category``) through this package's
namespace rather than a direct import, matching this module's behavior from
before the split.
"""

from __future__ import annotations

import shutil
import subprocess

from agent.config import Config
from agent_server.storage_service.core import StorageService
from agent_server.storage_service.database import probe_agent_database
from agent_server.storage_service.path_size import _path_size_bytes
from agent_server.storage_service.python_env import (
    _python_env_category,
    list_installed_packages,
    resolve_python_env_root,
)

__all__ = [
    "Config",
    "StorageService",
    "_path_size_bytes",
    "_python_env_category",
    "list_installed_packages",
    "probe_agent_database",
    "resolve_python_env_root",
]
