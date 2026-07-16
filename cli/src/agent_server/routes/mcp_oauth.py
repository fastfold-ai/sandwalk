"""MCP OAuth browser-redirect callback route."""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, HTTPException, Response

from agent_server.app_deps import AppDeps


def register_mcp_oauth_routes(app: FastAPI, deps: AppDeps) -> None:
    mcp_service = deps.mcp_service

    @app.get("/v1/mcp-servers/oauth/callback")
    async def mcp_oauth_callback(
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
        error_description: str | None = None,
    ) -> Response:
        if error:
            detail = error_description or error
            html = f"""<!doctype html><html><body style="font-family:system-ui;padding:2rem">
              <h2>MCP OAuth failed</h2><p>{detail}</p>
              <p>You can close this window and return to FastFold.</p>
              <script>window.opener&&window.opener.postMessage({{type:'fastfold-mcp-oauth',ok:false,error:{json.dumps(detail)}}},'*');</script>
              </body></html>"""
            return Response(content=html, media_type="text/html")
        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing code or state")
        try:
            result = await asyncio.to_thread(
                mcp_service.complete_oauth,
                code=code,
                state=state,
            )
        except Exception as exc:  # noqa: BLE001
            html = f"""<!doctype html><html><body style="font-family:system-ui;padding:2rem">
              <h2>MCP OAuth failed</h2><p>{exc}</p>
              <script>window.opener&&window.opener.postMessage({{type:'fastfold-mcp-oauth',ok:false,error:{json.dumps(str(exc))}}},'*');</script>
              </body></html>"""
            return Response(content=html, media_type="text/html", status_code=400)

        payload = json.dumps(
            {
                "type": "fastfold-mcp-oauth",
                "ok": bool(result.get("ok")),
                "catalogId": result.get("catalogId"),
                "serverId": result.get("serverId"),
                "enabled": result.get("enabled"),
                "toolCount": result.get("toolCount"),
                "message": result.get("message"),
            }
        )
        html = f"""<!doctype html><html><body style="font-family:system-ui;padding:2rem">
          <h2>{"Connected" if result.get("ok") else "Connected with errors"}</h2>
          <p>{result.get("message") or ""}</p>
          <p>You can close this window and return to FastFold.</p>
          <script>window.opener&&window.opener.postMessage({payload},'*');setTimeout(()=>window.close(),800);</script>
          </body></html>"""
        return Response(content=html, media_type="text/html")
