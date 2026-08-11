"""Unit tests for /mcps modal helpers."""

from __future__ import annotations

from ui.terminal.mcp_modal import (
    build_mcp_rows,
    first_selectable_index,
    mcp_insert_token,
    mcp_meta_label,
    run_mcp_modal,
)


def _server(
    *,
    id: str = "latch",
    name: str = "Latch Bio",
    enabled: bool = True,
    status: str = "connected",
    transport: str = "streamable_http",
    description: str = "Bioinformatics workflows",
):
    return {
        "kind": "catalog",
        "id": id,
        "name": name,
        "description": description,
        "enabled": enabled,
        "status": status,
        "transport": transport,
        "target": "https://mcp.latch.bio/mcp",
        "auth": "oauth",
        "ref": id,
        "insert_key": id,
    }


def test_mcp_insert_token():
    assert mcp_insert_token(_server()) == "mcp: latch"
    assert mcp_insert_token({"insert_key": "My Server"}) == "mcp: My_Server"


def test_mcp_meta_label():
    label = mcp_meta_label(_server())
    assert label.startswith("on")
    assert "latch" in label
    assert "http" in label


def test_build_mcp_rows_sections():
    rows = build_mcp_rows(
        [
            _server(id="a", name="A", enabled=True),
            _server(id="b", name="B", enabled=False, status="off"),
        ]
    )
    titles = [r.title for r in rows]
    assert titles[0] == "Enabled"
    assert "Disabled" in titles


def test_build_mcp_rows_search():
    rows = build_mcp_rows(
        [
            _server(id="latch", name="Latch Bio", description="workflows"),
            _server(id="tavily", name="Tavily", description="search"),
        ],
        query="workflow",
    )
    names = [r.title for r in rows if r.kind == "mcp"]
    assert names == ["Latch Bio"]


def test_first_selectable_skips_headers():
    rows = build_mcp_rows([_server()])
    assert rows[0].kind == "header"
    assert first_selectable_index(rows) == 1


def test_run_mcp_modal_skips_under_pytest():
    assert run_mcp_modal(object()) is False


def test_find_and_style_mcp_chips():
    from ui.terminal.attachments import find_mcp_chips, style_with_image_chips

    text = "mcp: latch what tools?"
    assert find_mcp_chips(text) == ["mcp: latch"]
    frags = style_with_image_chips(text, "class:transcript-user")
    chip = "".join(t for s, t in frags if "mcp-chip" in s)
    assert chip == "mcp: latch"


def test_user_message_renders_mcp_chip():
    from ui.terminal.transcript.render import entry_rows
    from ui.terminal.transcript.store import TranscriptStore

    store = TranscriptStore()
    store.append_text("mcp: tamarind check status", kind="user")
    rows = entry_rows(store.entries[0], width=80)
    chip_text = "".join(
        t for _e, _i, frags in rows for s, t in frags if "mcp-chip" in s
    )
    assert chip_text == "mcp: tamarind"
