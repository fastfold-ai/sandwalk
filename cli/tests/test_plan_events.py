"""Tests for plan.created payload helpers and emit_events wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from agent_server.service.emit_events import make_event_emitter
from agent_server.service.plan_events import (
    is_plans_markdown_path,
    plan_created_payload_from_tool_call,
    title_and_summary_from_markdown,
    title_from_path,
    workspace_relative_plans_path,
)


def test_is_plans_markdown_path():
    assert is_plans_markdown_path("/ws/plans/foo.md")
    assert is_plans_markdown_path("plans/foo.md")
    assert not is_plans_markdown_path("/ws/artifacts/foo.md")
    assert not is_plans_markdown_path("/ws/plans/foo.txt")


def test_title_and_summary_from_markdown():
    title, summary = title_and_summary_from_markdown(
        "# Nice Plan\n\nDo the thing carefully.\n",
        fallback_title="Fallback",
    )
    assert title == "Nice Plan"
    assert summary.startswith("Do the thing")

    title, summary = title_and_summary_from_markdown(
        "## Not H1\n\n" + ("x" * 300) + "\n",
        fallback_title="Fallback",
    )
    assert title == "Fallback"
    assert summary.endswith("...")
    assert len(summary) <= 280

    title, summary = title_and_summary_from_markdown(
        "# \n\n```\nskipped-fence-open\n",
        fallback_title="Fallback",
    )
    assert title == "Fallback"
    # Fence opener is skipped; first non-fence content becomes summary.
    assert summary == "skipped-fence-open"


def test_workspace_relative_and_title_from_path():
    assert workspace_relative_plans_path(r"C:\ws\plans\foo.md") == "plans/foo.md"
    assert workspace_relative_plans_path("plans/bar.md") == "plans/bar.md"
    assert workspace_relative_plans_path("only.md") == "plans/only.md"
    assert title_from_path("plans/my_cool-plan.md") == "my cool plan"
    assert title_from_path("") == "Plan"


def test_plan_created_payload_from_create_file():
    payload = plan_created_payload_from_tool_call(
        name="files.create_file",
        arguments={
            "path": "/Users/x/.sandwalk/workspaces/abc/plans/boltz-campaign.md",
            "content": "# Boltz campaign\n\nRun a small design loop.\n",
        },
    )
    assert payload is not None
    assert payload["path"] == "plans/boltz-campaign.md"
    assert payload["title"] == "Boltz campaign"
    assert "design loop" in payload["summary"]


def test_plan_created_payload_fallbacks_and_rejects():
    assert (
        plan_created_payload_from_tool_call(
            name="read_file",
            arguments={"path": "artifacts/note.txt"},
        )
        is None
    )
    payload = plan_created_payload_from_tool_call(
        name="custom_write_thing",
        arguments={},
        output={"path": "/tmp/ws/plans/from-output.md", "content": "Hello summary\n"},
    )
    assert payload is not None
    assert payload["path"] == "plans/from-output.md"
    assert payload["title"] == "from output"
    assert payload["summary"] == "Hello summary"

    assert (
        plan_created_payload_from_tool_call(
            name="files.create_file",
            arguments={"path": "artifacts/note.md"},
        )
        is None
    )


def test_emit_runtime_event_appends_plan_created():
    store = MagicMock()
    # Events are dropped unless the session is still active, so give the mock a
    # running status instead of a bare Mock attribute.
    store.get_session.return_value = SimpleNamespace(status="running")
    emit = make_event_emitter(store, "sess-1", "run-1")
    emit(
        "tool_start",
        name="files.create_file",
        arguments={
            "path": "/tmp/ws/plans/demo.md",
            "content": "# Demo\n\nOverview text.\n",
        },
        tool_call_id="tc-1",
    )
    types = [c.kwargs["event_type"] for c in store.append_event.call_args_list]
    assert "tool.started" in types
    assert "plan.created" in types
    plan_call = next(
        c for c in store.append_event.call_args_list if c.kwargs["event_type"] == "plan.created"
    )
    assert plan_call.kwargs["payload"]["path"] == "plans/demo.md"


def test_emit_runtime_event_drops_events_after_stop():
    """A worker thread that outlives Stop must not repaint the UI."""
    store = MagicMock()
    store.get_session.return_value = SimpleNamespace(status="interrupted")
    emit = make_event_emitter(store, "sess-1", "run-1")
    emit(
        "tool_start",
        name="files.create_file",
        arguments={"path": "/tmp/ws/plans/demo.md", "content": "# Demo\n"},
        tool_call_id="tc-1",
    )
    store.append_event.assert_not_called()
