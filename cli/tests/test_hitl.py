"""Unit tests for Deep Agents HITL helpers and approvals API."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.hitl.broker import ApprovalBroker
from agent.hitl.cli_prompt import collect_cli_decisions
from agent.hitl.config import (
    SKILLS_MANAGE_TOOL,
    build_interrupt_on,
    skills_manage_needs_approval,
    skills_manage_when,
)
from agent.hitl.decisions import (
    build_approve,
    build_edit,
    build_reject,
    validate_decisions,
)


def test_skills_manage_predicate_gates_sensitive_actions():
    assert skills_manage_needs_approval({"action": "install", "source": "x"})
    assert skills_manage_needs_approval({"action": "add"})
    assert skills_manage_needs_approval({"action": "remove", "name": "y"})
    assert skills_manage_needs_approval({"action": "uninstall"})
    assert skills_manage_needs_approval({"action": "create", "install": True})
    assert not skills_manage_needs_approval({"action": "create"})  # draft only
    assert not skills_manage_needs_approval({"action": "create", "install": False})
    assert not skills_manage_needs_approval({"action": "find", "query": "fold"})
    assert not skills_manage_needs_approval({"action": "list"})
    assert not skills_manage_needs_approval({"action": "info", "name": "fold"})


def test_skills_manage_when_reads_tool_call_args():
    class _Req:
        tool_call = {"name": SKILLS_MANAGE_TOOL, "args": {"action": "install"}}

    assert skills_manage_when(_Req()) is True

    class _Find:
        tool_call = {"name": SKILLS_MANAGE_TOOL, "args": {"action": "find"}}

    assert skills_manage_when(_Find()) is False


def test_build_interrupt_on_config():
    config = build_interrupt_on()
    assert SKILLS_MANAGE_TOOL in config
    assert config[SKILLS_MANAGE_TOOL]["allowed_decisions"] == [
        "approve",
        "edit",
        "reject",
    ]
    assert callable(config[SKILLS_MANAGE_TOOL]["when"])


def test_validate_decisions_ordering_and_edit():
    actions = [
        {"name": "skills_manage", "args": {"action": "install", "source": "a/b"}},
        {"name": "skills_manage", "args": {"action": "remove", "name": "x"}},
    ]
    configs = [
        {
            "action_name": "skills_manage",
            "allowed_decisions": ["approve", "edit", "reject"],
        }
    ]
    decisions = validate_decisions(
        [
            build_edit(name="skills_manage", args={"action": "install", "source": "c/d"}),
            build_reject("No thanks"),
        ],
        action_requests=actions,
        review_configs=configs,
    )
    assert decisions[0]["type"] == "edit"
    assert decisions[0]["edited_action"]["args"]["source"] == "c/d"
    assert decisions[1]["type"] == "reject"
    assert "No thanks" in decisions[1]["message"]


def test_validate_decisions_rejects_count_mismatch():
    with pytest.raises(ValueError, match="Expected 1"):
        validate_decisions(
            [build_approve(), build_approve()],
            action_requests=[{"name": "skills_manage", "args": {}}],
            review_configs=[],
        )


def test_validate_decisions_rejects_disallowed_type():
    with pytest.raises(ValueError, match="not allowed"):
        validate_decisions(
            [{"type": "respond", "message": "hi"}],
            action_requests=[{"name": "skills_manage", "args": {}}],
            review_configs=[
                {
                    "action_name": "skills_manage",
                    "allowed_decisions": ["approve", "edit", "reject"],
                }
            ],
        )


def test_cli_collector_auto_rejects_without_tty(monkeypatch):
    monkeypatch.setattr("agent.hitl.cli_prompt._stdin_is_tty", lambda: False)
    decisions = collect_cli_decisions(
        action_requests=[
            {"name": "skills_manage", "args": {"action": "install", "source": "x"}}
        ],
        review_configs=[
            {
                "action_name": "skills_manage",
                "allowed_decisions": ["approve", "edit", "reject"],
            }
        ],
    )
    assert len(decisions) == 1
    assert decisions[0]["type"] == "reject"
    assert "Non-interactive" in decisions[0]["message"]


def test_approval_broker_wait_and_submit():
    broker = ApprovalBroker()
    iid = broker.begin(
        "sess-1",
        action_requests=[{"name": "skills_manage", "args": {"action": "install"}}],
        review_configs=[
            {
                "action_name": "skills_manage",
                "allowed_decisions": ["approve", "edit", "reject"],
            }
        ],
    )
    holder: list = []

    def waiter():
        holder.append(broker.wait("sess-1", timeout=2.0))

    thread = threading.Thread(target=waiter)
    thread.start()
    broker.submit("sess-1", [build_approve()], interrupt_id=iid)
    thread.join(timeout=2.0)
    assert holder and holder[0][0]["type"] == "approve"


def test_ptc_gate_skips_find_action():
    from agent.hitl.ptc_gate import apply_skills_manage_hitl

    kwargs = {"action": "find", "query": "calendar"}
    assert apply_skills_manage_hitl(kwargs) is None


def test_ptc_gate_blocks_install_until_approve(monkeypatch):
    from agent.hitl import set_hitl_context, reset_hitl_context
    from agent.hitl.ptc_gate import apply_skills_manage_hitl

    events: list[str] = []

    def progress(event: str, **payload):
        events.append(event)

    token = set_hitl_context(
        session_id="sess-ptc",
        headless=True,
        progress_callback=progress,
    )
    try:
        from agent.hitl import get_approval_broker

        broker = get_approval_broker()

        def submit_later():
            import time

            time.sleep(0.05)
            pending = broker.get_pending("sess-ptc")
            assert pending is not None
            broker.submit("sess-ptc", [build_approve()])

        thread = threading.Thread(target=submit_later)
        thread.start()
        kwargs = {"action": "install", "source": "googleworkspace/cli@gws-calendar"}
        blocked = apply_skills_manage_hitl(kwargs)
        thread.join(timeout=2.0)
        assert blocked is None
        assert "approval_required" in events
        assert "approval_resolved" in events
    finally:
        reset_hitl_context(token)


def test_ptc_gate_reject_returns_blocked_result(monkeypatch):
    from agent.hitl import set_hitl_context, reset_hitl_context
    from agent.hitl.ptc_gate import apply_skills_manage_hitl

    monkeypatch.setattr(
        "agent.hitl.ptc_gate.collect_decisions_for_interrupt",
        lambda **kwargs: [build_reject("Nope")],
    )
    token = set_hitl_context(session_id="s", headless=True)
    try:
        out = apply_skills_manage_hitl(
            {"action": "remove", "name": "gws-calendar"}
        )
    finally:
        reset_hitl_context(token)
    assert out is not None
    assert out["blocked"] is True
    assert out["ok"] is False
    assert "Nope" in out["summary"]


def test_approve_remaining_skips_later_ptc_removes(monkeypatch):
    from agent.hitl import clear_session_grants, reset_hitl_context, set_hitl_context
    from agent.hitl.grants import has_grant
    from agent.hitl.ptc_gate import apply_skills_manage_hitl

    calls = {"n": 0}

    def collect(**kwargs):
        calls["n"] += 1
        return [build_approve(scope="remaining")]

    monkeypatch.setattr(
        "agent.hitl.ptc_gate.collect_decisions_for_interrupt",
        collect,
    )
    token = set_hitl_context(session_id="sess-batch", headless=True)
    try:
        first = apply_skills_manage_hitl({"action": "remove", "name": "gws-chat"})
        assert first is None
        assert calls["n"] == 1
        assert has_grant("skills_manage:remove", session_id="sess-batch")

        second = apply_skills_manage_hitl(
            {"action": "remove", "name": "gws-chat-send"}
        )
        assert second is None
        assert calls["n"] == 1  # no second prompt
    finally:
        clear_session_grants("sess-batch")
        reset_hitl_context(token)


def test_broker_submit_approve_grants_session_without_contextvar():
    """UI submit must grant even when the waiter thread has no ContextVar."""
    from agent.hitl.grants import clear_session_grants, has_grant

    clear_session_grants("sess-ui")
    broker = ApprovalBroker()
    iid = broker.begin(
        "sess-ui",
        action_requests=[
            {"name": "skills_manage", "args": {"action": "remove", "name": "a"}}
        ],
        review_configs=[
            {
                "action_name": "skills_manage",
                "allowed_decisions": ["approve", "edit", "reject"],
            }
        ],
    )
    holder: list = []

    def waiter():
        holder.append(broker.wait("sess-ui", timeout=2.0))

    thread = threading.Thread(target=waiter)
    thread.start()
    # Plain approve (no scope) still grants remaining for skills_manage.
    broker.submit("sess-ui", [{"type": "approve"}], interrupt_id=iid)
    thread.join(timeout=2.0)
    assert holder and holder[0][0]["type"] == "approve"
    assert has_grant("skills_manage:remove", session_id="sess-ui")
    clear_session_grants("sess-ui")


def test_session_grant_works_when_context_grants_empty():
    """Worker threads may share session_id via ContextVar but miss ctx.grants."""
    from agent.hitl import get_hitl_context, reset_hitl_context, set_hitl_context
    from agent.hitl.grants import clear_session_grants, grant_remaining, has_grant
    from agent.hitl.ptc_gate import apply_skills_manage_hitl

    clear_session_grants("sess-orphan")
    token = set_hitl_context(session_id="sess-orphan", headless=True)
    try:
        grant_remaining("skills_manage:remove", session_id="sess-orphan")
        ctx = get_hitl_context()
        assert ctx is not None
        ctx.grants.clear()  # simulate grant recorded only in session store
        assert has_grant("skills_manage:remove", session_id="sess-orphan")
        assert apply_skills_manage_hitl({"action": "remove", "name": "gws-x"}) is None
    finally:
        clear_session_grants("sess-orphan")
        reset_hitl_context(token)


def test_skills_manage_when_respects_run_grant():
    from agent.hitl import clear_session_grants, reset_hitl_context, set_hitl_context
    from agent.hitl.grants import grant_remaining

    class _Req:
        tool_call = {"name": SKILLS_MANAGE_TOOL, "args": {"action": "remove", "name": "x"}}

    token = set_hitl_context(session_id="s", headless=True)
    try:
        assert skills_manage_when(_Req()) is True
        grant_remaining("skills_manage:remove", session_id="s")
        assert skills_manage_when(_Req()) is False
    finally:
        clear_session_grants("s")
        reset_hitl_context(token)


def test_validate_decisions_keeps_approve_remaining_scope():
    decisions = validate_decisions(
        [{"type": "approve", "scope": "remaining"}],
        action_requests=[{"name": "skills_manage", "args": {"action": "remove"}}],
        review_configs=[
            {
                "action_name": "skills_manage",
                "allowed_decisions": ["approve", "edit", "reject"],
            }
        ],
    )
    assert decisions[0]["type"] == "approve"
    assert decisions[0]["scope"] == "remaining"


def test_approvals_http_rejects_mismatched_count(tmp_path: Path, monkeypatch):
    from agent.config import Config
    from agent.hitl import get_approval_broker
    from agent_server.app import create_app

    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        created = client.post("/v1/sessions", json={"title": "HITL"})
        assert created.status_code == 201
        session_id = created.json()["id"]

        get_approval_broker().begin(
            session_id,
            action_requests=[
                {"name": "skills_manage", "args": {"action": "install"}},
                {"name": "skills_manage", "args": {"action": "remove"}},
            ],
            review_configs=[
                {
                    "action_name": "skills_manage",
                    "allowed_decisions": ["approve", "edit", "reject"],
                }
            ],
        )

        response = client.post(
            f"/v1/sessions/{session_id}/approvals",
            json={"decisions": [{"type": "approve"}]},
        )
    assert response.status_code == 400
    assert "Expected 2" in response.json()["detail"]
