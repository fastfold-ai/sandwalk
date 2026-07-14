"""Backfill curated specialist tool allowlists."""

from __future__ import annotations

from pathlib import Path

from agent_server.default_specialists import (
    DEFAULT_SPECIALIST_TOOL_NAMES_META_KEY,
    ensure_default_specialist_tool_names,
)
from agent_server.store import AgentStore


def test_backfill_fills_empty_default_tool_names(tmp_path: Path):
    store = AgentStore(tmp_path / "specs.db")
    for specialist in store.list_specialists():
        if specialist.slug == "fast-computational-scientist":
            continue
        store.update_specialist(specialist.id, tool_names=[])
    with store._write_lock, store._connect() as connection:
        connection.execute(
            "DELETE FROM store_meta WHERE key = ?",
            (DEFAULT_SPECIALIST_TOOL_NAMES_META_KEY,),
        )

    updated = ensure_default_specialist_tool_names(store)
    assert updated >= 7
    for specialist in store.list_specialists():
        assert specialist.tool_names, specialist.slug

    # Second call is a no-op.
    assert ensure_default_specialist_tool_names(store) == 0
