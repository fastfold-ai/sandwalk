"""`/v1/connectors/slack/*` HTTP surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_server.app import create_app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        yield client


def connect_workspace(client: TestClient, team_id: str = "T1") -> None:
    """Seed a workspace directly — connecting for real would call Slack."""
    store = client.app.state.store
    store.upsert_slack_workspace(
        team_id=team_id, mode="socket", team_name="Acme", bot_user_id="BBOT"
    )


def test_status_starts_empty(client: TestClient) -> None:
    body = client.get("/v1/connectors/slack/status").json()
    assert body["mode"] is None
    assert body["relayState"] == "off"
    assert body["workspaces"] == []


def test_manifest_is_valid_json_with_socket_mode(client: TestClient) -> None:
    body = client.get("/v1/connectors/slack/manifest").json()
    assert body["appName"] == "Sandwalk"
    assert body["steps"]

    manifest = json.loads(body["manifest"])
    settings = manifest["settings"]
    assert settings["socket_mode_enabled"] is True
    # Slack rejects event subscriptions without either a Request URL or Socket
    # Mode, and interactivity has the same rule.
    assert settings["interactivity"]["is_enabled"] is True
    assert "app_mention" in settings["event_subscriptions"]["bot_events"]

    scopes = manifest["oauth_config"]["scopes"]["bot"]
    for required in ("app_mentions:read", "chat:write", "channels:history"):
        assert required in scopes


def test_manifest_honours_a_custom_app_name(client: TestClient) -> None:
    body = client.get("/v1/connectors/slack/manifest", params={"app_name": "Acme Bot"}).json()
    manifest = json.loads(body["manifest"])
    assert manifest["display_information"]["name"] == "Acme Bot"
    assert manifest["features"]["bot_user"]["display_name"] == "Acme Bot"


def test_connect_rejects_a_missing_app_token(client: TestClient) -> None:
    response = client.post(
        "/v1/connectors/slack/connect",
        json={"botToken": "xoxb-x", "appToken": "xoxb-oops"},
    )
    assert response.status_code == 400
    assert "xapp-" in response.json()["detail"]


def test_workspaces_never_expose_tokens(client: TestClient) -> None:
    connect_workspace(client)
    client.app.state.store.upsert_slack_workspace(
        team_id="T1", mode="socket", bot_token="xoxb-secret", app_token="xapp-secret"
    )

    body = client.get("/v1/connectors/slack/workspaces").json()
    assert body["data"][0]["hasBotToken"] is True
    assert "xoxb-secret" not in json.dumps(body)


def test_workspace_needs_reauth_round_trips(client: TestClient) -> None:
    connect_workspace(client)
    store = client.app.state.store
    assert store.get_slack_workspace("T1").needs_reauth is False

    store.set_slack_workspace_reauth("T1", needs_reauth=True)
    body = client.get("/v1/connectors/slack/workspaces").json()
    assert body["data"][0]["needsReauth"] is True


def test_import_one_click_accepts_a_reauth_team_id(client: TestClient) -> None:
    """Routing/param wiring only — no FastFold Cloud key is configured here,
    so this exercises the same "not signed in" error either way."""
    response = client.post(
        "/v1/connectors/slack/connect/one-click/import",
        params={"reauth_team_id": "T1"},
    )
    assert response.status_code == 400
    assert "Connect FastFold Cloud" in response.json()["detail"]


def test_people_allowlist_round_trip(client: TestClient) -> None:
    connect_workspace(client)

    listed = client.get("/v1/connectors/slack/workspaces/T1/people").json()
    assert listed["data"] == []

    added = client.post(
        "/v1/connectors/slack/people",
        json={"teamId": "T1", "slackUserId": "U1", "displayName": "Julio"},
    )
    assert added.status_code == 201
    assert added.json()["data"][0]["slackUserId"] == "U1"

    removed = client.delete("/v1/connectors/slack/workspaces/T1/people/U1")
    assert removed.status_code == 200
    assert client.get("/v1/connectors/slack/workspaces/T1/people").json()["data"] == []


def test_people_routes_require_a_connected_workspace(client: TestClient) -> None:
    assert client.get("/v1/connectors/slack/workspaces/T-nope/people").status_code == 404
    response = client.post(
        "/v1/connectors/slack/people", json={"teamId": "T-nope", "slackUserId": "U1"}
    )
    assert response.status_code == 404


def test_subscription_accepts_a_pasted_channel_link(client: TestClient) -> None:
    connect_workspace(client)
    session = client.post("/v1/sessions", json={"title": "Listener"}).json()

    added = client.post(
        "/v1/connectors/slack/subscriptions",
        json={
            "sessionId": session["id"],
            "channel": "https://acme.slack.com/archives/C0456",
        },
    )
    assert added.status_code == 201
    assert added.json()["data"][0]["channel"] == "slack:T1/C0456"

    # Query params stay snake_case across this API (cf. per_page on Library).
    removed = client.delete(
        "/v1/connectors/slack/subscriptions",
        params={"session_id": session["id"], "channel": "slack:T1/C0456"},
    )
    assert removed.status_code == 200
    assert (
        client.get(
            "/v1/connectors/slack/subscriptions",
            params={"session_id": session["id"]},
        ).json()["data"]
        == []
    )


def test_subscription_rejects_garbage_channels(client: TestClient) -> None:
    connect_workspace(client)
    session = client.post("/v1/sessions", json={"title": "Listener"}).json()

    response = client.post(
        "/v1/connectors/slack/subscriptions",
        json={"sessionId": session["id"], "channel": "not a channel!"},
    )
    assert response.status_code == 400


def test_subscription_requires_a_real_session(client: TestClient) -> None:
    connect_workspace(client)
    response = client.post(
        "/v1/connectors/slack/subscriptions",
        json={"sessionId": "nope", "channel": "C1"},
    )
    assert response.status_code == 404


def test_ambiguous_channel_without_a_single_workspace(client: TestClient) -> None:
    connect_workspace(client, "T1")
    connect_workspace(client, "T2")
    session = client.post("/v1/sessions", json={"title": "Listener"}).json()

    # Two workspaces connected, so a bare channel id cannot be resolved.
    response = client.post(
        "/v1/connectors/slack/subscriptions",
        json={"sessionId": session["id"], "channel": "C1"},
    )
    assert response.status_code == 400
    assert "workspace" in response.json()["detail"]


def test_parked_allow_adds_the_sender_and_clears_the_queue(
    client: TestClient,
) -> None:
    connect_workspace(client)
    store = client.app.state.store
    parked = store.park_slack_message(
        team_id="T1",
        channel="slack:T1/C1",
        slack_user_id="U9",
        text="hey",
        user_name="Priya",
    )

    listed = client.get("/v1/connectors/slack/parked").json()
    assert len(listed["data"]) == 1

    allowed = client.post(f"/v1/connectors/slack/parked/{parked.id}/allow")
    assert allowed.status_code == 200
    assert client.get("/v1/connectors/slack/parked").json()["data"] == []

    people = client.get("/v1/connectors/slack/workspaces/T1/people").json()
    assert people["data"][0]["slackUserId"] == "U9"
    assert people["data"][0]["displayName"] == "Priya"


def test_parked_dismiss_does_not_allow_the_sender(client: TestClient) -> None:
    connect_workspace(client)
    store = client.app.state.store
    parked = store.park_slack_message(
        team_id="T1", channel="slack:T1/C1", slack_user_id="U9", text="hey"
    )

    assert client.delete(f"/v1/connectors/slack/parked/{parked.id}").status_code == 200
    assert client.get("/v1/connectors/slack/workspaces/T1/people").json()["data"] == []


def test_parked_actions_404_on_unknown_id(client: TestClient) -> None:
    assert client.post("/v1/connectors/slack/parked/nope/allow").status_code == 404
    assert client.delete("/v1/connectors/slack/parked/nope").status_code == 404


def test_session_mute_round_trip(client: TestClient) -> None:
    session = client.post("/v1/sessions", json={"title": "Muted"}).json()
    path = f"/v1/sessions/{session['id']}/connectors/slack"

    assert client.get(path).json()["muted"] is False
    assert client.put(path, json={"muted": True}).json()["muted"] is True
    assert client.get(path).json()["muted"] is True
    assert client.put(path, json={"muted": False}).json()["muted"] is False


def test_session_mute_requires_a_real_session(client: TestClient) -> None:
    assert client.get("/v1/sessions/nope/connectors/slack").status_code == 404
    assert client.put("/v1/sessions/nope/connectors/slack", json={"muted": True}).status_code == 404


def test_disconnect_removes_the_workspace(client: TestClient) -> None:
    connect_workspace(client)
    assert client.delete("/v1/connectors/slack/workspaces/T1").status_code == 200
    assert client.get("/v1/connectors/slack/workspaces").json()["data"] == []
    assert client.delete("/v1/connectors/slack/workspaces/T1").status_code == 404
