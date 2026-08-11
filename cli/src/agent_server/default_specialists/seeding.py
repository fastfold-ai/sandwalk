"""One-time seeding of curated defaults, and a legacy-slug migration."""

from __future__ import annotations

from typing import Any

from agent_server.default_specialists.catalog import DEFAULT_SPECIALISTS

_LEGACY_SLUG_REDIRECTS: dict[str, str] = {
    "protein-design": "protein-designer",
}

DEFAULT_SPECIALISTS_SEEDED_META_KEY = "default_specialists_seeded"
DEFAULT_SPECIALIST_TOOL_NAMES_META_KEY = "default_specialist_tool_names_backfilled"


def _migrate_legacy_slugs(store: Any) -> None:
    for legacy_slug, new_slug in _LEGACY_SLUG_REDIRECTS.items():
        legacy = store.get_specialist_by_slug(legacy_slug)
        if legacy is None:
            continue
        target = store.get_specialist_by_slug(new_slug)
        if target is None:
            store.update_specialist(legacy.id, slug=new_slug)
        else:
            store.delete_specialist(legacy.id)


def ensure_default_specialists(store: Any) -> list[Any]:
    """Seed curated specialists once on a fresh empty store.

    Safe to call on every boot. After the one-time seed (or when the store
    already had any specialists), never creates or updates defaults again so
    deletes and edits stay under user control.
    """
    _migrate_legacy_slugs(store)

    if store.get_meta(DEFAULT_SPECIALISTS_SEEDED_META_KEY) == "1":
        return []

    existing = store.list_specialists()
    if existing:
        # Prior install / user-owned data — mark seeded without backfilling.
        store.set_meta(DEFAULT_SPECIALISTS_SEEDED_META_KEY, "1")
        return []

    created: list[Any] = []
    for spec in DEFAULT_SPECIALISTS:
        created.append(
            store.create_specialist(
                slug=str(spec["slug"]),
                name=str(spec["name"]),
                description=str(spec.get("description") or "") or None,
                instructions=str(spec.get("instructions") or "") or None,
                color=str(spec.get("color") or "ink"),
                icon=str(spec.get("icon") or "git-branch"),
                skill_names=list(spec.get("skill_names") or []),
                tool_names=list(spec.get("tool_names") or spec.get("preferred_tools") or []),
                mcp_server_ids=list(spec.get("mcp_server_ids") or []),
                mcp_catalog_ids=list(spec.get("mcp_catalog_ids") or []),
                enabled=bool(spec.get("enabled", True)),
            )
        )
    store.set_meta(DEFAULT_SPECIALISTS_SEEDED_META_KEY, "1")
    return created


def ensure_default_specialist_tool_names(store: Any) -> int:
    """One-shot: fill empty ``tool_names`` on curated defaults from seed profiles.

    Existing specialists were created before the allowlist field existed, so the
    UI shows ``0 tools``. Populate from ``DEFAULT_SPECIALISTS`` (core + domain
    extras). Never overwrites a non-empty allowlist (user edits win).
    """
    if store.get_meta(DEFAULT_SPECIALIST_TOOL_NAMES_META_KEY) == "1":
        return 0

    updated = 0
    by_slug = {
        str(spec.get("slug") or "").strip(): spec for spec in DEFAULT_SPECIALISTS
    }
    for slug, spec in by_slug.items():
        if not slug:
            continue
        existing = store.get_specialist_by_slug(slug)
        if existing is None:
            continue
        if list(existing.tool_names or []):
            continue
        tools = list(spec.get("tool_names") or spec.get("preferred_tools") or [])
        if not tools:
            continue
        store.update_specialist(existing.id, tool_names=tools)
        updated += 1

    store.set_meta(DEFAULT_SPECIALIST_TOOL_NAMES_META_KEY, "1")
    return updated
