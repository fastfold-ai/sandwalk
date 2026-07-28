"""Local static Sites lifecycle tool used by the bundled Sites skills."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_server.sites_service import SitesService
from agent_server.store import AgentStore
from tools import registry


def _dump(site: Any) -> dict[str, Any]:
    return site.model_dump(mode="json", by_alias=True)


@registry.register(
    name="sites.manage",
    description=(
        "Create, update, list, inspect, preview, publish, rename, or delete static sites. "
        "Actions: create, update, list, status, preview, publish, rename, delete."
    ),
    category="sites",
    parameters={
        "action": "One of: create, update, list, status, preview, publish, rename, delete",
        "name": "Site display name for create or rename",
        "path": "Static output directory containing index.html for create or update",
        "site_id": "Existing local site id for update/status/preview/publish/rename/delete",
        "slug": "Optional requested <slug>.sandwalk.site subdomain for publish",
        "session_id": "Optional origin chat session id",
        "project_id": "Optional origin project id",
    },
    usage_guide=(
        "Use after sites-building has produced a static output directory. Preview before publish. "
        "Publishing is a public external side effect: confirm the final name and requested slug "
        "with the user before action=publish."
    ),
)
def manage(
    action: str = "list",
    name: str = "",
    path: str = "",
    site_id: str = "",
    slug: str = "",
    session_id: str = "",
    project_id: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    del kwargs
    store = AgentStore()
    service = SitesService(store)
    current = (action or "list").strip().lower()
    try:
        if current == "list":
            sites = store.list_sites()
            return {
                "ok": True,
                "summary": f"{len(sites)} site(s).",
                "sites": [_dump(site) for site in sites],
            }
        if current in {"status", "info"}:
            site = store.get_site(site_id)
            if site is None:
                return {"ok": False, "summary": "Site not found."}
            return {"ok": True, "summary": f"Site '{site.name}' is {site.status}.", "site": _dump(site)}
        if current == "create":
            site = service.register(
                name=name,
                source=path,
                session_id=session_id or None,
                project_id=project_id or None,
                workspace_root=Path.cwd(),
            )
            return {
                "ok": True,
                "summary": f"Created local site '{site.name}' ({site.id}).",
                "site": _dump(site),
            }
        if current == "update":
            existing = store.get_site(site_id)
            if existing is None:
                return {"ok": False, "summary": "Site not found."}
            site = service.register(
                site_id=site_id,
                name=name or existing.name,
                source=path,
                session_id=session_id or existing.origin_session_id,
                project_id=project_id or existing.origin_project_id,
                workspace_root=Path.cwd(),
            )
            return {
                "ok": True,
                "summary": f"Updated local site '{site.name}'.",
                "site": _dump(site),
            }
        if current == "rename":
            site = service.rename(site_id, name)
            return {"ok": True, "summary": f"Renamed site to '{site.name}'.", "site": _dump(site)}
        if current == "preview":
            url, expires = service.create_preview(site_id)
            return {
                "ok": True,
                "summary": f"Preview ready until {expires.isoformat()}.",
                "site_id": site_id,
                "url": url,
                "expires_at": expires.isoformat(),
            }
        if current == "publish":
            site = service.publish(site_id, slug=slug.strip() or None)
            return {
                "ok": True,
                "summary": f"Published '{site.name}' at {site.cloud_url}.",
                "site": _dump(site),
                "url": site.cloud_url,
            }
        if current == "delete":
            service.delete(site_id)
            return {"ok": True, "summary": f"Deleted local site {site_id}.", "deleted": True}
        return {"ok": False, "summary": f"Unknown Sites action: {action}"}
    except (KeyError, ValueError, RuntimeError, TimeoutError) as exc:
        return {"ok": False, "summary": str(exc)}
    finally:
        store.close()
