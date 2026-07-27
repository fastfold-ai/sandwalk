"""App Home Block Kit for the relay Slack app."""

from __future__ import annotations

from datetime import datetime, timezone

from agent_server.connectors.slack_home import (
    HomeSessionRow,
    HomeStatus,
    build_home_blocks,
    build_home_view,
    dashboard_base_url,
    is_home_opened,
    session_url,
    user_ref,
)


def test_is_home_opened() -> None:
    assert is_home_opened({"type": "app_home_opened", "tab": "home"})
    assert not is_home_opened({"type": "app_home_opened", "tab": "messages"})
    assert not is_home_opened({"type": "app_context_changed", "tab": "home"})


def test_user_ref() -> None:
    assert user_ref({"user": "U1"}) == "U1"
    assert user_ref({}) is None


def test_home_view_includes_welcome_and_empty_recent() -> None:
    view = build_home_view([], bot_name="sandwalk")
    assert view["type"] == "home"
    blob = str(view["blocks"])
    assert "Welcome to Sandwalk" in blob
    assert "@sandwalk" in blob
    assert "No Slack sessions yet" in blob
    assert "Open Sandwalk" in blob
    assert "FastFold Integration" in blob
    assert "cloud.fastfold.ai/integrations/sandwalk" in blob


def test_home_blocks_list_recent_sessions_as_links() -> None:
    blocks = build_home_blocks(
        [
            HomeSessionRow(
                id="s1",
                title="hey you",
                source_label="DM · Acme",
                updated_at=datetime.now(timezone.utc),
            )
        ]
    )
    blob = str(blocks)
    assert "Recent threads" in blob
    assert "hey you" in blob
    assert "DM · Acme" in blob
    assert session_url("s1") in blob


def test_recent_session_without_id_is_not_a_link() -> None:
    blocks = build_home_blocks([HomeSessionRow(title="no id here")])
    blob = str(blocks)
    assert "no id here" in blob
    assert "<http" not in blob


def test_recent_session_link_is_not_bold_wrapped() -> None:
    """Slack does not combine `*<url|text>*` cleanly — link text stays plain."""
    blocks = build_home_blocks([HomeSessionRow(id="s1", title="hey you")])
    blob = str(blocks)
    link = f"<{session_url('s1')}|hey you>"
    assert link in blob
    assert f"*{link}*" not in blob


def test_session_url_uses_local_serve_host_and_port(monkeypatch) -> None:
    monkeypatch.delenv("SANDWALK_DASHBOARD_BASE_URL", raising=False)
    monkeypatch.setenv("FASTFOLD_SERVE_HOST", "127.0.0.1")
    monkeypatch.setenv("FASTFOLD_SERVE_PORT", "8787")
    assert session_url("abc") == "http://127.0.0.1:8787/agents/abc"


def test_dashboard_base_url_prefers_menubar_override(monkeypatch) -> None:
    monkeypatch.setenv("SANDWALK_DASHBOARD_BASE_URL", "http://127.0.0.1:8969/")
    monkeypatch.setenv("FASTFOLD_SERVE_PORT", "8787")
    assert dashboard_base_url() == "http://127.0.0.1:8969"
    assert session_url("abc") == "http://127.0.0.1:8969/agents/abc"


def test_status_defaults_to_off() -> None:
    blob = str(build_home_blocks([]))
    assert "Not connected" in blob


def test_status_reflects_live_relay_and_workspace() -> None:
    status = HomeStatus(relay_state="live", team_name="Acme")
    blob = str(build_home_blocks([], status=status))
    assert "Connected" in blob
    assert "Acme" in blob


def test_status_shows_detail_when_not_live() -> None:
    status = HomeStatus(
        relay_state="signed_out",
        relay_detail="Connect FastFold Cloud to receive Slack messages.",
    )
    blob = str(build_home_blocks([], status=status))
    assert "FastFold account not linked" in blob
    assert "Connect FastFold Cloud" in blob


def test_status_shows_account_email_when_known() -> None:
    status = HomeStatus(relay_state="live", account_email="julio@fastfold.ai")
    blob = str(build_home_blocks([], status=status))
    assert "julio@fastfold.ai" in blob


def test_status_falls_back_to_user_id_without_email() -> None:
    status = HomeStatus(relay_state="live", account_user_id="U123")
    blob = str(build_home_blocks([], status=status))
    assert "U123" in blob
