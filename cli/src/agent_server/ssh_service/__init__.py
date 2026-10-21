"""SSH Manager & Remote-SSH Auto-Bootstrap Service package."""

from __future__ import annotations

from agent_server.ssh_service.config_discovery import (
    ParsedSshTarget,
    discover_ssh_config_hosts,
    parse_ssh_target_string,
)
from agent_server.ssh_service.service import SshService

__all__ = [
    "ParsedSshTarget",
    "SshService",
    "discover_ssh_config_hosts",
    "parse_ssh_target_string",
]
