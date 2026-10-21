"""One-time seeding of curated defaults, persona backfill, and legacy-slug migration."""

from __future__ import annotations

from typing import Any

from agent_server.default_specialists.catalog import (
    DEFAULT_SPECIALISTS,
    PERSONA_SPECIALISTS,
)

_LEGACY_SLUG_REDIRECTS: dict[str, str] = {
    "protein-design": "protein-designer",
}

DEFAULT_SPECIALISTS_SEEDED_META_KEY = "default_specialists_seeded"
DEFAULT_SPECIALIST_TOOL_NAMES_META_KEY = "default_specialist_tool_names_backfilled"
PERSONA_SPECIALISTS_SEEDED_META_KEY = "persona_specialists_seeded_v2"


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


def _create_from_spec(store: Any, spec: dict[str, Any]) -> Any:
    created = store.create_specialist(
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
    spec_id = getattr(created, "id", None) or (created.get("id") if isinstance(created, dict) else None)
    if spec_id and any(spec.get(k) for k in ("role_label", "cookbook_id", "priors")):
        try:
            from agent_server.memory_service.store import MemoryStore

            MemoryStore().upsert_specialist_persona(
                str(spec_id),
                slug=str(spec["slug"]),
                role_label=spec.get("role_label"),
                cookbook_id=spec.get("cookbook_id"),
                priors=spec.get("priors"),
            )
        except Exception:
            pass
    return created


def ensure_default_specialists(store: Any) -> list[Any]:
    """Seed curated specialists once on a fresh empty store."""
    _migrate_legacy_slugs(store)

    if store.get_meta(DEFAULT_SPECIALISTS_SEEDED_META_KEY) == "1":
        return []

    existing = store.list_specialists()
    if existing:
        store.set_meta(DEFAULT_SPECIALISTS_SEEDED_META_KEY, "1")
        return []

    created: list[Any] = []
    for spec in DEFAULT_SPECIALISTS:
        created.append(_create_from_spec(store, spec))
    store.set_meta(DEFAULT_SPECIALISTS_SEEDED_META_KEY, "1")
    return created


def ensure_persona_specialists(store: Any) -> list[Any]:
    """Upsert general-purpose Persona specialists (Atlas, Nova, Milo, Soren) once on existing stores."""
    if store.get_meta(PERSONA_SPECIALISTS_SEEDED_META_KEY) == "1":
        return []
    created: list[Any] = []
    for spec in PERSONA_SPECIALISTS:
        slug = str(spec["slug"])
        if store.get_specialist_by_slug(slug) is not None:
            continue
        created.append(_create_from_spec(store, spec))
    store.set_meta(PERSONA_SPECIALISTS_SEEDED_META_KEY, "1")
    return created


def ensure_default_specialist_tool_names(store: Any) -> int:
    """One-shot: fill empty ``tool_names`` on curated defaults from seed profiles."""
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
