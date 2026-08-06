"""Install featured catalog MCPs (including local stdio launchers)."""

from __future__ import annotations

from typing import Any

from agent.mcp_catalog import get_catalog_entry
from agent_server.mcp_service.auth import credentials_configured
from agent_server.mcp_service.custom_server import enrich_mcp_server


class InstallMixin:
    def install_featured(
        self, catalog_id: str, *, force: bool = False
    ) -> dict[str, Any]:
        """Install a catalog template; for PyMOL also create the managed launcher."""
        # Lazy import: mcp_json_config → mcp_service would cycle at package import.
        from agent_server.mcp_json_config import install_catalog_server

        entry = get_catalog_entry(catalog_id)
        if entry is None:
            raise KeyError(catalog_id)

        launcher_message: str | None = None
        if catalog_id == "pymol":
            from agent.mcps.pymol_mcp import ensure_launcher

            ok, message = ensure_launcher(force=force)
            if not ok:
                raise RuntimeError(message)
            launcher_message = message

        server = install_catalog_server(self.store, catalog_id)

        # Keep stdio command in sync with the resolved launcher path.
        if entry.transport == "stdio":
            from agent.mcp_catalog import resolve_catalog_command

            command = resolve_catalog_command(entry)
            if command and server.command != command:
                server = (
                    self.store.update_mcp_server(server.id, command=command) or server
                )

        enable_result: dict[str, Any] | None = None
        if entry.transport == "stdio" or entry.auth_mode == "none":
            if credentials_configured(entry):
                enable_result = self.set_enabled(catalog_id, True)

        return {
            "server": enrich_mcp_server(server),
            "launcherMessage": launcher_message,
            "enable": enable_result,
        }
