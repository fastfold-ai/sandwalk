"""Unit tests for specialists service and default seeding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_server.default_specialists import (
    DEFAULT_SPECIALISTS,
    DEFAULT_SPECIALISTS_SEEDED_META_KEY,
    ensure_default_specialists,
    filter_mcp_servers_for_specialist,
)
from agent_server.specialists_service import SpecialistsService
from agent_server.store import AgentStore


class _FakeStore:
    """Minimal store double for seeding logic without SQLite boot seed."""

    def __init__(self) -> None:
        self._meta: dict[str, str] = {}
        self._specialists: list[dict[str, Any]] = []
        self._by_slug: dict[str, dict[str, Any]] = {}

    def get_meta(self, key: str) -> str | None:
        return self._meta.get(key)

    def set_meta(self, key: str, value: str) -> None:
        self._meta[key] = value

    def list_specialists(self) -> list[Any]:
        return list(self._specialists)

    def get_specialist_by_slug(self, slug: str) -> Any | None:
        return self._by_slug.get(slug)

    def create_specialist(self, **kwargs: Any) -> Any:
        row = {"id": f"id-{len(self._specialists)}", **kwargs}
        self._specialists.append(row)
        if kwargs.get("slug"):
            self._by_slug[str(kwargs["slug"])] = row
        return row

    def update_specialist(self, specialist_id: str, **kwargs: Any) -> Any | None:
        for row in self._specialists:
            if row["id"] == specialist_id:
                row.update(kwargs)
                return row
        return None

    def delete_specialist(self, specialist_id: str) -> bool:
        before = len(self._specialists)
        self._specialists = [row for row in self._specialists if row["id"] != specialist_id]
        return len(self._specialists) < before


def test_specialists_crud(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    svc = SpecialistsService(store)
    baseline = len(svc.list())

    created = svc.create(
        name="Fold Expert",
        slug="fold-expert",
        description="Structures",
        instructions="Focus on folding.",
        skill_names=["fold"],
        mcp_catalog_ids=["tamarind"],
    )
    assert created.slug == "fold-expert"
    assert len(svc.list()) == baseline + 1
    assert svc.get(created.id) is not None

    updated = svc.update(
        created.id,
        name="Fold Pro",
        update_description=True,
        description="Updated",
        enabled=False,
    )
    assert updated is not None
    assert updated.name == "Fold Pro"
    assert updated.enabled is False

    assert svc.delete(created.id) is True
    assert svc.get(created.id) is None
    assert svc.delete("missing") is False


def test_ensure_default_specialists_seeds_once():
    store = _FakeStore()
    first = ensure_default_specialists(store)
    assert len(first) == len(DEFAULT_SPECIALISTS)
    assert store.get_meta(DEFAULT_SPECIALISTS_SEEDED_META_KEY) == "1"

    second = ensure_default_specialists(store)
    assert second == []
    assert len(store.list_specialists()) == len(DEFAULT_SPECIALISTS)


def test_ensure_default_specialists_marks_existing_store():
    store = _FakeStore()
    store.create_specialist(name="Custom", slug="custom")
    created = ensure_default_specialists(store)
    assert created == []
    assert len(store.list_specialists()) == 1
    assert store.get_meta(DEFAULT_SPECIALISTS_SEEDED_META_KEY) == "1"


def test_filter_mcp_servers_for_specialist():
    servers = [
        {"id": "srv-1", "catalog_id": "tamarind", "name": "Tamarind"},
        {"id": "srv-2", "catalog_id": "linear", "name": "Linear"},
        {"id": "srv-3", "name": "Custom"},
    ]
    by_catalog = filter_mcp_servers_for_specialist(
        servers,
        mcp_server_ids=None,
        mcp_catalog_ids=["tamarind"],
    )
    assert len(by_catalog) == 1
    assert by_catalog[0]["catalog_id"] == "tamarind"

    by_server = filter_mcp_servers_for_specialist(
        servers,
        mcp_server_ids=["srv-3"],
        mcp_catalog_ids=None,
    )
    assert len(by_server) == 1
    assert by_server[0]["id"] == "srv-3"

    empty = filter_mcp_servers_for_specialist(servers, mcp_server_ids=[], mcp_catalog_ids=[])
    assert empty == []
