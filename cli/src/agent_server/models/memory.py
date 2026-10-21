"""API models for Sandwalk Memory, Living Wiki, Cookbooks, and Omnigraph."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from agent_server.models.base import ApiModel

MemoryScopeKind = Literal["user", "global", "project", "specialist", "capy"]
MemoryLayer = Literal["L1", "L2", "L3"]
MemoryWriteStatus = Literal["active", "pending", "rejected"]
CookbookId = Literal[
    "biomed-research",
    "pharma-intel",
    "industry-intel",
    "context-graph",
    "vc-os",
    "second-brain",
]


class MemoryEntry(ApiModel):
    id: str
    scope: str
    target: Literal["user", "memory", "project", "specialist"] = "memory"
    layer: MemoryLayer = "L1"
    content: str
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False
    status: MemoryWriteStatus = "active"
    source_session_id: str | None = None
    created_at: str
    updated_at: str


class MemoryEntryList(ApiModel):
    data: list[MemoryEntry] = Field(default_factory=list)
    scope: str
    char_used: int = 0
    char_limit: int = 2200
    user_char_used: int = 0
    user_char_limit: int = 1375


class CreateMemoryEntryRequest(ApiModel):
    scope: str = "global"
    target: Literal["user", "memory", "project", "specialist"] = "memory"
    layer: MemoryLayer = "L1"
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False
    source_session_id: str | None = None


class UpdateMemoryEntryRequest(ApiModel):
    content: str | None = None
    old_text: str | None = None
    tags: list[str] | None = None
    pinned: bool | None = None


class PendingMemoryWrite(ApiModel):
    id: str
    scope: str
    kind: Literal["memory", "wiki", "graph_claim", "graph_node"] = "memory"
    action: Literal["add", "patch", "remove", "write", "claim", "node"] = "add"
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    source_session_id: str | None = None
    created_at: str


class PendingMemoryWriteList(ApiModel):
    data: list[PendingMemoryWrite] = Field(default_factory=list)


class WikiPageSummary(ApiModel):
    slug: str
    title: str
    scope: str
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    backlinks: list[str] = Field(default_factory=list)
    updated_at: str
    path: str


class WikiPageDetail(WikiPageSummary):
    content: str


class WikiPageList(ApiModel):
    data: list[WikiPageSummary] = Field(default_factory=list)
    scope: str


class UpsertWikiPageRequest(ApiModel):
    scope: str = "global"
    title: str = Field(min_length=1)
    content: str
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)


class OntologyPropertyDef(ApiModel):
    name: str
    type: str
    is_key: bool = False
    is_indexed: bool = False
    optional: bool = False


class OntologyNodeTypeDef(ApiModel):
    name: str
    layer: str
    color: str
    description: str = ""
    count: int = 0
    properties: list[OntologyPropertyDef] = Field(default_factory=list)


class OntologyEdgeTypeDef(ApiModel):
    predicate: str
    source_type: str
    target_type: str
    polarity: Literal["support", "contradict", "neutral"] = "neutral"
    count: int = 0


class OntologyLayerDef(ApiModel):
    id: str
    label: str
    description: str
    node_types: list[str] = Field(default_factory=list)


class StoredQueryDef(ApiModel):
    name: str
    label: str
    description: str
    gq_source: str


class CookbookSummary(ApiModel):
    id: str
    number: str
    name: str
    tagline: str
    description: str
    default_for: str
    layers: list[OntologyLayerDef] = Field(default_factory=list)
    node_types: list[OntologyNodeTypeDef] = Field(default_factory=list)
    edge_types: list[OntologyEdgeTypeDef] = Field(default_factory=list)
    stored_queries: list[StoredQueryDef] = Field(default_factory=list)
    pg_schema: str = ""


class CookbookList(ApiModel):
    data: list[CookbookSummary] = Field(default_factory=list)
    active_cookbook_id: str


class SelectCookbookRequest(ApiModel):
    scope: str = "global"
    cookbook_id: str
    load_demo_seed: bool = False


class RunCookbookQueryRequest(ApiModel):
    scope: str = "global"
    query_name: str
    branch: str = "main"
    params: dict[str, Any] = Field(default_factory=dict)


class GraphNode(ApiModel):
    id: str
    slug: str
    node_type: str
    layer: str = "domain"
    name: str
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    source_ref: str | None = None
    branch: str = "main"
    updated_at: str


class GraphEdge(ApiModel):
    id: str
    source_id: str
    target_id: str
    predicate: str
    polarity: Literal["support", "contradict", "neutral"] = "neutral"
    score: float = 0.8
    summary: str = ""
    source_ref: str | None = None
    branch: str = "main"
    updated_at: str


class GraphBranch(ApiModel):
    name: str
    is_default: bool = False
    node_count: int = 0
    edge_count: int = 0
    updated_at: str


class GraphSnapshot(ApiModel):
    scope: str
    branch: str = "main"
    active_cookbook: CookbookSummary
    branches: list[GraphBranch] = Field(default_factory=list)
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    contradiction_count: int = 0
    matched_node_ids: list[str] = Field(default_factory=list)
    active_query_name: str | None = None


class UpsertGraphNodeRequest(ApiModel):
    scope: str = "global"
    branch: str = "main"
    node_type: str
    slug: str | None = None
    name: str = Field(min_length=1)
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    source_ref: str | None = None


class CreateGraphClaimRequest(ApiModel):
    scope: str = "global"
    branch: str = "main"
    subject_id: str
    subject_type: str = "Entity"
    subject_name: str | None = None
    predicate: str = "Supports"
    object_id: str
    object_type: str = "Claim"
    object_name: str | None = None
    polarity: Literal["support", "contradict", "neutral"] = "support"
    score: float = 0.85
    summary: str = ""
    source_ref: str | None = None


class GraphBranchActionRequest(ApiModel):
    scope: str = "global"
    action: Literal["create", "merge", "delete"]
    name: str = Field(min_length=1)
    target_branch: str = "main"


class OmnigraphEngineStatus(ApiModel):
    installed: bool
    binary_path: str | None = None
    server_binary_path: str | None = None
    version: str | None = None
    store_path: str
    mcp_enabled: bool = False
    phase: Literal["idle", "installing", "ready", "error"] = "idle"
    detail: str = ""


class MemorySettings(ApiModel):
    enabled: bool = True
    user_profile_enabled: bool = True
    wiki_enabled: bool = True
    graph_enabled: bool = True
    default_cookbook: str = "biomed-research"
    global_cookbook: str = "second-brain"
    memory_char_limit: int = 2200
    user_char_limit: int = 1375
    wiki_toc_max_chars: int = 1800
    write_approval: bool = False
    graph_branch_on_write: bool = False
    distiller_mode: Literal["hybrid", "manual", "auto"] = "hybrid"
    distiller_provider: str = "auto"
    distiller_model: str = "auto"
    distiller_openai_profile_id: str = ""
    distiller_defer_on_local_gpu: bool = True
    distiller_max_input_tokens: int = 48000
    embeddings_provider: Literal[
        "none", "openrouter", "openai", "gemini", "local_llama", "custom_profile"
    ] = "none"
    embeddings_model: str = ""
    embeddings_profile_id: str = ""


class UpdateMemorySettingsRequest(ApiModel):
    enabled: bool | None = None
    user_profile_enabled: bool | None = None
    wiki_enabled: bool | None = None
    graph_enabled: bool | None = None
    default_cookbook: str | None = None
    global_cookbook: str | None = None
    memory_char_limit: int | None = None
    user_char_limit: int | None = None
    wiki_toc_max_chars: int | None = None
    write_approval: bool | None = None
    graph_branch_on_write: bool | None = None
    distiller_mode: Literal["hybrid", "manual", "auto"] | None = None
    distiller_provider: str | None = None
    distiller_model: str | None = None
    distiller_openai_profile_id: str | None = None
    distiller_defer_on_local_gpu: bool | None = None
    distiller_max_input_tokens: int | None = None
    embeddings_provider: (
        Literal["none", "openrouter", "openai", "gemini", "local_llama", "custom_profile"]
        | None
    ) = None
    embeddings_model: str | None = None
    embeddings_profile_id: str | None = None


class MemoryOverview(ApiModel):
    scope: str
    active_cookbook_id: str
    memory_count: int = 0
    user_memory_count: int = 0
    pending_count: int = 0
    wiki_page_count: int = 0
    graph_node_count: int = 0
    graph_edge_count: int = 0
    contradiction_count: int = 0
    char_used: int = 0
    char_limit: int = 2200
    user_char_used: int = 0
    user_char_limit: int = 1375
    omnigraph: OmnigraphEngineStatus
    settings: MemorySettings


class DistillSessionRequest(ApiModel):
    scope: str | None = None
    include_wiki: bool = True
    include_graph: bool = True


class DistillSessionResponse(ApiModel):
    ok: bool = True
    session_id: str
    scope: str
    memories_added: int = 0
    wiki_slug: str | None = None
    nodes_added: int = 0
    claims_added: int = 0
    staged_for_approval: bool = False
    summary: str


class CreateSkillFromMemoryRequest(ApiModel):
    scope: str = "global"
    name: str = Field(min_length=1)
    slug: str | None = None
    description: str | None = None
    topic: str | None = None
    wiki_slug: str | None = None
    include_memories: bool = True
    include_wiki: bool = True
    include_graph: bool = True
    custom_instructions: str | None = None


class CreatedSkillResponse(ApiModel):
    ok: bool = True
    skill_name: str
    skill_dir: str
    skill_md_path: str
    scope: str
    cookbook_id: str
    memories_included: int = 0
    wiki_pages_included: int = 0
    graph_nodes_included: int = 0
    summary: str

