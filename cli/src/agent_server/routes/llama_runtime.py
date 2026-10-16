"""Routes that install, open, and read the external Llama macOS app."""

from __future__ import annotations

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent_server.app_deps import AppDeps
from agent_server.llama_runtime import (
    catalog,
    ensure,
    install_model,
    load_model,
    memory_tiers,
    publish_profile,
    set_context,
    status,
    unload_model,
    update_engine,
)


class _ModelBody(BaseModel):
    model: str


class _ContextBody(BaseModel):
    model: str
    context: int


class _InstallBody(BaseModel):
    repo: str
    quant: str | None = None


def register_llama_runtime_routes(app: FastAPI, deps: AppDeps) -> None:
    del deps

    @app.get("/v1/local-runtimes/llama")
    async def llama_runtime_status() -> dict:
        return status()

    @app.post("/v1/local-runtimes/llama/ensure")
    async def llama_runtime_ensure() -> dict:
        return ensure()

    @app.get("/v1/local-runtimes/llama/catalog")
    async def llama_runtime_catalog(q: str = "") -> dict:
        publish_profile()
        return catalog(q)

    @app.get("/v1/local-runtimes/llama/memory")
    async def llama_runtime_memory(model: str) -> dict:
        import asyncio

        return await asyncio.to_thread(memory_tiers, model)

    @app.post("/v1/local-runtimes/llama/update")
    async def llama_runtime_update() -> dict:
        try:
            return update_engine()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/local-runtimes/llama/load")
    async def llama_runtime_load(body: _ModelBody) -> dict:
        try:
            return load_model(body.model)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/local-runtimes/llama/unload")
    async def llama_runtime_unload(body: _ModelBody) -> dict:
        try:
            return unload_model(body.model)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/v1/local-runtimes/llama/context")
    async def llama_runtime_context(body: _ContextBody) -> dict:
        try:
            return set_context(body.model, body.context)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/local-runtimes/llama/install")
    async def llama_runtime_install(body: _InstallBody) -> dict:
        try:
            return install_model(body.repo, body.quant)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
