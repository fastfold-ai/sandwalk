"""CLI specialist list/show/active and create/update/delete helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from rich.table import Table

from agent.specialists_manage import crud, display
from agent.specialists_manage import state as specialist_state


def _specialist(**overrides: Any) -> SimpleNamespace:
    fields: dict[str, Any] = {
        "id": "sp-fold",
        "name": "Fold Lab",
        "slug": "fold-lab",
        "description": "Protein folding",
        "instructions": "Prefer experimental structures.\nCite the source.",
        "color": "teal",
        "icon": "flask",
        "skill_names": ["fold", "dock"],
        "mcp_server_ids": ["mcp-a", "mcp-b"],
        "mcp_catalog_ids": ["cat-a"],
        "enabled": True,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _printed(console: MagicMock) -> str:
    chunks: list[str] = []
    for call in console.print.call_args_list:
        if not call.args:
            continue
        chunks.append(str(call.args[0]))
    return "\n".join(chunks)


class _FakeStore:
    """In-memory specialist store. Never opens ~/.sandwalk."""

    def __init__(self) -> None:
        self.specialists: list[SimpleNamespace] = []
        self.created: list[dict[str, Any]] = []
        self.updated: list[tuple[str, dict[str, Any]]] = []
        self.deleted: list[str] = []
        self.create_error: str | None = None
        self.update_error: str | None = None
        self.force_update_none = False

    def list_specialists(self) -> list[SimpleNamespace]:
        return list(self.specialists)

    def resolve_specialist_ref(self, ref: str) -> SimpleNamespace | None:
        key = (ref or "").strip()
        if not key:
            return None
        lowered = key.lower()
        for item in self.specialists:
            if item.id == key or item.slug == key or item.name.strip().lower() == lowered:
                return item
        return None

    def create_specialist(self, **kwargs: Any) -> SimpleNamespace:
        if self.create_error is not None:
            raise ValueError(self.create_error)
        spec = _specialist(
            id=f"id-{len(self.specialists) + 1}",
            name=kwargs["name"],
            slug=kwargs.get("slug") or "generated",
            description=kwargs.get("description"),
            instructions=kwargs.get("instructions"),
            color=kwargs.get("color", "ink"),
            icon=kwargs.get("icon", "agent"),
            skill_names=list(kwargs.get("skill_names") or []),
            mcp_server_ids=list(kwargs.get("mcp_server_ids") or []),
            mcp_catalog_ids=[],
            enabled=True,
        )
        self.created.append(kwargs)
        self.specialists.append(spec)
        return spec

    def update_specialist(self, specialist_id: str, **kwargs: Any) -> SimpleNamespace | None:
        self.updated.append((specialist_id, kwargs))
        if self.update_error is not None:
            raise ValueError(self.update_error)
        if self.force_update_none:
            return None
        current = next((item for item in self.specialists if item.id == specialist_id), None)
        if current is None:
            return None
        if kwargs.get("name") is not None:
            current.name = kwargs["name"]
        if kwargs.get("slug") is not None:
            current.slug = kwargs["slug"]
        return current

    def delete_specialist(self, specialist_id: str) -> bool:
        self.deleted.append(specialist_id)
        self.specialists = [item for item in self.specialists if item.id != specialist_id]
        return True


def _install_store(monkeypatch, store: _FakeStore) -> None:
    def _store() -> _FakeStore:
        return store

    monkeypatch.setattr(display, "_store", _store)
    monkeypatch.setattr(crud, "_store", _store)
    monkeypatch.setattr(specialist_state, "_store", _store)


def test_cmd_list_empty(monkeypatch) -> None:
    _install_store(monkeypatch, _FakeStore())
    console = MagicMock()

    assert display.cmd_list(console) == 0

    text = _printed(console)
    assert "No specialists yet." in text
    assert "fastfold specialists create" in text


def test_cmd_list_marks_active_and_counts_mcps(monkeypatch) -> None:
    store = _FakeStore()
    active = _specialist()
    bare = _specialist(
        id="sp-bare",
        name="Bare",
        slug="bare",
        description=None,
        instructions=None,
        skill_names=None,
        mcp_server_ids=None,
    )
    del bare.mcp_catalog_ids
    store.specialists.extend([active, bare])
    _install_store(monkeypatch, store)
    specialist_state.set_active_specialist_ref(active.slug)
    console = MagicMock()

    assert display.cmd_list(console) == 0

    table = next(
        call.args[0]
        for call in console.print.call_args_list
        if call.args and isinstance(call.args[0], Table)
    )
    assert table.row_count == 2
    assert "Specialists (2)" in str(table.title)
    text = _printed(console)
    assert "CLI active:" in text
    assert "Fold Lab" in text
    assert "/specialist clear" in text


def test_cmd_list_without_active_specialist(monkeypatch) -> None:
    store = _FakeStore()
    store.specialists.append(
        _specialist(description="  ", skill_names=[], mcp_server_ids=[], mcp_catalog_ids=[])
    )
    _install_store(monkeypatch, store)
    console = MagicMock()

    assert display.cmd_list(console) == 0

    assert "CLI active: none (global skills/MCPs)" in _printed(console)


def test_cmd_show_missing_and_inactive(monkeypatch) -> None:
    store = _FakeStore()
    sparse = SimpleNamespace(
        id="sp-sparse",
        name="Sparse",
        slug="sparse",
        description="",
        instructions="",
        color="ink",
        icon="agent",
        skill_names=[],
        mcp_server_ids=[],
        enabled=True,
    )
    store.specialists.append(sparse)
    _install_store(monkeypatch, store)
    console = MagicMock()

    assert display.cmd_show(console, "missing") == 1
    assert "Specialist not found:" in _printed(console)
    assert "missing" in _printed(console)

    console.reset_mock()
    assert display.cmd_show(console, "sparse") == 0
    text = _printed(console)
    assert "Sparse" in text
    assert "(none)" in text
    assert "Currently active" not in text


def test_cmd_show_prints_details_when_active(monkeypatch) -> None:
    store = _FakeStore()
    spec = _specialist()
    store.specialists.append(spec)
    _install_store(monkeypatch, store)
    specialist_state.set_active_specialist_ref(spec.slug)
    console = MagicMock()

    assert display.cmd_show(console, spec.id) == 0

    text = _printed(console)
    assert "Protein folding" in text
    assert "fold, dock" in text
    assert "mcp-a, mcp-b" in text
    assert "cat-a" in text
    assert "Prefer experimental structures." in text
    assert "Cite the source." in text
    assert "Currently active for CLI runs." in text


def test_cmd_active_none_and_set(monkeypatch) -> None:
    store = _FakeStore()
    _install_store(monkeypatch, store)
    console = MagicMock()

    assert display.cmd_active(console) == 0
    assert "No active specialist" in _printed(console)

    spec = _specialist()
    store.specialists.append(spec)
    specialist_state.set_active_specialist_ref(spec.slug)
    console.reset_mock()
    assert display.cmd_active(console) == 0
    text = _printed(console)
    assert "Active for CLI:" in text
    assert spec.name in text
    assert spec.slug in text


def test_cmd_create_success_and_validation_error(monkeypatch) -> None:
    store = _FakeStore()
    _install_store(monkeypatch, store)
    console = MagicMock()

    assert (
        crud.cmd_create(
            console,
            name="Fold Lab",
            slug="fold-lab",
            description="Structures",
            instructions="Be precise.",
            color="teal",
            icon="flask",
            skills=["fold"],
            mcps=["mcp-a"],
        )
        == 0
    )
    assert store.created[0]["skill_names"] == ["fold"]
    assert store.created[0]["mcp_server_ids"] == ["mcp-a"]
    assert "Created specialist" in _printed(console)
    assert "Fold Lab" in _printed(console)

    store.create_error = "Specialist slug already exists: fold-lab"
    console.reset_mock()
    assert crud.cmd_create(console, name="Fold Lab", slug="fold-lab") == 1
    assert "Specialist slug already exists" in _printed(console)


def test_cmd_create_can_set_active(monkeypatch) -> None:
    store = _FakeStore()
    _install_store(monkeypatch, store)
    console = MagicMock()

    assert crud.cmd_create(console, name="Reviewer", slug="reviewer", use=True) == 0

    assert specialist_state.get_active_specialist_ref() == "reviewer"
    assert "Set as active for CLI runs." in _printed(console)


def test_cmd_update_missing(monkeypatch) -> None:
    _install_store(monkeypatch, _FakeStore())
    console = MagicMock()

    assert crud.cmd_update(console, "nope", name="Renamed") == 1
    assert "Specialist not found:" in _printed(console)


def test_cmd_update_applies_fields(monkeypatch) -> None:
    store = _FakeStore()
    spec = _specialist()
    store.specialists.append(spec)
    _install_store(monkeypatch, store)
    console = MagicMock()

    assert (
        crud.cmd_update(
            console,
            spec.slug,
            name="Fold Pro",
            slug="fold-pro",
            description="Updated",
            clear_description=False,
            instructions="New instructions",
            clear_instructions=False,
            color="blue",
            icon="beaker",
            skills=["fold"],
            mcps=["mcp-a"],
        )
        == 0
    )

    specialist_id, kwargs = store.updated[0]
    assert specialist_id == spec.id
    assert kwargs["update_description"] is True
    assert kwargs["update_instructions"] is True
    assert kwargs["skill_names"] == ["fold"]
    assert kwargs["mcp_server_ids"] == ["mcp-a"]
    assert "Updated" in _printed(console)
    assert "Fold Pro" in _printed(console)


def test_cmd_update_clear_flags_and_errors(monkeypatch) -> None:
    store = _FakeStore()
    spec = _specialist()
    store.specialists.append(spec)
    _install_store(monkeypatch, store)
    console = MagicMock()

    assert (
        crud.cmd_update(
            console,
            spec.id,
            clear_description=True,
            clear_instructions=True,
        )
        == 0
    )
    _, kwargs = store.updated[-1]
    assert kwargs["update_description"] is True
    assert kwargs["update_instructions"] is True
    assert kwargs["description"] is None
    assert kwargs["instructions"] is None

    store.update_error = "Specialist name cannot be empty."
    console.reset_mock()
    assert crud.cmd_update(console, spec.slug, name=" ") == 1
    assert "Specialist name cannot be empty." in _printed(console)

    store.update_error = None
    store.force_update_none = True
    console.reset_mock()
    assert crud.cmd_update(console, spec.slug, name="Still Missing") == 1
    assert "Specialist not found:" in _printed(console)


def test_cmd_delete_missing(monkeypatch) -> None:
    _install_store(monkeypatch, _FakeStore())
    console = MagicMock()

    assert crud.cmd_delete(console, "gone") == 1
    assert "Specialist not found:" in _printed(console)


def test_cmd_delete_inactive_specialist(monkeypatch) -> None:
    store = _FakeStore()
    spec = _specialist()
    other = _specialist(id="sp-other", name="Other", slug="other")
    store.specialists.extend([spec, other])
    _install_store(monkeypatch, store)
    specialist_state.set_active_specialist_ref(other.slug)
    console = MagicMock()

    assert crud.cmd_delete(console, spec.name) == 0

    assert store.deleted == [spec.id]
    assert specialist_state.get_active_specialist_ref() == other.slug
    assert "Deleted" in _printed(console)
    assert spec.slug in _printed(console)


def test_cmd_delete_clears_active_ref(monkeypatch) -> None:
    store = _FakeStore()
    spec = _specialist()
    store.specialists.append(spec)
    _install_store(monkeypatch, store)
    specialist_state.set_active_specialist_ref(spec.slug)
    console = MagicMock()

    assert crud.cmd_delete(console, spec.slug) == 0

    assert store.deleted == [spec.id]
    assert specialist_state.get_active_specialist_ref() is None
    assert "Deleted" in _printed(console)


def test_cmd_delete_ignores_stale_active_ref(monkeypatch) -> None:
    store = _FakeStore()
    spec = _specialist()
    store.specialists.append(spec)
    _install_store(monkeypatch, store)
    specialist_state.set_active_specialist_ref("retired-slug")
    console = MagicMock()

    assert crud.cmd_delete(console, spec.id) == 0

    assert specialist_state.get_active_specialist_ref() == "retired-slug"


def test_cmd_use_missing_disabled_and_enabled(monkeypatch) -> None:
    store = _FakeStore()
    disabled = _specialist(id="sp-off", name="Paused", slug="paused", enabled=False)
    enabled = _specialist()
    store.specialists.extend([disabled, enabled])
    _install_store(monkeypatch, store)
    console = MagicMock()

    assert crud.cmd_use(console, "missing") == 1
    assert "Specialist not found:" in _printed(console)

    console.reset_mock()
    assert crud.cmd_use(console, disabled.slug) == 1
    text = _printed(console)
    assert "Specialist is disabled:" in text
    assert "Paused" in text
    assert "Dashboard → Specialists" in text
    assert specialist_state.get_active_specialist_ref() is None

    console.reset_mock()
    assert crud.cmd_use(console, enabled.slug) == 0
    assert specialist_state.get_active_specialist_ref() == enabled.slug
    text = _printed(console)
    assert "Active specialist" in text
    assert "CLI runs will use only this specialist's skills" in text


def test_cmd_clear(monkeypatch) -> None:
    _install_store(monkeypatch, _FakeStore())
    specialist_state.set_active_specialist_ref("fold-lab")
    console = MagicMock()

    assert crud.cmd_clear(console) == 0

    assert specialist_state.get_active_specialist_ref() is None
    text = _printed(console)
    assert "Cleared active specialist." in text
    assert "global skills/MCPs" in text
