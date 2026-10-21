"""Agent tools for Sandwalk Memory, Living Wiki, Cookbook Queries, and Omnigraph."""

from __future__ import annotations

from typing import Any

from tools import registry


def _service() -> Any:
    from agent_server.memory_service import MemoryService
    from agent_server.store import AgentStore

    try:
        store = AgentStore()
    except Exception:
        store = None
    return MemoryService(agent_store=store)


@registry.register(
    name="memory.mutate",
    description="Add, patch, or remove curated entries in USER.md, MEMORY.md, or Specialist memory.",
    category="memory",
    parameters={
        "action": "Operation: 'add', 'patch', or 'remove'",
        "target": "Store target: 'memory' (default), 'user', 'project', or 'specialist'",
        "content": "Entry text to add or replacement span for 'patch'",
        "old_text": "Unique substring span to match when action is 'patch' or 'remove'",
        "scope": "Optional scope ('global', 'project:<id>', or 'specialist:<id>')",
        "tags": "Optional comma-separated tags",
    },
    usage_guide=(
        "Use to persist high-signal user preferences (target='user'), durable project/environment "
        "facts (target='memory' or 'project'), or specialist lessons. Prefer 'patch' with a "
        "unique old_text span to update existing entries."
    ),
)
def memory_mutate(
    action: str = "add",
    target: str = "memory",
    content: str = "",
    old_text: str = "",
    scope: str = "global",
    tags: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    svc = _service()
    tag_list = [t.strip() for t in str(tags or "").split(",") if t.strip()]
    try:
        res = svc.store.mutate_by_substring(
            scope=scope,
            target=target,
            action=action,
            content=content,
            old_text=old_text,
            tags=tag_list,
            bypass_approval=False,
        )
        return {
            "summary": f"Memory {action} on {target} ({scope}) succeeded.",
            **res,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "summary": f"Memory {action} failed: {exc}"}


@registry.register(
    name="memory.session_search",
    description="Full-text search across past Sandwalk chat sessions and transcripts.",
    category="memory",
    parameters={
        "query": "Keyword or phrase to search across past conversations",
        "project_id": "Optional project ID filter",
        "limit": "Maximum sessions to return (default 10)",
    },
    usage_guide="Use when the user asks about prior conversations, earlier runs, or past decisions.",
)
def memory_session_search(
    query: str,
    project_id: str = "",
    limit: int = 10,
    **kwargs: Any,
) -> dict[str, Any]:
    from agent_server.memory_service.store import search_past_sessions

    svc = _service()
    matches = search_past_sessions(
        svc.agent_store,
        query,
        project_id=project_id.strip() or None,
        limit=limit,
    )
    return {
        "summary": f"Found {len(matches)} past session(s) matching '{query}'.",
        "count": len(matches),
        "matches": matches,
    }


@registry.register(
    name="memory.wiki_list",
    description="List Living Markdown Wiki pages and [[wikilinks]] for a scope.",
    category="memory",
    parameters={
        "scope": "Scope: 'global', 'project:<id>', or 'specialist:<id>' (default 'global')",
    },
    usage_guide="Use to inspect available Wiki pages and their summaries before reading or updating.",
)
def wiki_list(scope: str = "global", **kwargs: Any) -> dict[str, Any]:
    svc = _service()
    listed = svc.list_wiki(scope)
    return {
        "summary": f"Listed {len(listed.data)} wiki page(s) in {listed.scope}.",
        "scope": listed.scope,
        "pages": [p.model_dump(mode="json", by_alias=True) for p in listed.data],
    }


@registry.register(
    name="memory.wiki_read",
    description="Read the full Markdown content and backlinks of a Living Wiki page.",
    category="memory",
    parameters={
        "slug": "Wiki page slug (e.g. 'kras-g12d-dossier')",
        "scope": "Scope: 'global', 'project:<id>', or 'specialist:<id>' (default 'global')",
    },
    usage_guide="Use when a page in the Living Wiki Index is relevant to the current task.",
)
def wiki_read(slug: str, scope: str = "global", **kwargs: Any) -> dict[str, Any]:
    svc = _service()
    page = svc.get_wiki_page(slug, scope=scope)
    if page is None:
        return {"ok": False, "error": "not_found", "summary": f"Wiki page '{slug}' not found in {scope}."}
    return {
        "ok": True,
        "summary": f"Loaded wiki page [[{page.slug}]] ({page.title}).",
        "page": page.model_dump(mode="json", by_alias=True),
    }


@registry.register(
    name="memory.wiki_write",
    description="Create or update a Living Markdown Wiki page with [[wikilinks]].",
    category="memory",
    parameters={
        "slug": "Page slug (e.g. 'target-validation-summary')",
        "title": "Human-readable page title",
        "content": "Markdown body (use [[other-slug]] to link related pages)",
        "scope": "Scope: 'global', 'project:<id>', or 'specialist:<id>' (default 'global')",
        "tags": "Optional comma-separated tags",
    },
    usage_guide="Use to synthesize durable domain briefs, protocols, and target dossiers into the Living Wiki.",
)
def wiki_write(
    slug: str,
    title: str,
    content: str,
    scope: str = "global",
    tags: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    from agent_server.models.memory import UpsertWikiPageRequest

    svc = _service()
    tag_list = [t.strip() for t in str(tags or "").split(",") if t.strip()]
    page = svc.write_wiki_page(
        slug,
        UpsertWikiPageRequest(scope=scope, title=title, content=content, tags=tag_list),
    )
    return {
        "ok": True,
        "summary": f"Saved wiki page [[{page.slug}]] in {page.scope}.",
        "page": page.model_dump(mode="json", by_alias=True),
    }


@registry.register(
    name="memory.graph_cookbook_query",
    description="Run a named Stored Query from the active Omnigraph Cookbook Mode.",
    category="memory",
    parameters={
        "query_name": "Stored query name (e.g. 'contested_claims', 'signals_contradicting_assumptions', 'decisions_at_risk')",
        "scope": "Scope: 'global', 'project:<id>', or 'specialist:<id>' (default 'global')",
        "branch": "Graph branch (default 'main')",
    },
    usage_guide="Use to retrieve high-precision subgraphs, contested claims, or assumption risks.",
)
def graph_cookbook_query(
    query_name: str = "contested_claims",
    scope: str = "global",
    branch: str = "main",
    **kwargs: Any,
) -> dict[str, Any]:
    svc = _service()
    snap = svc.get_graph(scope, branch=branch, query_name=query_name)
    matched = set(snap.matched_node_ids)
    nodes = [n.model_dump(mode="json", by_alias=True) for n in snap.nodes if n.id in matched]
    edges = [
        e.model_dump(mode="json", by_alias=True)
        for e in snap.edges
        if e.source_id in matched or e.target_id in matched
    ]
    return {
        "ok": True,
        "summary": (
            f"Cookbook query '{query_name}' on {snap.active_cookbook.name} ({snap.scope}@{branch}) "
            f"matched {len(nodes)} node(s) and {len(edges)} edge(s)."
        ),
        "cookbook": snap.active_cookbook.id,
        "nodes": nodes,
        "edges": edges,
    }


@registry.register(
    name="memory.graph_upsert_node",
    description="Add or update a typed node in the active Cookbook Ontology.",
    category="memory",
    parameters={
        "node_type": "Ontology node type (e.g. 'Entity', 'Compound', 'Assumption', 'Signal', 'Decision', 'Hypothesis')",
        "name": "Display name or statement",
        "slug": "Optional stable slug identifier",
        "summary": "Concise description or context",
        "scope": "Scope: 'global', 'project:<id>', or 'specialist:<id>' (default 'global')",
        "branch": "Graph branch (default 'main')",
        "source_ref": "Optional citation (PMID, DOI, NCT ID, file, or session ID)",
    },
    usage_guide="Use to register entities, assumptions, signals, or decisions in the Knowledge Graph.",
)
def graph_upsert_node(
    node_type: str,
    name: str,
    slug: str = "",
    summary: str = "",
    scope: str = "global",
    branch: str = "main",
    source_ref: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    from agent_server.models.memory import UpsertGraphNodeRequest

    svc = _service()
    node = svc.upsert_graph_node(
        UpsertGraphNodeRequest(
            scope=scope,
            branch=branch,
            node_type=node_type,
            slug=slug.strip() or None,
            name=name,
            summary=summary,
            source_ref=source_ref.strip() or None,
        )
    )
    return {
        "ok": True,
        "summary": f"Upserted graph node {node.id} ({node.name}) on {scope}@{branch}.",
        "node": node.model_dump(mode="json", by_alias=True),
    }


@registry.register(
    name="memory.graph_record_claim",
    description="Record a directed relationship or evidence claim (Supports / Contradicts) in the Knowledge Graph.",
    category="memory",
    parameters={
        "subject_id": "Source node ID or slug (e.g. 'AssayResult:rtk-rebound-72h' or 'Signal:trial-readout')",
        "predicate": "Edge predicate (e.g. 'Supports', 'Contradicts', 'Targets', 'ContradictsAssumption')",
        "object_id": "Target node ID or slug (e.g. 'Hypothesis:mono-durable' or 'Assumption:oral-tolerability')",
        "polarity": "'support', 'contradict', or 'neutral'",
        "summary": "Evidence summary or quote",
        "source_ref": "Citation / provenance (PMID, DOI, NCT, session ID)",
        "scope": "Scope: 'global', 'project:<id>', or 'specialist:<id>' (default 'global')",
        "branch": "Graph branch (default 'main')",
    },
    usage_guide=(
        "Use to connect evidence, signals, and entities to hypotheses or assumptions. "
        "Preserve conflicting findings with polarity='contradict'."
    ),
)
def graph_record_claim(
    subject_id: str,
    predicate: str,
    object_id: str,
    polarity: str = "support",
    summary: str = "",
    source_ref: str = "",
    scope: str = "global",
    branch: str = "main",
    **kwargs: Any,
) -> dict[str, Any]:
    from agent_server.models.memory import CreateGraphClaimRequest

    svc = _service()
    edge = svc.record_graph_claim(
        CreateGraphClaimRequest(
            scope=scope,
            branch=branch,
            subject_id=subject_id,
            predicate=predicate,
            object_id=object_id,
            polarity=polarity,  # type: ignore[arg-type]
            summary=summary,
            source_ref=source_ref.strip() or None,
        )
    )
    return {
        "ok": True,
        "summary": f"Recorded graph edge {edge.source_id} -[{edge.predicate} ({edge.polarity})]-> {edge.target_id}.",
        "edge": edge.model_dump(mode="json", by_alias=True),
    }


@registry.register(
    name="memory.graph_branch",
    description="List, create, merge, or delete Git-style branches on the Knowledge Graph.",
    category="memory",
    parameters={
        "action": "'list', 'create', 'merge', or 'delete'",
        "name": "Branch name (e.g. 'review/hypothesis-1')",
        "scope": "Scope: 'global', 'project:<id>', or 'specialist:<id>' (default 'global')",
        "target_branch": "Target branch for create/merge (default 'main')",
    },
    usage_guide="Use to isolate speculative hypothesis exploration on a branch before merging into main.",
)
def graph_branch(
    action: str = "list",
    name: str = "",
    scope: str = "global",
    target_branch: str = "main",
    **kwargs: Any,
) -> dict[str, Any]:
    from agent_server.models.memory import GraphBranchActionRequest

    svc = _service()
    act = action.strip().lower()
    if act == "list":
        branches = svc.graph.list_branches(scope)
        return {
            "ok": True,
            "summary": f"Found {len(branches)} branch(es) in {scope}.",
            "branches": [b.model_dump(mode="json", by_alias=True) for b in branches],
        }
    branches = svc.manage_graph_branch(
        GraphBranchActionRequest(
            scope=scope,
            action=act,  # type: ignore[arg-type]
            name=name,
            target_branch=target_branch,
        )
    )
    return {
        "ok": True,
        "summary": f"Branch action '{act}' on '{name}' completed.",
        "branches": [b.model_dump(mode="json", by_alias=True) for b in branches],
    }


@registry.register(
    name="memory.create_skill",
    description=(
        "Crystallize curated Memories, Living Wiki pages, and Omnigraph Cookbook ontologies "
        "into an installed Sandwalk Skill (~/.sandwalk/skills/<slug>/SKILL.md)."
    ),
    category="memory",
    parameters={
        "name": "Human-readable title or slug for the new skill (e.g. 'Oral GLP-1R Discovery')",
        "slug": "Optional kebab-case skill identifier (e.g. 'oral-glp1r-discovery')",
        "description": "Short 1-sentence description of when agents should use this skill",
        "scope": "Source brain scope ('global', 'project:<id>', or 'specialist:<id>')",
        "topic": "Optional keyword filter to include only matching memories, wiki pages, and graph nodes",
        "wiki_slug": "Optional specific Living Wiki page slug to turn into a skill",
        "custom_instructions": "Optional extra step-by-step instructions to include in SKILL.md",
    },
    usage_guide=(
        "Use when the user asks to turn what we know about a topic, a Living Wiki page, "
        "or an Omnigraph Cookbook ontology into a reusable Skill (/skill-slug)."
    ),
)
def create_skill_from_memory(
    name: str,
    slug: str = "",
    description: str = "",
    scope: str = "global",
    topic: str = "",
    wiki_slug: str = "",
    custom_instructions: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    from agent_server.models.memory import CreateSkillFromMemoryRequest

    svc = _service()
    res = svc.create_skill(
        CreateSkillFromMemoryRequest(
            scope=scope,
            name=name,
            slug=slug.strip() or None,
            description=description.strip() or None,
            topic=topic.strip() or None,
            wiki_slug=wiki_slug.strip() or None,
            custom_instructions=custom_instructions.strip() or None,
        )
    )
    return res.model_dump(mode="json", by_alias=True)


@registry.register(
    name="memory.select_cookbook",
    description=(
        "Switch a scope's active Omnigraph Cookbook Mode (01 industry-intel, 02 pharma-intel, "
        "03 context-graph, 04 vc-os, 05 biomed-research, 06 second-brain) and optionally seed it."
    ),
    category="memory",
    parameters={
        "cookbook_id": (
            "Cookbook ID: 'industry-intel', 'pharma-intel', 'context-graph', "
            "'vc-os', 'biomed-research', or 'second-brain'"
        ),
        "scope": "Scope: 'global', 'project:<id>', or 'specialist:<id>' (default 'global')",
        "load_demo_seed": "Whether to populate the cookbook's starter graph seed (default False)",
    },
    usage_guide="Use when the user asks to change the active ontology / Cookbook mode for a brain scope.",
)
def select_cookbook_tool(
    cookbook_id: str,
    scope: str = "global",
    load_demo_seed: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    svc = _service()
    snap = svc.select_cookbook(
        scope=scope,
        cookbook_id=cookbook_id.strip(),
        load_demo_seed=bool(load_demo_seed),
    )
    return {
        "ok": True,
        "scope": snap.scope,
        "cookbookId": snap.active_cookbook.id,
        "cookbookName": snap.active_cookbook.name,
        "nodes": len(snap.nodes),
        "edges": len(snap.edges),
        "summary": (
            f"Switched {snap.scope} ontology to {snap.active_cookbook.number} "
            f"{snap.active_cookbook.name} ({len(snap.nodes)} nodes, {len(snap.edges)} edges)."
        ),
    }


@registry.register(
    name="memory.distill_session",
    description="Distill a chat session into durable MEMORY.md notes, a Living Wiki page, and Knowledge Graph claims.",
    category="memory",
    parameters={
        "session_id": "Chat session ID to distill",
        "scope": "Optional target scope ('global', 'project:<id>', or 'specialist:<id>')",
    },
    usage_guide="Use when the user asks to distill or extract takeaways from a session into Memory/Wiki/Graph.",
)
def distill_session_tool(
    session_id: str,
    scope: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    svc = _service()
    res = svc.distill_session(
        session_id.strip(),
        scope=scope.strip() or None,
    )
    return res.model_dump(mode="json", by_alias=True)


