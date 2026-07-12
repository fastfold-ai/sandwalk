"""Local and self-hosted control plane for FastFold Agent."""

from agent_server.app import create_app

__all__ = ["create_app"]
