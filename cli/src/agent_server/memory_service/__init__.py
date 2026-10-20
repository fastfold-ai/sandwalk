"""Unified Memory, Living Wiki, Cookbook Ontology, and Omnigraph service."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_server.memory_service.cookbooks import (
    COOKBOOK_DEFINITIONS,
    get_cookbook_seed,
    get_cookbook_summary,
    list_cookbook_summaries,
)
from agent_server.memory_service.distiller import distill_session_to_memory
from agent_server.memory_service.omnigraph_engine import (
    GraphEngine,
    find_omnigraph_binary,
    get_omnigraph_status,
    install_omnigraph_engine,
    resolve_omnigraph_env,
)
from agent_server.memory_service.store import (
    MemoryStore,
    load_memory_settings,
    memory_root,
    normalize_scope,
    scrub_and_validate_text,
    search_past_sessions,
    update_memory_settings,
)
from agent_server.memory_service.wiki import WikiManager
from agent_server.models.memory import (
    CookbookList,
    CookbookSummary,
    CreateGraphClaimRequest,
    CreateMemoryEntryRequest,
    DistillSessionResponse,
    GraphBranch,
    GraphBranchActionRequest,
    GraphEdge,
    GraphNode,
    GraphSnapshot,
    MemoryEntry,
    MemoryEntryList,
    MemoryOverview,
    MemorySettings,
    OmnigraphEngineStatus,
    PendingMemoryWrite,
    PendingMemoryWriteList,
    UpdateMemoryEntryRequest,
    UpdateMemorySettingsRequest,
    UpsertGraphNodeRequest,
    UpsertWikiPageRequest,
    WikiPageDetail,
    WikiPageList,
)


class MemoryService:
    """High-level facade wired into AppDeps, Agent Tools, Capy, and FastAPI routes."""

    def __init__(self, agent_store: Any | None = None, db_path: Path | None = None) -> None:
        self.agent_store = agent_store
        self.store = MemoryStore(db_path=db_path)
        self.wiki = WikiManager()
        self.graph = GraphEngine(self.store)

    def _project_folder(self, scope: str) -> Path | None:
        norm = normalize_scope(scope)
        if not norm.startswith("project:") or self.agent_store is None:
            return None
        pid = norm.split(":", 1)[1]
        try:
            proj = self.agent_store.get_project(pid)
            if proj and getattr(proj, "folder_path", None):
                path = Path(str(proj.folder_path)).expanduser()
                if path.is_dir():
                    return path
        except Exception:
            return None
        return None

    def get_settings(self) -> MemorySettings:
        return load_memory_settings()

    def update_settings(self, payload: UpdateMemorySettingsRequest) -> MemorySettings:
        return update_memory_settings(payload)

    def get_overview(self, scope: str = "global") -> MemoryOverview:
        if self.agent_store is not None and self.store.db_path == (memory_root() / "memory.db"):
            try:
                self.seed_showcase(force=False)
            except Exception:
                pass
        norm = normalize_scope(scope)
        settings = self.get_settings()
        entries = self.store.list_entries(scope=norm, include_user=True)
        scope_only = [e for e in entries.data if e.scope == norm]
        user_only = [e for e in entries.data if e.scope == "user"]
        pending = self.store.list_pending_writes(scope=norm if norm != "global" else "all")
        wiki_pages = self.wiki.list_pages(norm, project_folder=self._project_folder(norm)).data
        snap = self.graph.get_snapshot(norm)
        omni = get_omnigraph_status(self.agent_store, scope=norm)

        return MemoryOverview(
            scope=norm,
            active_cookbook_id=snap.active_cookbook.id,
            memory_count=len(scope_only),
            user_memory_count=len(user_only),
            pending_count=len(pending),
            wiki_page_count=len(wiki_pages),
            graph_node_count=len(snap.nodes),
            graph_edge_count=len(snap.edges),
            contradiction_count=snap.contradiction_count,
            char_used=entries.char_used,
            char_limit=entries.char_limit,
            user_char_used=entries.user_char_used,
            user_char_limit=entries.user_char_limit,
            omnigraph=omni,
            settings=settings,
        )

    def list_entries(self, scope: str = "global", *, include_user: bool = True) -> MemoryEntryList:
        return self.store.list_entries(scope=scope, include_user=include_user)

    def create_entry(
        self, payload: CreateMemoryEntryRequest, *, bypass_approval: bool = True
    ) -> MemoryEntry:
        return self.store.add_entry(
            scope=payload.scope,
            target=payload.target,
            layer=payload.layer,
            content=payload.content,
            tags=payload.tags,
            pinned=payload.pinned,
            source_session_id=payload.source_session_id,
            bypass_approval=bypass_approval,
        )

    def update_entry(self, entry_id: str, payload: UpdateMemoryEntryRequest) -> MemoryEntry | None:
        return self.store.update_entry(
            entry_id,
            content=payload.content,
            tags=payload.tags,
            pinned=payload.pinned,
        )

    def delete_entry(self, entry_id: str) -> bool:
        return self.store.delete_entry(entry_id)

    def list_pending(self, scope: str | None = None) -> PendingMemoryWriteList:
        return PendingMemoryWriteList(data=self.store.list_pending_writes(scope=scope))

    def approve_pending(self, pending_id: str) -> dict[str, Any]:
        items = self.store.list_pending_writes()
        target = next((item for item in items if item.id == pending_id), None)
        if target is None:
            raise KeyError(pending_id)
        payload = target.payload
        if target.kind == "memory":
            entry = self.store.add_entry(
                scope=str(payload.get("scope") or target.scope),
                target=str(payload.get("target") or "memory"),
                layer=str(payload.get("layer") or "L1"),
                content=str(payload.get("content") or target.summary),
                tags=list(payload.get("tags") or []),
                pinned=bool(payload.get("pinned", False)),
                source_session_id=target.source_session_id,
                bypass_approval=True,
            )
            self.store.reject_pending_write(pending_id)
            return {"ok": True, "approved_id": pending_id, "entry_id": entry.id}
        self.store.reject_pending_write(pending_id)
        return {"ok": True, "approved_id": pending_id}

    def reject_pending(self, pending_id: str) -> bool:
        return self.store.reject_pending_write(pending_id)

    def list_wiki(self, scope: str = "global") -> WikiPageList:
        return self.wiki.list_pages(scope, project_folder=self._project_folder(scope))

    def get_wiki_page(self, slug: str, scope: str = "global") -> WikiPageDetail | None:
        return self.wiki.get_page(slug, scope, project_folder=self._project_folder(scope))

    def write_wiki_page(self, slug: str, payload: UpsertWikiPageRequest) -> WikiPageDetail:
        return self.wiki.write_page(
            slug=slug,
            title=payload.title,
            content=payload.content,
            scope=payload.scope,
            summary=payload.summary,
            tags=payload.tags,
            project_folder=self._project_folder(payload.scope),
        )

    def delete_wiki_page(self, slug: str, scope: str = "global") -> bool:
        return self.wiki.delete_page(slug, scope, project_folder=self._project_folder(scope))

    def list_cookbooks(self, scope: str = "global") -> CookbookList:
        active = self.store.get_scope_cookbook(scope)
        return CookbookList(data=list_cookbook_summaries(), active_cookbook_id=active)

    def select_cookbook(
        self,
        *,
        scope: str = "global",
        cookbook_id: str,
        load_demo_seed: bool = False,
    ) -> GraphSnapshot:
        if cookbook_id not in COOKBOOK_DEFINITIONS:
            raise ValueError(f"Unknown cookbook_id: {cookbook_id}")
        self.store.set_scope_cookbook(scope, cookbook_id)
        if load_demo_seed:
            return self.graph.load_cookbook_seed(scope, cookbook_id)
        return self.graph.get_snapshot(scope)

    def get_graph(
        self,
        scope: str = "global",
        *,
        branch: str = "main",
        query_name: str | None = None,
    ) -> GraphSnapshot:
        return self.graph.get_snapshot(scope, branch=branch, query_name=query_name)

    def upsert_graph_node(self, payload: UpsertGraphNodeRequest) -> GraphNode:
        return self.graph.upsert_node(
            scope=payload.scope,
            branch=payload.branch,
            node_type=payload.node_type,
            slug=payload.slug,
            name=payload.name,
            summary=payload.summary,
            tags=payload.tags,
            properties=payload.properties,
            source_ref=payload.source_ref,
        )

    def delete_graph_node(self, node_id: str, scope: str = "global", branch: str = "main") -> bool:
        return self.graph.delete_node(scope=scope, node_id=node_id, branch=branch)

    def record_graph_claim(self, payload: CreateGraphClaimRequest) -> GraphEdge:
        return self.graph.record_claim(
            scope=payload.scope,
            branch=payload.branch,
            subject_id=payload.subject_id,
            subject_type=payload.subject_type,
            subject_name=payload.subject_name,
            predicate=payload.predicate,
            object_id=payload.object_id,
            object_type=payload.object_type,
            object_name=payload.object_name,
            polarity=payload.polarity,
            score=payload.score,
            summary=payload.summary,
            source_ref=payload.source_ref,
        )

    def manage_graph_branch(self, payload: GraphBranchActionRequest) -> list[GraphBranch]:
        return self.graph.manage_branch(
            scope=payload.scope,
            action=payload.action,
            name=payload.name,
            target_branch=payload.target_branch,
        )

    def distill_session(
        self,
        session_id: str,
        *,
        scope: str | None = None,
        include_wiki: bool = True,
        include_graph: bool = True,
        is_background: bool = False,
    ) -> DistillSessionResponse:
        return distill_session_to_memory(
            agent_store=self.agent_store,
            memory_store=self.store,
            wiki_manager=self.wiki,
            graph_engine=self.graph,
            session_id=session_id,
            scope=scope,
            include_wiki=include_wiki,
            include_graph=include_graph,
            is_background=is_background,
        )

    def omnigraph_status(self, scope: str = "global") -> OmnigraphEngineStatus:
        return get_omnigraph_status(self.agent_store, scope=scope)

    def omnigraph_install(self) -> OmnigraphEngineStatus:
        return install_omnigraph_engine(self.agent_store)

    def omnigraph_sync(self, scope: str = "global", branch: str = "main") -> dict[str, Any]:
        return self.graph.sync_omnigraph_bundle(scope, branch=branch)

    def seed_showcase(self, *, force: bool = False) -> dict[str, Any]:
        from agent_server.memory_service.showcase import seed_end_to_end_showcase

        return seed_end_to_end_showcase(self, self.agent_store, force=force)

    def build_prompt_snapshot(
        self,
        *,
        project_id: str | None = None,
        specialist_id: str | None = None,
        specialist_priors: str | None = None,
        specialist_name: str | None = None,
    ) -> str:
        """Assemble the bounded, frozen session-start memory & ontology snapshot."""
        settings = self.get_settings()
        if not settings.enabled:
            return ""

        sections: list[str] = []

        if settings.user_profile_enabled:
            user_list = self.store.list_entries(scope="user", include_user=False)
            if user_list.data:
                pct = int(round((user_list.char_used / max(1, user_list.char_limit)) * 100))
                body = "\n§\n".join(e.content for e in user_list.data)
                sections.append(
                    f"### USER PROFILE [{pct}% — {user_list.char_used}/{user_list.char_limit} chars]\n{body}"
                )

        global_list = self.store.list_entries(scope="global", include_user=False)
        if global_list.data:
            pct = int(round((global_list.char_used / max(1, global_list.char_limit)) * 100))
            body = "\n§\n".join(e.content for e in global_list.data)
            sections.append(
                f"### GLOBAL MEMORY [{pct}% — {global_list.char_used}/{global_list.char_limit} chars]\n{body}"
            )

        active_scope = f"project:{project_id}" if project_id else "global"
        if project_id:
            proj_list = self.store.list_entries(scope=active_scope, include_user=False)
            if proj_list.data:
                pct = int(round((proj_list.char_used / max(1, proj_list.char_limit)) * 100))
                body = "\n§\n".join(e.content for e in proj_list.data)
                sections.append(
                    f"### PROJECT MEMORY [{pct}% — {proj_list.char_used}/{proj_list.char_limit} chars]\n{body}"
                )

        if specialist_id or specialist_priors:
            spec_lines: list[str] = []
            if specialist_priors and specialist_priors.strip():
                spec_lines.append(f"**Cognitive Priors & Biases**: {specialist_priors.strip()}")
            if specialist_id:
                spec_list = self.store.list_entries(
                    scope=f"specialist:{specialist_id}", include_user=False
                )
                for item in spec_list.data:
                    spec_lines.append(f"- {item.content}")
            if spec_lines:
                label = specialist_name or specialist_id or "Specialist"
                sections.append(
                    f"### PERSONA BRAIN ({label})\n" + "\n".join(spec_lines)
                )

        if settings.wiki_enabled:
            toc = self.wiki.build_toc_block(
                active_scope, max_chars=settings.wiki_toc_max_chars
            )
            if toc:
                sections.append(toc)

        if settings.graph_enabled:
            snap = self.graph.get_snapshot(active_scope)
            cb = snap.active_cookbook
            nt_names = ", ".join(nt.name for nt in cb.node_types)
            q_names = ", ".join(q.name for q in cb.stored_queries)
            sections.append(
                f"### ACTIVE KNOWLEDGE GRAPH ({cb.number} {cb.name})\n"
                f"- Ontology Node Types: {nt_names}\n"
                f"- Stored Queries (`graph.cookbook_query`): {q_names}\n"
                f"- Graph State: {len(snap.nodes)} nodes, {len(snap.edges)} edges, "
                f"{snap.contradiction_count} contested/contradicting claims."
            )

        if not sections:
            return ""
        return "\n\n".join(sections)


__all__ = [
    "COOKBOOK_DEFINITIONS",
    "GraphEngine",
    "MemoryService",
    "MemoryStore",
    "WikiManager",
    "distill_session_to_memory",
    "find_omnigraph_binary",
    "get_cookbook_seed",
    "get_cookbook_summary",
    "get_omnigraph_status",
    "install_omnigraph_engine",
    "list_cookbook_summaries",
    "load_memory_settings",
    "memory_root",
    "normalize_scope",
    "resolve_omnigraph_env",
    "scrub_and_validate_text",
    "search_past_sessions",
    "update_memory_settings",
]
