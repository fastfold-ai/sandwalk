"""Session message list, feedback, and send-message routes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException

from agent_server.app_deps import AppDeps
from agent_server.models import (
    MessageFeedbackRequest,
    MessageFeedbackResponse,
    MessageList,
    SendMessageRequest,
    StartRunResponse,
)
from agent_server.service import SessionBusyError


def register_message_routes(app: FastAPI, deps: AppDeps) -> None:
    store = deps.store
    service = deps.service

    @app.get("/v1/sessions/{session_id}/messages", response_model=MessageList)
    async def list_messages(session_id: str) -> MessageList:
        if await asyncio.to_thread(store.get_session, session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return MessageList(
            data=await asyncio.to_thread(store.list_messages, session_id),
            feedback=await asyncio.to_thread(store.get_session_feedback, session_id),
        )

    @app.post(
        "/v1/sessions/{session_id}/messages/{message_id}/feedback",
        response_model=MessageFeedbackResponse,
    )
    async def update_message_feedback(
        session_id: str,
        message_id: str,
        payload: MessageFeedbackRequest,
    ) -> MessageFeedbackResponse:
        if await asyncio.to_thread(store.get_session, session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        saved = await asyncio.to_thread(
            store.set_message_feedback,
            message_id,
            payload.reaction,
        )
        if not saved:
            raise HTTPException(status_code=404, detail="Message not found.")
        return MessageFeedbackResponse(
            message_id=message_id,
            reaction=payload.reaction,
        )

    @app.post(
        "/v1/sessions/{session_id}/messages",
        response_model=StartRunResponse,
        status_code=202,
    )
    async def send_message(
        session_id: str,
        payload: SendMessageRequest,
    ) -> StartRunResponse:
        try:
            return service.submit_message(session_id=session_id, content=payload.content)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found.") from exc
        except SessionBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
