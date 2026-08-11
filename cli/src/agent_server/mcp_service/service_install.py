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
        elif catalog_id == "raymol":
            from agent.mcps.raymol_mcp import ensure_launcher

            ok, message = ensure_launcher(force=force)
            if not ok:
                raise RuntimeError(message)
            launcher_message = message

        server = install_catalog_server(self.store, catalog_id)

        # Keep stdio command/args in sync with the resolved launcher path.
        if entry.transport == "stdio":
            from agent.mcp_catalog import resolve_catalog_command

            command = resolve_catalog_command(entry)
            args = list(entry.args or [])
            updates: dict[str, Any] = {}
            if command and server.command != command:
                updates["command"] = command
            if list(server.args or []) != args:
                updates["args"] = args
            if updates:
                server = self.store.update_mcp_server(server.id, **updates) or server

        enable_result: dict[str, Any] | None = None
        if entry.transport == "stdio" or entry.auth_mode == "none":
            if credentials_configured(entry):
                enable_result = self.set_enabled(catalog_id, True)

        return {
            "server": enrich_mcp_server(server),
            "launcherMessage": launcher_message,
            "enable": enable_result,
        }

    def reset_featured_defaults(self) -> dict[str, Any]:
        """Re-install every missing featured catalog template.

        Add-only: never deletes or updates custom servers (no ``catalog_id``)
        or already-installed featured rows. Same path as per-id install
        (PyMOL runs the managed launcher). Partial failures are reported
        without aborting the rest.
        """
        from agent_server.mcp_json_config import (
            install_catalog_server,
            suggested_catalog_ids,
        )

        missing = suggested_catalog_ids(self.store)
        installed: list[str] = []
        errors: list[dict[str, str]] = []
        for catalog_id in missing:
            try:
                entry = get_catalog_entry(catalog_id)
                if entry is not None and (
                    entry.transport == "stdio" or entry.auth_mode == "none"
                ):
                    self.install_featured(catalog_id)
                else:
                    install_catalog_server(self.store, catalog_id)
                installed.append(catalog_id)
            except Exception as exc:  # noqa: BLE001 — continue remaining installs
                errors.append({"id": catalog_id, "error": str(exc)})
        return {"installed": installed, "errors": errors}
