"""Bounded transcript extracts for Capy (never dump a full chat)."""

from __future__ import annotations

from typing import Any

MAX_TURNS = 20
MAX_CHARS = 8000


def extract_session(store, session_id: str) -> dict[str, Any]:
    session = store.get_session(session_id)
    if session is None:
        return {"ok": False, "summary": "Session not found."}
    if str(getattr(session, "source", "") or "") in {"capy", "bench"}:
        return {
            "ok": False,
            "summary": "Capy cannot read its own transcript or bench cells.",
        }
    messages = store.list_messages(session_id)
    tools_used: list[str] = []
    try:
        for event in store.list_events(session_id):
            if event.type == "tool.started":
                name = (event.payload or {}).get("name")
                if name and str(name) not in tools_used:
                    tools_used.append(str(name))
    except Exception:  # noqa: BLE001
        pass
    recent = messages[-MAX_TURNS:]
    lines: list[str] = []
    for message in recent:
        role = message.role
        text = (message.content or "").strip()
        if not text:
            continue
        lines.append(f"{role}: {text}")
    excerpt = "\n".join(lines)
    truncated = len(messages) > MAX_TURNS or len(excerpt) > MAX_CHARS
    if len(excerpt) > MAX_CHARS:
        excerpt = excerpt[-MAX_CHARS:]
    return {
        "ok": True,
        "summary": f"Extracted {len(recent)} turns from {session.title}.",
        "sessionId": session.id,
        "title": session.title,
        "status": session.status,
        "excerpt": excerpt,
        "toolsUsed": tools_used[:40],
        "truncated": truncated,
        "messageCount": len(messages),
    }
