"""Shared implementation behind CLI keys and web integrations.

This is a package so the metadata tables, provider read path, mutate path,
Vercel auto-import, and Vercel setup wizard can live in their own modules;
:class:`IntegrationsService` composes them via mixins in
:mod:`agent_server.integrations_service.core`. Import from
``agent_server.integrations_service`` as before — this module re-exports the
public API.

Exposed here so ``agent_server.integrations_service.shutil.which`` /
``...subprocess.run`` keep working as monkeypatch/patch targets (submodules
share the same ``shutil``/``subprocess`` module objects, so patching them
here patches them everywhere), matching this module's behavior from before
the split.
"""

from __future__ import annotations

import shutil
import subprocess

from agent_server.integrations_service.core import IntegrationsService
from agent_server.integrations_service.metadata import (
    KEY_ALIASES,
    PROVIDER_METADATA,
    VERCEL_INTEGRATION_DIR,
    category_for,
)

__all__ = [
    "KEY_ALIASES",
    "PROVIDER_METADATA",
    "VERCEL_INTEGRATION_DIR",
    "IntegrationsService",
    "category_for",
]
