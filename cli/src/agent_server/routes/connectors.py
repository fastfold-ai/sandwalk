"""`/v1/connectors/slack/*` routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException, Query

from agent_server.app_deps import AppDeps
from agent_server.connectors.addressing import resolve_channel_input
from agent_server.connectors.manifest import (
    DEFAULT_APP_NAME,
    SETUP_STEPS,
    build_manifest_json,
)
from agent_server.models.connectors import (
    AddSlackSubscriptionRequest,
    AllowSlackUserRequest,
    ConnectorActionResponse,
    ConnectSlackManualRequest,
    SessionConnectorMute,
    SetConnectorMuteRequest,
    SetSlackWorkspaceEnabledRequest,
    SlackAllowedUserList,
    SlackConnectorStatus,
    SlackDirectory,
    SlackDirectoryChannel,
    SlackDirectoryPerson,
    SlackManifestResponse,
    SlackOneClickStart,
    SlackParkedMessageList,
    SlackSubscriptionList,
    SlackWorkspace,
    SlackWorkspaceList,
    StartSlackOneClickRequest,
)

CONNECTOR = "slack"


def register_connector_routes(app: FastAPI, deps: AppDeps) -> None:
    connectors = deps.connector_service
    store = deps.store

    @app.get("/v1/connectors/slack/status", response_model=SlackConnectorStatus)
    async def slack_status() -> SlackConnectorStatus:
        return connectors.status()

    @app.get("/v1/connectors/slack/manifest", response_model=SlackManifestResponse)
    async def slack_manifest(
        app_name: str = Query(default=DEFAULT_APP_NAME),
    ) -> SlackManifestResponse:
        return SlackManifestResponse(
            app_name=app_name,
            manifest=build_manifest_json(app_name),
            steps=list(SETUP_STEPS),
        )

    @app.get("/v1/connectors/slack/workspaces", response_model=SlackWorkspaceList)
    async def list_workspaces() -> SlackWorkspaceList:
        return SlackWorkspaceList(data=store.list_slack_workspaces())

    @app.post(
        "/v1/connectors/slack/connect/one-click",
        response_model=SlackOneClickStart,
    )
    async def start_one_click(
        payload: StartSlackOneClickRequest | None = None,
    ) -> SlackOneClickStart:
        """Hand back the Slack install URL for the user's browser."""
        try:
            url = await connectors.start_one_click(return_to=payload.return_to if payload else None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return SlackOneClickStart(auth_url=url)

    @app.post(
        "/v1/connectors/slack/connect/one-click/import",
        response_model=SlackWorkspaceList,
    )
    async def import_one_click(
        reauth_team_id: str | None = Query(default=None),
    ) -> SlackWorkspaceList:
        """Pick up installs finished in the browser.

        Polled by the UI after opening the install URL, since the desktop never
        sees the OAuth callback itself. ``reauth_team_id`` marks this as a
        reconnect for a team we already have a (possibly stale) token for, so
        that one gets overwritten instead of skipped.
        """
        try:
            return SlackWorkspaceList(
                data=await connectors.import_one_click_connections(reauth_team_id=reauth_team_id)
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/v1/connectors/slack/connect",
        response_model=SlackWorkspace,
        status_code=201,
    )
    async def connect_manual(payload: ConnectSlackManualRequest) -> SlackWorkspace:
        try:
            return await connectors.connect_socket_mode(
                bot_token=payload.bot_token, app_token=payload.app_token
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete(
        "/v1/connectors/slack/workspaces/{team_id}",
        response_model=ConnectorActionResponse,
    )
    async def disconnect_workspace(team_id: str) -> ConnectorActionResponse:
        removed = await connectors.disconnect_workspace(team_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Workspace not connected.")
        return ConnectorActionResponse()

    @app.patch(
        "/v1/connectors/slack/workspaces/{team_id}/enabled",
        response_model=SlackWorkspace,
    )
    async def set_workspace_enabled(
        team_id: str, payload: SetSlackWorkspaceEnabledRequest
    ) -> SlackWorkspace:
        """Pause/resume - keeps tokens and settings, unlike disconnect."""
        try:
            return await connectors.set_workspace_enabled(team_id, enabled=payload.enabled)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Workspace not connected.") from exc

    @app.get(
        "/v1/connectors/slack/workspaces/{team_id}/directory",
        response_model=SlackDirectory,
    )
    async def workspace_directory(
        team_id: str, refresh: bool = Query(default=False)
    ) -> SlackDirectory:
        try:
            people, channels = await connectors.directory(team_id, force=refresh)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Workspace not connected.") from exc
        return SlackDirectory(
            people=[
                SlackDirectoryPerson(
                    id=person.id,
                    name=person.name,
                    handle=person.handle,
                    avatar_url=person.avatar_url,
                )
                for person in people
            ],
            channels=[
                SlackDirectoryChannel(
                    id=channel.id, name=channel.name, is_private=channel.is_private
                )
                for channel in channels
            ],
        )

    # --- allowlist ------------------------------------------------------

    @app.get(
        "/v1/connectors/slack/workspaces/{team_id}/people",
        response_model=SlackAllowedUserList,
    )
    async def list_people(team_id: str) -> SlackAllowedUserList:
        _require_workspace(team_id)
        return SlackAllowedUserList(data=store.list_slack_allowed_users(team_id))

    @app.post(
        "/v1/connectors/slack/people",
        response_model=SlackAllowedUserList,
        status_code=201,
    )
    async def allow_person(payload: AllowSlackUserRequest) -> SlackAllowedUserList:
        _require_workspace(payload.team_id)
        await asyncio.to_thread(
            store.allow_slack_user,
            team_id=payload.team_id,
            slack_user_id=payload.slack_user_id,
            display_name=payload.display_name,
        )
        return SlackAllowedUserList(data=store.list_slack_allowed_users(payload.team_id))

    @app.delete(
        "/v1/connectors/slack/workspaces/{team_id}/people/{slack_user_id}",
        response_model=ConnectorActionResponse,
    )
    async def disallow_person(team_id: str, slack_user_id: str) -> ConnectorActionResponse:
        removed = store.disallow_slack_user(team_id=team_id, slack_user_id=slack_user_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Person not on the list.")
        return ConnectorActionResponse()

    # --- channel subscriptions -----------------------------------------

    @app.get("/v1/connectors/slack/subscriptions", response_model=SlackSubscriptionList)
    async def list_subscriptions(
        session_id: str | None = Query(default=None),
    ) -> SlackSubscriptionList:
        return SlackSubscriptionList(data=store.list_slack_subscriptions(session_id=session_id))

    @app.post(
        "/v1/connectors/slack/subscriptions",
        response_model=SlackSubscriptionList,
        status_code=201,
    )
    async def add_subscription(
        payload: AddSlackSubscriptionRequest,
    ) -> SlackSubscriptionList:
        if store.get_session(payload.session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        workspaces = store.list_slack_workspaces()
        default_team = workspaces[0].team_id if len(workspaces) == 1 else None
        try:
            channel = resolve_channel_input(payload.channel, default_team_id=default_team)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        store.add_slack_subscription(session_id=payload.session_id, channel=channel)
        return SlackSubscriptionList(
            data=store.list_slack_subscriptions(session_id=payload.session_id)
        )

    @app.delete(
        "/v1/connectors/slack/subscriptions",
        response_model=ConnectorActionResponse,
    )
    async def remove_subscription(
        session_id: str = Query(...), channel: str = Query(...)
    ) -> ConnectorActionResponse:
        removed = store.remove_slack_subscription(session_id=session_id, channel=channel)
        if not removed:
            raise HTTPException(status_code=404, detail="Subscription not found.")
        return ConnectorActionResponse()

    # --- parked (unauthorized) ------------------------------------------

    @app.get("/v1/connectors/slack/parked", response_model=SlackParkedMessageList)
    async def list_parked() -> SlackParkedMessageList:
        return SlackParkedMessageList(data=store.list_slack_parked_messages())

    @app.post(
        "/v1/connectors/slack/parked/{message_id}/allow",
        response_model=ConnectorActionResponse,
    )
    async def allow_parked(message_id: str) -> ConnectorActionResponse:
        """Allow the sender and deliver the message they were waiting on."""
        if not await connectors.allow_parked(message_id):
            raise HTTPException(status_code=404, detail="Message not found.")
        return ConnectorActionResponse()

    @app.delete(
        "/v1/connectors/slack/parked/{message_id}",
        response_model=ConnectorActionResponse,
    )
    async def dismiss_parked(message_id: str) -> ConnectorActionResponse:
        if not store.delete_slack_parked_message(message_id):
            raise HTTPException(status_code=404, detail="Message not found.")
        return ConnectorActionResponse()

    # --- per-session mute ------------------------------------------------

    @app.get(
        "/v1/sessions/{session_id}/connectors/slack",
        response_model=SessionConnectorMute,
    )
    async def get_session_mute(session_id: str) -> SessionConnectorMute:
        if store.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return SessionConnectorMute(
            session_id=session_id,
            connector=CONNECTOR,
            muted=store.is_session_connector_muted(session_id=session_id, connector=CONNECTOR),
        )

    @app.put(
        "/v1/sessions/{session_id}/connectors/slack",
        response_model=SessionConnectorMute,
    )
    async def set_session_mute(
        session_id: str, payload: SetConnectorMuteRequest
    ) -> SessionConnectorMute:
        if store.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        store.set_session_connector_mute(
            session_id=session_id, connector=CONNECTOR, muted=payload.muted
        )
        return SessionConnectorMute(session_id=session_id, connector=CONNECTOR, muted=payload.muted)

    def _require_workspace(team_id: str) -> None:
        if store.get_slack_workspace(team_id) is None:
            raise HTTPException(status_code=404, detail="Workspace not connected.")
