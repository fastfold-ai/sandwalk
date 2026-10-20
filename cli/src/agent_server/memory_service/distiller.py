"""Session Distiller: extract Memories, Wiki pages, and Graph claims from chats."""

from __future__ import annotations

import re
from typing import Any

from agent_server.memory_service.omnigraph_engine import GraphEngine
from agent_server.memory_service.store import (
    MemoryStore,
    load_memory_settings,
    normalize_scope,
)
from agent_server.memory_service.wiki import WikiManager
from agent_server.models.memory import DistillSessionResponse


def _is_local_llama_busy() -> bool:
    """Return True if local llama.cpp is currently mid-load so background review can defer."""
    try:
        from agent_server.llama_runtime import status as llama_status

        st = llama_status()
        phase = str(st.get("phase") or "idle")
        return phase in {"installing", "opening", "updating", "downloading"}
    except Exception:
        return False


def _extract_key_sentences(messages: list[Any], max_items: int = 4) -> list[str]:
    """Deterministic high-signal extraction from user and assistant messages."""
    candidates: list[str] = []
    markers = (
        "conclud",
        "decid",
        "assum",
        "prefer",
        "always ",
        "never ",
        "hypothes",
        "contradict",
        "support",
        "found that",
        "key takeaway",
        "summary:",
    )
    for msg in reversed(messages):
        text = str(getattr(msg, "content", "") or "").strip()
        if not text:
            continue
        for raw_line in text.splitlines():
            line = re.sub(r"^[-*#\d.)\s]+", "", raw_line).strip()
            if len(line) < 24 or len(line) > 260:
                continue
            lower = line.lower()
            if any(m in lower for m in markers):
                if line not in candidates:
                    candidates.append(line)
                    if len(candidates) >= max_items:
                        return candidates

    # Fallback: take first substantive assistant summary lines
    for msg in reversed(messages):
        if getattr(msg, "role", "") != "assistant":
            continue
        for raw_line in str(getattr(msg, "content", "") or "").splitlines():
            line = re.sub(r"^[-*#\d.)\s]+", "", raw_line).strip()
            if 30 <= len(line) <= 220 and line not in candidates:
                candidates.append(line)
                if len(candidates) >= max_items:
                    return candidates
    return candidates


def distill_session_to_memory(
    *,
    agent_store: Any,
    memory_store: MemoryStore,
    wiki_manager: WikiManager,
    graph_engine: GraphEngine,
    session_id: str,
    scope: str | None = None,
    include_wiki: bool = True,
    include_graph: bool = True,
    is_background: bool = False,
) -> DistillSessionResponse:
    session = agent_store.get_session(session_id) if agent_store else None
    if session is None:
        raise KeyError(f"Session not found: {session_id}")

    settings = load_memory_settings()
    if is_background and settings.distiller_defer_on_local_gpu and _is_local_llama_busy():
        return DistillSessionResponse(
            ok=True,
            session_id=session_id,
            scope=normalize_scope(scope),
            summary="Deferred background distillation while local GPU is busy.",
        )

    resolved_scope = normalize_scope(
        scope
        or (f"project:{session.project_id}" if getattr(session, "project_id", None) else None)
        or (
            f"specialist:{session.specialist_id}"
            if getattr(session, "specialist_id", None)
            else "global"
        )
    )

    messages = agent_store.list_messages(session_id)
    if not messages:
        return DistillSessionResponse(
            ok=True,
            session_id=session_id,
            scope=resolved_scope,
            summary="Session has no messages to distill.",
        )

    highlights = _extract_key_sentences(messages, max_items=4)
    memories_added = 0
    staged = False
    for sentence in highlights[:2]:
        try:
            entry = memory_store.add_entry(
                scope=resolved_scope,
                target="memory",
                layer="L1",
                content=f"[{session.title}] {sentence}",
                tags=["distilled", f"session:{session_id[:8]}"],
                source_session_id=session_id,
                bypass_approval=not settings.write_approval,
            )
            memories_added += 1
            if entry.status == "pending":
                staged = True
        except ValueError:
            continue

    wiki_slug: str | None = None
    if include_wiki and settings.wiki_enabled and highlights:
        slug = f"session-{session_id[:8]}-{re.sub(r'[^a-z0-9]+', '-', session.title.lower()).strip('-')[:32]}"
        bullet_lines = "\n".join(f"- {item}" for item in highlights)
        wiki_body = (
            f"# {session.title}\n\n"
            f"Distilled from session `{session_id}`.\n\n"
            f"## Key Findings & Decisions\n\n{bullet_lines}\n"
        )
        page = wiki_manager.write_page(
            slug=slug,
            title=session.title,
            content=wiki_body,
            scope=resolved_scope,
            summary=highlights[0][:140],
            tags=["session-brief"],
        )
        wiki_slug = page.slug

    nodes_added = 0
    claims_added = 0
    if include_graph and settings.graph_enabled and highlights:
        branch = (
            f"review/{session_id[:8]}"
            if settings.graph_branch_on_write
            else "main"
        )
        cookbook_id = memory_store.get_scope_cookbook(resolved_scope)
        primary_type = "Claim"
        if cookbook_id == "industry-intel":
            primary_type = "Signal"
        elif cookbook_id == "second-brain":
            primary_type = "Note"

        session_node = graph_engine.upsert_node(
            scope=resolved_scope,
            branch=branch,
            node_type=primary_type,
            slug=f"sess-{session_id[:8]}",
            name=session.title,
            summary=highlights[0],
            source_ref=f"session:{session_id}",
        )
        nodes_added += 1

        for idx, sentence in enumerate(highlights[1:], start=1):
            polarity = (
                "contradict"
                if any(w in sentence.lower() for w in ("contradict", "however", "failed", "rebound"))
                else "support"
            )
            pred = "Contradicts" if polarity == "contradict" else "Supports"
            graph_engine.record_claim(
                scope=resolved_scope,
                branch=branch,
                subject_id=session_node.id,
                predicate=pred,
                object_id=f"{primary_type}:finding-{session_id[:8]}-{idx}",
                object_name=sentence[:90],
                polarity=polarity,
                summary=sentence,
                source_ref=f"session:{session_id}",
            )
            claims_added += 1

    return DistillSessionResponse(
        ok=True,
        session_id=session_id,
        scope=resolved_scope,
        memories_added=memories_added,
        wiki_slug=wiki_slug,
        nodes_added=nodes_added,
        claims_added=claims_added,
        staged_for_approval=staged,
        summary=(
            f"Distilled session '{session.title}' into {memories_added} memory note(s)"
            + (f", wiki page [[{wiki_slug}]]" if wiki_slug else "")
            + (f", and {claims_added} graph claim(s)." if claims_added else ".")
        ),
    )
