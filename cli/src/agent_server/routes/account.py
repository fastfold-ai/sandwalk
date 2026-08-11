"""`/v1/account/*` routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, Query

from _version import __version__
from agent_server.app_deps import AppDeps
from agent_server.models import AccountSummary


def register_account_routes(app: FastAPI, deps: AppDeps) -> None:
    account_service = deps.account_service

    @app.get("/v1/account", response_model=AccountSummary)
    async def get_account(check_updates: bool = Query(default=False)) -> AccountSummary:
        return await asyncio.to_thread(
            account_service.get,
            version=__version__,
            check_updates=check_updates,
        )

    @app.post("/v1/account/logout", response_model=AccountSummary)
    async def logout_account() -> AccountSummary:
        return await asyncio.to_thread(account_service.logout)
