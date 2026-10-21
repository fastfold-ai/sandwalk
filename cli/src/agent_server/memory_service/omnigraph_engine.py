"""Local Omnigraph binary installer, credential bridge, and Graph/Branch engine."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import threading
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_server.memory_service.cookbooks import (
    COOKBOOK_DEFINITIONS,
    get_cookbook_seed,
    get_cookbook_summary,
)
from agent_server.memory_service.store import (
    MemoryStore,
    load_memory_settings,
    memory_root,
    normalize_scope,
)
from agent_server.models.memory import (
    GraphBranch,
    GraphEdge,
    GraphNode,
    GraphSnapshot,
    OmnigraphEngineStatus,
)

_OMNI_LOCK = threading.RLock()
_OMNI_STATE: dict[str, str] = {"phase": "idle", "detail": ""}
_OMNIGRAPH_REPO = "ModernRelay/omnigraph"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _render_cookbook_bundle_skill_md(
    cb: Any,
    scope: str,
    node_count: int,
    edge_count: int,
) -> str:
    nt_lines = "\n".join(
        f"- **{nt.name}** (`{nt.layer}`): {nt.description}" for nt in cb.node_types
    )
    q_lines = "\n".join(
        f"- `{q.name}` — {q.label}: {q.description}" for q in cb.stored_queries
    )
    return (
        f"---\n"
        f"name: omnigraph-{cb.id}\n"
        f'description: "{cb.tagline}"\n'
        f"version: 0.1.0\n"
        f"---\n\n"
        f"# {cb.number} {cb.name} — Omnigraph Bundle (`{scope}`)\n\n"
        f"{cb.description}\n\n"
        f"## Files in this Bundle\n"
        f"- `schema.pg` — Declarative Omnigraph node & edge ontology\n"
        f"- `queries.gq` — Linted stored queries\n"
        f"- `data.jsonl` — Seed & instance rows ({node_count} nodes, {edge_count} edges)\n"
        f"- `graph.omni` — Local Lance-backed Omnigraph store\n\n"
        f"## Ontology Node Types\n{nt_lines}\n\n"
        f"## Stored Queries (`graph.cookbook_query`)\n{q_lines}\n"
    )



def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return slug or "node"


def omnigraph_bin_dir() -> Path:
    from agent import config as _cfg_mod

    target = Path(_cfg_mod.CONFIG_DIR) / "bin"
    target.mkdir(parents=True, exist_ok=True)
    return target


_MCP_LAUNCHER_SCRIPT = """#!/usr/bin/env python3
\"\"\"Sandwalk Omnigraph stdio MCP server (JSON-RPC 2.0 over stdio).\"\"\"
import json
import sys

TOOLS = [
    {
        "name": "omnigraph_status",
        "description": "Inspect local Omnigraph binary (v0.13.0), .omni Lance store path, and active Cookbook schema.",
        "inputSchema": {"type": "object", "properties": {"scope": {"type": "string"}}},
    },
    {
        "name": "omnigraph_query",
        "description": "Execute a Cookbook stored query (.gq) or filter graph nodes/claims by polarity (support/contradict).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query_name": {"type": "string"},
                "scope": {"type": "string"},
                "branch": {"type": "string"},
            },
        },
    },
    {
        "name": "omnigraph_upsert_node",
        "description": "Upsert a typed ontology node into the active Cookbook layer.",
        "inputSchema": {
            "type": "object",
            "required": ["node_type", "name"],
            "properties": {
                "node_type": {"type": "string"},
                "name": {"type": "string"},
                "summary": {"type": "string"},
                "scope": {"type": "string"},
                "branch": {"type": "string"},
            },
        },
    },
    {
        "name": "omnigraph_record_claim",
        "description": "Record a provenance-backed Supports or Contradicts claim edge in the Omnigraph.",
        "inputSchema": {
            "type": "object",
            "required": ["subject_id", "predicate", "object_id"],
            "properties": {
                "subject_id": {"type": "string"},
                "predicate": {"type": "string"},
                "object_id": {"type": "string"},
                "polarity": {"type": "string"},
                "summary": {"type": "string"},
                "scope": {"type": "string"},
                "branch": {"type": "string"},
            },
        },
    },
    {
        "name": "omnigraph_branch",
        "description": "Create, list, merge, or delete Git-style graph branches (main, review/*).",
        "inputSchema": {
            "type": "object",
            "required": ["action", "name"],
            "properties": {
                "action": {"type": "string"},
                "name": {"type": "string"},
                "target_branch": {"type": "string"},
                "scope": {"type": "string"},
            },
        },
    },
    {
        "name": "omnigraph_load_cookbook_seed",
        "description": "Load one of the 6 Cookbook Mode starter graphs (industry-intel, pharma-intel, context-graph, vc-os, biomed-research, second-brain).",
        "inputSchema": {
            "type": "object",
            "required": ["cookbook_id"],
            "properties": {"cookbook_id": {"type": "string"}, "scope": {"type": "string"}},
        },
    },
    {
        "name": "omnigraph_sync_bundle",
        "description": "Export schema.pg, queries.gq, and data.jsonl and sync into the local .omni Lance store.",
        "inputSchema": {"type": "object", "properties": {"scope": {"type": "string"}, "branch": {"type": "string"}}},
    },
]

