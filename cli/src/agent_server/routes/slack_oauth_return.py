"""Where the browser lands after Slack's one-click OAuth finishes.

FastFold Cloud does the actual token exchange (Slack requires a public HTTPS
redirect_uri, so that leg can't be local); this route is just the last hop -
FastFold Cloud's callback redirects the browser here with ``?slack=...`` once
it's done, so the user sees a page that says "sandwalk", not a generic cloud
dashboard loading screen. The desktop itself learns about the new workspace by
polling, same as always - this page has nothing to hand off.
"""

from __future__ import annotations

from fastapi import FastAPI, Response

from agent_server.app_deps import AppDeps
from agent_server.routes.oauth_return_page import connector_icon_data_uri, render_oauth_return_page


def register_slack_oauth_return_routes(app: FastAPI, deps: AppDeps) -> None:
    @app.get("/oauth/callback")
    async def slack_oauth_return(slack: str | None = None, reason: str | None = None) -> Response:
        if slack == "connected":
            html = render_oauth_return_page(
                ok=True,
                title="Slack connected",
                detail="You can close this tab and return to Sandwalk — it's already picking up the new workspace.",
                tag_label="Slack workspace",
                tag_icon_data_uri=connector_icon_data_uri("slack.png"),
            )
            return Response(content=html, media_type="text/html")

        html = render_oauth_return_page(
            ok=False,
            title="Could not connect Slack",
            detail=reason or "Something went wrong. Close this tab and try again from Sandwalk.",
            tag_label="Slack",
        )
        return Response(content=html, media_type="text/html", status_code=400)
