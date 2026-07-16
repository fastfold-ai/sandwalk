"""Per-session sandbox status and lifecycle controls (split package).

Re-exports the public surface previously defined in
``agent_server/session_sandbox_service.py`` so existing imports keep working.
"""

from __future__ import annotations

from agent_server.sandbox_settings_service import SandboxSettingsService
from agent_server.session_sandbox_service.backend import effective_session_sandbox_backend
from agent_server.session_sandbox_service.service import SessionSandboxService

__all__ = [
    "SessionSandboxService",
    "effective_session_sandbox_backend",
    "SandboxSettingsService",
]