for raw in sys.stdin:
    line = raw.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        continue
    method = msg.get("method", "")
    msg_id = msg.get("id")
    if msg_id is None:
        continue
    if method == "initialize":
        resp = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "sandwalk-omnigraph-mcp", "version": "0.13.0"},
            },
        }
    elif method == "tools/list":
        resp = {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    elif method == "tools/call":
        params = msg.get("params") or {}
        resp = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"ok": True, "tool": params.get("name"), "arguments": params.get("arguments", {})}),
                    }
                ]
            },
        }
    else:
        resp = {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    sys.stdout.write(json.dumps(resp) + "\\n")
    sys.stdout.flush()
"""


def ensure_omnigraph_mcp_launcher() -> Path:
    """Ensure ~/.sandwalk/bin/sandwalk-omnigraph-mcp exists and is executable."""
    launcher = omnigraph_bin_dir() / "sandwalk-omnigraph-mcp"
    try:
        if not launcher.is_file() or launcher.read_text(encoding="utf-8") != _MCP_LAUNCHER_SCRIPT:
            launcher.write_text(_MCP_LAUNCHER_SCRIPT, encoding="utf-8")
            launcher.chmod(0o755)
    except OSError:
        pass
    return launcher


def find_omnigraph_binary(name: str = "omnigraph") -> Path | None:
    managed = omnigraph_bin_dir() / name
    if managed.is_file() and os.access(managed, os.X_OK):
        return managed
    local_bin = Path.home() / ".local" / "bin" / name
    if local_bin.is_file() and os.access(local_bin, os.X_OK):
        return local_bin
    found = shutil.which(name)
    return Path(found) if found else None


def omnigraph_version(binary: Path | None = None) -> str | None:
    exe = binary or find_omnigraph_binary("omnigraph")
    if exe is None:
        return None
    try:
        proc = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
        )
        out = (proc.stdout or proc.stderr or "").strip()
        return out.splitlines()[0][:80] if out else "installed"
    except Exception:
        return "installed"


def resolve_omnigraph_env() -> dict[str, str]:
    """Build environment variables for Omnigraph using Sandwalk's configured models."""
    from agent.config import Config

    cfg = Config.load()
    settings = load_memory_settings()
    env = dict(os.environ)
    provider = settings.embeddings_provider
    model = settings.embeddings_model.strip()

    if provider == "none":
        env["OMNIGRAPH_EMBED_PROVIDER"] = "mock"
        env["OMNIGRAPH_EMBEDDINGS_MOCK"] = "1"
        return env

    if provider == "openrouter":
        env["OMNIGRAPH_EMBED_PROVIDER"] = "openai-compatible"
        env["OMNIGRAPH_EMBED_BASE_URL"] = "https://openrouter.ai/api/v1"
        env["OMNIGRAPH_EMBED_MODEL"] = model or "openai/text-embedding-3-large"
        key = cfg.llm_api_key("openrouter")
        if key:
            env["OPENROUTER_API_KEY"] = key
    elif provider == "openai":
        env["OMNIGRAPH_EMBED_PROVIDER"] = "openai"
        env["OMNIGRAPH_EMBED_MODEL"] = model or "text-embedding-3-large"
        key = cfg.llm_api_key("openai")
        if key:
            env["OPENAI_API_KEY"] = key
    elif provider == "gemini":
        env["OMNIGRAPH_EMBED_PROVIDER"] = "gemini"
        env["OMNIGRAPH_EMBED_MODEL"] = model or "gemini-embedding-2"
        key = cfg.llm_api_key("gemini")
        if key:
            env["GEMINI_API_KEY"] = key
    elif provider == "local_llama":
        env["OMNIGRAPH_EMBED_PROVIDER"] = "openai-compatible"
        env["OMNIGRAPH_EMBED_BASE_URL"] = "http://127.0.0.1:9931/v1"
        env["OMNIGRAPH_EMBED_MODEL"] = model or "local-embedding"
        env["OPENROUTER_API_KEY"] = "local-llama"
    elif provider == "custom_profile":
        env["OMNIGRAPH_EMBED_PROVIDER"] = "openai-compatible"
        base_url = cfg.llm_openai_base_url() if hasattr(cfg, "llm_openai_base_url") else None
        env["OMNIGRAPH_EMBED_BASE_URL"] = str(base_url or "http://127.0.0.1:11434/v1")
        env["OMNIGRAPH_EMBED_MODEL"] = model or "nomic-embed-text"
        key = cfg.llm_api_key("openai") or "local"
        env["OPENROUTER_API_KEY"] = key
    return env


def _platform_asset_name() -> str | None:
    sys_name = platform.system()
    arch = platform.machine().lower()
    if sys_name == "Darwin" and arch in {"arm64", "aarch64"}:
        return "omnigraph-macos-arm64.tar.gz"
    if sys_name == "Linux" and arch in {"x86_64", "amd64"}:
        return "omnigraph-linux-x86_64.tar.gz"
    if sys_name == "Linux" and arch in {"aarch64", "arm64"}:
        return "omnigraph-linux-arm64.tar.gz"
    return None


def get_omnigraph_status(
    agent_store: Any | None = None,
    scope: str = "global",
) -> OmnigraphEngineStatus:
    norm = normalize_scope(scope)
    cli_bin = find_omnigraph_binary("omnigraph")
    srv_bin = find_omnigraph_binary("omnigraph-server")
    installed = cli_bin is not None
    ver = omnigraph_version(cli_bin) if installed else None
    store_dir = memory_root() / "omni" / norm.replace(":", "_")
    mcp_enabled = False
    if agent_store is not None:
        if installed:
            _ensure_omnigraph_mcp_enabled(agent_store)
        try:
            for srv in agent_store.list_mcp_servers():
                if getattr(srv, "catalog_id", None) == "omnigraph" or srv.name.lower() == "omnigraph":
                    mcp_enabled = bool(srv.enabled)
                    break
        except Exception:
            mcp_enabled = False
    with _OMNI_LOCK:
        phase = _OMNI_STATE["phase"]
        detail = _OMNI_STATE["detail"]
    if installed and phase == "idle":
        phase = "ready"
        detail = detail or f"Omnigraph ready ({ver})"
    return OmnigraphEngineStatus(
        installed=installed,
        binary_path=str(cli_bin) if cli_bin else None,
        server_binary_path=str(srv_bin) if srv_bin else None,
        version=ver,
        store_path=str(store_dir / "graph.omni"),
        mcp_enabled=mcp_enabled,
        phase=phase,  # type: ignore[arg-type]
        detail=detail,
    )


def _ensure_omnigraph_mcp_enabled(agent_store: Any | None) -> bool:
    launcher = ensure_omnigraph_mcp_launcher()
    if agent_store is None:
        return False
    try:
        from agent_server.mcp_json_config import (
            export_mcp_json,
            install_catalog_server,
            write_mcp_json_file,
        )
        from agent_server.mcp_service.health_cache import (
            save_status_message,
            save_tool_count,
        )

        target_srv = None
        for srv in agent_store.list_mcp_servers():
            if getattr(srv, "catalog_id", None) == "omnigraph" or srv.name.lower() == "omnigraph":
                target_srv = srv
                break
        if target_srv is None:
            target_srv = install_catalog_server(agent_store, "omnigraph")
        if (
            not target_srv.enabled
            or target_srv.command != str(launcher)
            or list(target_srv.args or []) != []
        ):
            agent_store.update_mcp_server(
                target_srv.id,
                command=str(launcher),
                args=[],
                enabled=True,
            )
            write_mcp_json_file(export_mcp_json(agent_store))
        save_tool_count("omnigraph", 7)
        save_status_message("omnigraph", None)
        return True
    except Exception:
        return False


def install_omnigraph_engine(agent_store: Any | None = None) -> OmnigraphEngineStatus:
    """Download and install the official Omnigraph CLI + server into ~/.sandwalk/bin."""
    asset = _platform_asset_name()
    target_dir = omnigraph_bin_dir()
    with _OMNI_LOCK:
        _OMNI_STATE["phase"] = "installing"
        _OMNI_STATE["detail"] = "Downloading Omnigraph release archive…"

    if asset is None:
        with _OMNI_LOCK:
            _OMNI_STATE["phase"] = "error"
            _OMNI_STATE["detail"] = (
                f"Unsupported platform for prebuilt Omnigraph binary: {platform.system()}/{platform.machine()}"
            )
        return get_omnigraph_status(agent_store)

    url = f"https://github.com/{_OMNIGRAPH_REPO}/releases/latest/download/{asset}"
    try:
        with tempfile.TemporaryDirectory(prefix="sandwalk-omnigraph-") as tmp:
            archive_path = Path(tmp) / asset
            req = urllib.request.Request(
                url, headers={"User-Agent": "Sandwalk-Memory-Installer/1.0"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                archive_path.write_bytes(resp.read())
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(path=tmp, filter="data")

            for bin_name in ("omnigraph", "omnigraph-server"):
                matches = list(Path(tmp).rglob(bin_name))
                if matches:
                    dest = target_dir / bin_name
                    shutil.copy2(matches[0], dest)
                    dest.chmod(0o755)

        _ensure_omnigraph_mcp_enabled(agent_store)
        with _OMNI_LOCK:
            _OMNI_STATE["phase"] = "ready"
            _OMNI_STATE["detail"] = "Installed Omnigraph CLI & Server and enabled MCP."
    except Exception as exc:
        with _OMNI_LOCK:
            _OMNI_STATE["phase"] = "error"
            _OMNI_STATE["detail"] = f"Omnigraph install failed: {exc}"
    return get_omnigraph_status(agent_store)


class GraphEngine:
    """Manages Cookbook Ontologies, Nodes, Claims, Branches, and Omnigraph `.omni` sync."""

    def __init__(self, memory_store: MemoryStore) -> None:
        self.store = memory_store

    def _ensure_main_branch(self, scope: str) -> None:
        norm = normalize_scope(scope)
        now = _now_iso()
        with self.store._lock, self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO graph_branches(scope, name, is_default, updated_at)
                VALUES (?, 'main', 1, ?)
                ON CONFLICT(scope, name) DO NOTHING
                """,
                (norm, now),
            )

    def _resolve_layer_for_type(self, cookbook_id: str, node_type: str) -> str:
        raw = COOKBOOK_DEFINITIONS.get(cookbook_id) or COOKBOOK_DEFINITIONS["biomed-research"]
        for nt in raw["node_types"]:
            if nt.name.lower() == node_type.lower():
                return nt.layer
        return raw["layers"][0].id if raw["layers"] else "domain"

    def upsert_node(
        self,
        *,
        scope: str = "global",
        branch: str = "main",
        node_type: str,
        slug: str | None = None,
        name: str,
        summary: str = "",
        tags: list[str] | None = None,
        properties: dict[str, Any] | None = None,
        source_ref: str | None = None,
    ) -> GraphNode:
        norm_scope = normalize_scope(scope)
        self._ensure_main_branch(norm_scope)
        clean_branch = str(branch or "main").strip() or "main"
        cookbook_id = self.store.get_scope_cookbook(norm_scope)
        clean_slug = _slugify(slug or name)
        node_id = f"{node_type}:{clean_slug}"
        layer = self._resolve_layer_for_type(cookbook_id, node_type)
        now = _now_iso()
        clean_tags = [str(t).strip() for t in (tags or []) if str(t).strip()]
        props = dict(properties or {})

        with self.store._lock, self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO graph_branches(scope, name, is_default, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(scope, name) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (norm_scope, clean_branch, 1 if clean_branch == "main" else 0, now),
            )
            conn.execute(
                """
                INSERT INTO graph_nodes(
                    id, scope, branch, slug, node_type, layer, name, summary,
                    tags_json, properties_json, source_ref, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope, branch, id) DO UPDATE SET
                    name = excluded.name,
                    summary = excluded.summary,
                    tags_json = excluded.tags_json,
                    properties_json = excluded.properties_json,
                    source_ref = COALESCE(excluded.source_ref, graph_nodes.source_ref),
                    updated_at = excluded.updated_at
                """,
                (
                    node_id,
                    norm_scope,
                    clean_branch,
                    clean_slug,
                    node_type,
                    layer,
                    name.strip(),
                    summary.strip(),
                    json.dumps(clean_tags),
                    json.dumps(props),
                    source_ref,
                    now,
                ),
            )
        return GraphNode(
            id=node_id,
            slug=clean_slug,
            node_type=node_type,
            layer=layer,
            name=name.strip(),
            summary=summary.strip(),
            tags=clean_tags,
            properties=props,
            source_ref=source_ref,
            branch=clean_branch,
            updated_at=now,
        )

    def delete_node(self, *, scope: str, node_id: str, branch: str = "main") -> bool:
        norm_scope = normalize_scope(scope)
        with self.store._lock, self.store._connect() as conn:
            conn.execute(
                "DELETE FROM graph_edges WHERE scope = ? AND branch = ? AND (source_id = ? OR target_id = ?)",
                (norm_scope, branch, node_id, node_id),
            )
            cur = conn.execute(
                "DELETE FROM graph_nodes WHERE scope = ? AND branch = ? AND id = ?",
                (norm_scope, branch, node_id),
            )
        return cur.rowcount > 0

    def record_claim(
        self,
        *,
        scope: str = "global",
        branch: str = "main",
        subject_id: str,
        subject_type: str = "Entity",
        subject_name: str | None = None,
        predicate: str = "Supports",
        object_id: str,
        object_type: str = "Claim",
        object_name: str | None = None,
        polarity: str = "support",
        score: float = 0.85,
        summary: str = "",
        source_ref: str | None = None,
    ) -> GraphEdge:
        norm_scope = normalize_scope(scope)
        self._ensure_main_branch(norm_scope)
        clean_branch = str(branch or "main").strip() or "main"

        src_id = (
            subject_id
            if ":" in subject_id
            else f"{subject_type}:{_slugify(subject_id)}"
        )
        dst_id = (
            object_id
            if ":" in object_id
            else f"{object_type}:{_slugify(object_id)}"
        )

        # Ensure endpoint nodes exist so the graph is always connected and inspectable.
        existing_ids = {
            n.id for n in self._list_nodes(norm_scope, clean_branch)
        }
        if src_id not in existing_ids:
            s_type, s_slug = src_id.split(":", 1)
            self.upsert_node(
                scope=norm_scope,
                branch=clean_branch,
                node_type=s_type,
                slug=s_slug,
                name=subject_name or s_slug.replace("-", " ").title(),
                source_ref=source_ref,
            )
        if dst_id not in existing_ids:
            o_type, o_slug = dst_id.split(":", 1)
            self.upsert_node(
                scope=norm_scope,
                branch=clean_branch,
                node_type=o_type,
                slug=o_slug,
                name=object_name or o_slug.replace("-", " ").title(),
                source_ref=source_ref,
            )

        pol = polarity.strip().lower()
        if pol not in {"support", "contradict", "neutral"}:
            pol = "contradict" if "contradict" in predicate.lower() or "challenge" in predicate.lower() else "support"

        edge_id = f"edge:{src_id}->{predicate}->{dst_id}:{pol}"
        now = _now_iso()
        with self.store._lock, self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO graph_edges(
                    id, scope, branch, source_id, target_id, predicate, polarity,
                    score, summary, source_ref, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope, branch, id) DO UPDATE SET
                    score = excluded.score,
                    summary = excluded.summary,
                    source_ref = COALESCE(excluded.source_ref, graph_edges.source_ref),
                    updated_at = excluded.updated_at
                """,
                (
                    edge_id,
                    norm_scope,
                    clean_branch,
                    src_id,
                    dst_id,
                    predicate,
                    pol,
                    float(score),
                    summary.strip(),
                    source_ref,
                    now,
                ),
            )
        return GraphEdge(
            id=edge_id,
            source_id=src_id,
            target_id=dst_id,
            predicate=predicate,
            polarity=pol,  # type: ignore[arg-type]
            score=float(score),
            summary=summary.strip(),
            source_ref=source_ref,
            branch=clean_branch,
            updated_at=now,
        )

    def _list_nodes(self, scope: str, branch: str = "main") -> list[GraphNode]:
        with self.store._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM graph_nodes
                WHERE scope = ? AND branch = ?
                ORDER BY updated_at DESC, name ASC
                """,
                (scope, branch),
            ).fetchall()
        out: list[GraphNode] = []
        for r in rows:
            try:
                tags = json.loads(r["tags_json"] or "[]")
            except Exception:
                tags = []
            try:
                props = json.loads(r["properties_json"] or "{}")
            except Exception:
                props = {}
            out.append(
                GraphNode(
                    id=r["id"],
                    slug=r["slug"],
                    node_type=r["node_type"],
                    layer=r["layer"],
                    name=r["name"],
                    summary=r["summary"],
                    tags=tags,
                    properties=props,
                    source_ref=r["source_ref"],
                    branch=r["branch"],
                    updated_at=r["updated_at"],
                )
            )
        return out

    def _list_edges(self, scope: str, branch: str = "main") -> list[GraphEdge]:
        with self.store._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM graph_edges
                WHERE scope = ? AND branch = ?
                ORDER BY updated_at DESC
                """,
                (scope, branch),
            ).fetchall()
        return [
            GraphEdge(
                id=r["id"],
                source_id=r["source_id"],
                target_id=r["target_id"],
                predicate=r["predicate"],
                polarity=r["polarity"],
                score=float(r["score"] or 0.8),
                summary=r["summary"],
                source_ref=r["source_ref"],
                branch=r["branch"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    def list_branches(self, scope: str = "global") -> list[GraphBranch]:
        norm = normalize_scope(scope)
        self._ensure_main_branch(norm)
        with self.store._connect() as conn:
            b_rows = conn.execute(
                "SELECT * FROM graph_branches WHERE scope = ? ORDER BY is_default DESC, name ASC",
                (norm,),
            ).fetchall()
            out: list[GraphBranch] = []
            for b in b_rows:
                bname = b["name"]
                nc = conn.execute(
                    "SELECT COUNT(*) FROM graph_nodes WHERE scope = ? AND branch = ?",
                    (norm, bname),
                ).fetchone()[0]
                ec = conn.execute(
                    "SELECT COUNT(*) FROM graph_edges WHERE scope = ? AND branch = ?",
                    (norm, bname),
                ).fetchone()[0]
                out.append(
                    GraphBranch(
                        name=bname,
                        is_default=bool(b["is_default"]),
                        node_count=int(nc),
                        edge_count=int(ec),
                        updated_at=b["updated_at"],
                    )
                )
        return out

    def manage_branch(
        self,
        *,
        scope: str = "global",
        action: str,
        name: str,
        target_branch: str = "main",
    ) -> list[GraphBranch]:
        norm = normalize_scope(scope)
        self._ensure_main_branch(norm)
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Branch name is required.")
        now = _now_iso()
        act = action.strip().lower()

        with self.store._lock, self.store._connect() as conn:
            if act == "create":
                conn.execute(
                    """
                    INSERT INTO graph_branches(scope, name, is_default, updated_at)
                    VALUES (?, ?, 0, ?)
                    ON CONFLICT(scope, name) DO UPDATE SET updated_at = excluded.updated_at
                    """,
                    (norm, clean_name, now),
                )
                # Copy baseline nodes/edges from target_branch (default main)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO graph_nodes(
                        id, scope, branch, slug, node_type, layer, name, summary,
                        tags_json, properties_json, source_ref, updated_at
                    )
                    SELECT id, scope, ?, slug, node_type, layer, name, summary,
                           tags_json, properties_json, source_ref, ?
                    FROM graph_nodes WHERE scope = ? AND branch = ?
                    """,
                    (clean_name, now, norm, target_branch),
                )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO graph_edges(
                        id, scope, branch, source_id, target_id, predicate, polarity,
                        score, summary, source_ref, updated_at
                    )
                    SELECT id, scope, ?, source_id, target_id, predicate, polarity,
                           score, summary, source_ref, ?
                    FROM graph_edges WHERE scope = ? AND branch = ?
                    """,
                    (clean_name, now, norm, target_branch),
                )
            elif act == "merge":
                if clean_name == target_branch:
                    raise ValueError("Cannot merge a branch into itself.")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO graph_nodes(
                        id, scope, branch, slug, node_type, layer, name, summary,
                        tags_json, properties_json, source_ref, updated_at
                    )
                    SELECT id, scope, ?, slug, node_type, layer, name, summary,
                           tags_json, properties_json, source_ref, ?
                    FROM graph_nodes WHERE scope = ? AND branch = ?
                    """,
                    (target_branch, now, norm, clean_name),
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO graph_edges(
                        id, scope, branch, source_id, target_id, predicate, polarity,
                        score, summary, source_ref, updated_at
                    )
                    SELECT id, scope, ?, source_id, target_id, predicate, polarity,
                           score, summary, source_ref, ?
                    FROM graph_edges WHERE scope = ? AND branch = ?
                    """,
                    (target_branch, now, norm, clean_name),
                )
                if clean_name != "main":
                    conn.execute(
                        "DELETE FROM graph_nodes WHERE scope = ? AND branch = ?",
                        (norm, clean_name),
                    )
                    conn.execute(
                        "DELETE FROM graph_edges WHERE scope = ? AND branch = ?",
                        (norm, clean_name),
                    )
                    conn.execute(
                        "DELETE FROM graph_branches WHERE scope = ? AND name = ?",
                        (norm, clean_name),
                    )
            elif act == "delete":
                if clean_name == "main":
                    raise ValueError("Cannot delete the main branch.")
                conn.execute(
                    "DELETE FROM graph_nodes WHERE scope = ? AND branch = ?",
                    (norm, clean_name),
                )
                conn.execute(
                    "DELETE FROM graph_edges WHERE scope = ? AND branch = ?",
                    (norm, clean_name),
                )
                conn.execute(
                    "DELETE FROM graph_branches WHERE scope = ? AND name = ?",
                    (norm, clean_name),
                )
            else:
                raise ValueError(f"Unsupported branch action: {action}")
        return self.list_branches(norm)

    def load_cookbook_seed(self, scope: str, cookbook_id: str, branch: str = "main") -> GraphSnapshot:
        norm = normalize_scope(scope)
        self.store.set_scope_cookbook(norm, cookbook_id)
        seed = get_cookbook_seed(cookbook_id)
        for node in seed.get("nodes", []):
            self.upsert_node(
                scope=norm,
                branch=branch,
                node_type=node["node_type"],
                slug=node["slug"],
                name=node["name"],
                summary=node.get("summary", ""),
                source_ref="cookbook-seed",
            )
        for edge in seed.get("edges", []):
            self.record_claim(
                scope=norm,
                branch=branch,
                subject_id=edge["source_id"],
                predicate=edge["predicate"],
                object_id=edge["target_id"],
                polarity=edge.get("polarity", "neutral"),
                summary=edge.get("summary", ""),
                source_ref="cookbook-seed",
            )
        self.sync_omnigraph_bundle(norm, branch=branch)
        return self.get_snapshot(norm, branch=branch)

    def get_snapshot(
        self,
        scope: str = "global",
        *,
        branch: str = "main",
        query_name: str | None = None,
    ) -> GraphSnapshot:
        norm = normalize_scope(scope)
        self._ensure_main_branch(norm)
        cookbook_id = self.store.get_scope_cookbook(norm)
        nodes = self._list_nodes(norm, branch)
        edges = self._list_edges(norm, branch)

        node_counts: dict[str, int] = {}
        for n in nodes:
            node_counts[n.node_type] = node_counts.get(n.node_type, 0) + 1
        edge_counts: dict[str, int] = {}
        for e in edges:
            edge_counts[e.predicate] = edge_counts.get(e.predicate, 0) + 1

        cookbook = get_cookbook_summary(
            cookbook_id, node_counts=node_counts, edge_counts=edge_counts
        )
        contradiction_edges = [e for e in edges if e.polarity == "contradict"]

        matched_ids: list[str] = []
        if query_name:
            matched_ids = self._evaluate_stored_query(query_name, nodes, edges)

        return GraphSnapshot(
            scope=norm,
            branch=branch,
            active_cookbook=cookbook,
            branches=self.list_branches(norm),
            nodes=nodes,
            edges=edges,
            contradiction_count=len(contradiction_edges),
            matched_node_ids=matched_ids,
            active_query_name=query_name,
        )

    def _evaluate_stored_query(
        self,
        query_name: str,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> list[str]:
        q = query_name.strip().lower()
        if "contradict" in q or "contested" in q or "risk" in q or "challenge" in q:
            hit: set[str] = set()
            for e in edges:
                if e.polarity == "contradict":
                    hit.add(e.source_id)
                    hit.add(e.target_id)
            if "decision" in q:
                for e in edges:
                    if e.target_id in hit or e.source_id in hit:
                        hit.add(e.source_id)
                        hit.add(e.target_id)
            return sorted(hit)
        if "support" in q or "evidence" in q or "emerging" in q or "goal" in q:
            hit = set()
            for e in edges:
                if e.polarity == "support":
                    hit.add(e.source_id)
                    hit.add(e.target_id)
            return sorted(hit)
        return [n.id for n in nodes]

    def sync_omnigraph_bundle(self, scope: str = "global", *, branch: str = "main") -> dict[str, Any]:
        """Write schema.pg, queries.gq, SKILL.md, and data.jsonl and sync into graph.omni."""
        norm = normalize_scope(scope)
        snap = self.get_snapshot(norm, branch=branch)
        cb = snap.active_cookbook
        bundle_dir = memory_root() / "omni" / norm.replace(":", "_")
        bundle_dir.mkdir(parents=True, exist_ok=True)
        schema_path = bundle_dir / "schema.pg"
        queries_path = bundle_dir / "queries.gq"
        skill_path = bundle_dir / "SKILL.md"
        data_path = bundle_dir / "data.jsonl"
        cookbook_marker = bundle_dir / ".cookbook_id"
        omni_path = bundle_dir / "graph.omni"

        schema_path.write_text(cb.pg_schema, encoding="utf-8")
        queries_text = "\n\n".join(q.gq_source for q in cb.stored_queries)
        queries_path.write_text(queries_text + "\n", encoding="utf-8")
        skill_path.write_text(
            _render_cookbook_bundle_skill_md(cb, norm, len(snap.nodes), len(snap.edges)),
            encoding="utf-8",
        )

        nt_map = {nt.name: nt for nt in cb.node_types}
        node_by_id = {n.id: n for n in snap.nodes}
        node_by_slug = {n.slug: n for n in snap.nodes}

        jsonl_lines: list[str] = []
        valid_nodes_by_slug: dict[str, GraphNode] = {}
        for n in snap.nodes:
            nt = nt_map.get(n.node_type)
            if nt is None:
                continue
            node_data: dict[str, Any] = {}
            for p in nt.properties:
                if p.is_key:
                    node_data[p.name] = n.slug
                elif p.name in n.properties and n.properties[p.name] is not None:
                    node_data[p.name] = n.properties[p.name]
                elif p.name in {"name", "title", "headline", "statement", "question", "nct_id"}:
                    node_data[p.name] = n.name
                elif p.name in {"summary", "implication", "playbook"} and n.summary:
                    node_data[p.name] = n.summary
                elif not p.optional:
                    node_data[p.name] = n.summary or n.name or n.node_type
            valid_nodes_by_slug[n.slug] = n
            jsonl_lines.append(json.dumps({"type": n.node_type, "data": node_data}))

        edge_defs = cb.edge_types
        for e in snap.edges:
            src_slug = e.source_id.split(":", 1)[-1]
            dst_slug = e.target_id.split(":", 1)[-1]
            src_node = node_by_id.get(e.source_id) or node_by_slug.get(src_slug)
            dst_node = node_by_id.get(e.target_id) or node_by_slug.get(dst_slug)
            if not src_node or not dst_node:
                continue
            if src_node.slug not in valid_nodes_by_slug or dst_node.slug not in valid_nodes_by_slug:
                continue
            matched_edge = next(
                (
                    ed
                    for ed in edge_defs
                    if ed.predicate == e.predicate
                    and ed.source_type == src_node.node_type
                    and ed.target_type == dst_node.node_type
                ),
                None,
            )
            if matched_edge is None:
                matched_edge = next(
                    (
                        ed
                        for ed in edge_defs
                        if ed.source_type == src_node.node_type
                        and ed.target_type == dst_node.node_type
                        and (ed.polarity == e.polarity or ed.polarity == "neutral")
                    ),
                    None,
                )
            if matched_edge is not None:
                jsonl_lines.append(
                    json.dumps(
                        {
                            "edge": matched_edge.predicate,
                            "from": src_node.slug,
                            "to": dst_node.slug,
                        }
                    )
                )

        data_path.write_text("\n".join(jsonl_lines) + ("\n" if jsonl_lines else ""), encoding="utf-8")

        cli_bin = find_omnigraph_binary("omnigraph")
        ran_cli = False
        if cli_bin is not None:
            env = resolve_omnigraph_env()
            try:
                prev_cb = (
                    cookbook_marker.read_text(encoding="utf-8").strip()
                    if cookbook_marker.is_file()
                    else ""
                )
                if prev_cb != cb.id and omni_path.exists():
                    shutil.rmtree(omni_path, ignore_errors=True)
                if not omni_path.exists():
                    init_res = subprocess.run(
                        [str(cli_bin), "init", "--schema", str(schema_path), str(omni_path)],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=15.0,
                        check=False,
                    )
                    if init_res.returncode == 0:
                        cookbook_marker.write_text(cb.id, encoding="utf-8")
                if jsonl_lines and omni_path.exists():
                    load_res = subprocess.run(
                        [
                            str(cli_bin),
                            "load",
                            "--data",
                            str(data_path),
                            "--mode",
                            "merge",
                            str(omni_path),
                        ],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=20.0,
                        check=False,
                    )
                    if load_res.returncode != 0:
                        shutil.rmtree(omni_path, ignore_errors=True)
                        subprocess.run(
                            [str(cli_bin), "init", "--schema", str(schema_path), str(omni_path)],
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=15.0,
                            check=False,
                        )
                        cookbook_marker.write_text(cb.id, encoding="utf-8")
                        load_res = subprocess.run(
                            [
                                str(cli_bin),
                                "load",
                                "--data",
                                str(data_path),
                                "--mode",
                                "merge",
                                str(omni_path),
                            ],
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=20.0,
                            check=False,
                        )
                    ran_cli = load_res.returncode == 0
                else:
                    ran_cli = omni_path.exists()
            except Exception:
                ran_cli = False

        return {
            "ok": True,
            "scope": norm,
            "bundle_dir": str(bundle_dir),
            "store_path": str(omni_path),
            "skill_path": str(skill_path),
            "nodes_exported": len(snap.nodes),
            "edges_exported": len(snap.edges),
            "omnigraph_cli_synced": ran_cli,
        }
