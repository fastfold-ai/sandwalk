"""Track which catalog templates the user explicitly removed."""

from __future__ import annotations

from agent.config import Config

REMOVED_CATALOG_IDS_KEY = "mcp.removed_catalog_ids"


def get_removed_catalog_ids(config: Config | None = None) -> set[str]:
    cfg = config or Config.load()
    raw = cfg.get(REMOVED_CATALOG_IDS_KEY)
    if not isinstance(raw, list):
        return set()
    return {str(item).strip() for item in raw if str(item).strip()}


def set_removed_catalog_ids(ids: set[str], *, config: Config | None = None) -> None:
    cfg = config or Config.load()
    cleaned = sorted({str(item).strip() for item in ids if str(item).strip()})
    if cleaned:
        cfg.set(REMOVED_CATALOG_IDS_KEY, cleaned)
    elif cfg.get(REMOVED_CATALOG_IDS_KEY) is not None:
        cfg.unset(REMOVED_CATALOG_IDS_KEY)
    cfg.save()


def mark_catalog_removed(catalog_id: str) -> None:
    cid = catalog_id.strip()
    if not cid:
        return
    removed = get_removed_catalog_ids()
    removed.add(cid)
    set_removed_catalog_ids(removed)


def clear_catalog_removed(catalog_id: str) -> None:
    cid = catalog_id.strip()
    if not cid:
        return
    removed = get_removed_catalog_ids()
    if cid not in removed:
        return
    removed.discard(cid)
    set_removed_catalog_ids(removed)
