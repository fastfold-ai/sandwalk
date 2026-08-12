"""Spawn agent-server sessions for a matrix (sequential model latch).

Each batch run creates a Sandwalk **Project** and attaches every chat session
to it so the UI can browse/filter by batch.
"""

from __future__ import annotations

import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sandwalk_bench.pack import expand_matrix, load_pack
from sandwalk_bench.paths import FIXTURES_DIR, PKG_ROOT
from sandwalk_bench.schema import MatrixCell, Pack


def _req(
    base: str,
    key: str,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> Any:
    data = None if body is None else json.dumps(body).encode()
    r = Request(
        base.rstrip("/") + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(r, timeout=60) as resp:  # noqa: S310 — local agent-server
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except HTTPError as e:
        err = e.read().decode()
        raise RuntimeError(f"{method} {path} -> {e.code}: {err}") from e


def resolve_fixture_dir(pack: Pack, cell: MatrixCell) -> Path | None:
    q = cell.question
    pack_dir = Path(pack.path).parent if pack.path else PKG_ROOT / "packs"
    rel = None
    if q and q.fixture_dir:
        rel = q.fixture_dir
    elif pack.inputs_dir:
        rel = pack.inputs_dir
    if not rel:
        return None
    p = Path(rel)
    if not p.is_absolute():
        p = (pack_dir / rel).resolve()
    return p if p.is_dir() else None


def copy_cell_inputs(pack: Pack, cell: MatrixCell, workspace: Path) -> None:
    """Copy question fixtures into the session workspace."""
    q = cell.question
    if not q:
        return
    fixture = resolve_fixture_dir(pack, cell)
    if fixture is None:
        return
    # Bix adapted: fixture has data/; sandwalk pack: flat inputs
    data_src = fixture / "data"
    if data_src.is_dir():
        dest = workspace / "data"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(data_src, dest)
        return
    # Treat fixture dir as inputs/
    dest = workspace / "inputs"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(fixture, dest)


def default_project_name(pack_id: str, matrix_name: str, when: datetime | None = None) -> str:
    ts = (when or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H%M")
    return f"bench · {pack_id} · {matrix_name} · {ts}"


def build_project_description(
    *,
    pack: Pack,
    matrix_name: str,
    cells: list[MatrixCell],
) -> str:
    models = sorted({f"{c.provider}:{c.model_id}" for c in cells})
    question_count = len({c.question_id for c in cells})
    lines = [
        "sandwalk-bench batch",
        f"pack: {pack.id} v{pack.version}",
        f"matrix: {matrix_name}",
        f"sessions: {len(cells)}",
        f"questions: {question_count}",
        f"models: {', '.join(models)}",
    ]
    if pack.description:
        lines.append("")
        lines.append(pack.description.strip()[:500])
    return "\n".join(lines)


def build_project_agent_context(pack: Pack, matrix_name: str) -> str:
    """Optional project.agent_context.

    Keep empty by default so sessions read like normal chats — the agent
    should not be told it is inside a benchmark harness.
    """
    del pack, matrix_name
    return ""


def bench_kickoff_message(*, question_id: str) -> str:
    """Short chat kickoff. Full prompt is only written to BENCH_PROMPT.md."""
    qid = (question_id or "").strip() or "unknown"
    return (
        f"Complete benchmark question `{qid}`.\n"
        "Read `BENCH_PROMPT.md` in the workspace and follow it exactly."
    )


def spawn_matrix(
    *,
    pack_path: str | Path,
    matrix_name: str,
    base_url: str = "http://127.0.0.1:8787",
    api_key: str,
    latch_delay_s: float = 2.0,
    dry_run: bool = False,
    project_name: str | None = None,
    project_description: str | None = None,
    project_id: str | None = None,
    no_project: bool = False,
) -> dict[str, Any]:
    """Spawn a matrix of sessions.

    Returns ``{ "project": {...}|null, "sessions": [...] }``.
    By default creates one Project per batch and sets ``projectId`` on each session.
    """
    pack = load_pack(pack_path)
    cells = expand_matrix(pack, matrix_name)
    name = project_name or default_project_name(pack.id, matrix_name)
    description = project_description or build_project_description(
        pack=pack, matrix_name=matrix_name, cells=cells
    )
    agent_context = build_project_agent_context(pack, matrix_name)

    if dry_run:
        planned: dict[str, Any] | None = None
        if not no_project:
            planned = {
                "id": project_id or "(new)",
                "name": name,
                "description": description,
            }
            if agent_context.strip():
                planned["agentContext"] = agent_context
        return {
            "project": planned,
            "sessions": [
                {
                    "title": c.title,
                    "model": f"{c.provider}:{c.model_id}",
                    "question_id": c.question_id,
                    "prompt_chars": len(c.prompt),
                }
                for c in cells
            ],
        }

    runtime = _req(base_url, api_key, "GET", "/v1/settings/runtime")
    orig = (runtime["provider"], runtime["model"])
    project: dict[str, Any] | None = None
    pid = project_id

    if not no_project:
        if pid:
            project = _req(base_url, api_key, "GET", f"/v1/projects/{pid}")
        else:
            body: dict[str, Any] = {
                "name": name,
                "description": description,
                "icon": "sparkles",
                "color": "purple",
                "pinned": True,
            }
            if agent_context.strip():
                body["agentContext"] = agent_context
            project = _req(
                base_url,
                api_key,
                "POST",
                "/v1/projects",
                body,
            )
            pid = project["id"]

    sessions: list[dict[str, Any]] = []
    try:
        for cell in cells:
            _req(
                base_url,
                api_key,
                "PATCH",
                "/v1/settings/runtime",
                {"provider": cell.provider, "model": cell.model_id},
            )
            time.sleep(0.3)
            create_body: dict[str, Any] = {"title": cell.title}
            if pid:
                create_body["projectId"] = pid
            sess = _req(base_url, api_key, "POST", "/v1/sessions", create_body)
            sid = sess["id"]
            ws = Path(sess.get("workspacePath") or "")
            if ws:
                ws.mkdir(parents=True, exist_ok=True)
                copy_cell_inputs(pack, cell, ws)
                (ws / "BENCH_PROMPT.md").write_text(cell.prompt, encoding="utf-8")
            run = _req(
                base_url,
                api_key,
                "POST",
                f"/v1/sessions/{sid}/messages",
                {"content": bench_kickoff_message(question_id=cell.question_id)},
            )
            status = "idle"
            for _ in range(40):
                s = _req(base_url, api_key, "GET", f"/v1/sessions/{sid}")
                status = s["status"]
                if status in ("running", "awaiting_approval", "error", "interrupted"):
                    break
                time.sleep(0.25)
            time.sleep(latch_delay_s)
            sessions.append(
                {
                    "title": cell.title,
                    "question_id": cell.question_id,
                    "model": f"{cell.provider}:{cell.model_id}",
                    "sessionId": sid,
                    "runId": run["runId"],
                    "status": status,
                    "projectId": pid,
                    "workspace": str(ws),
                }
            )
    finally:
        _req(
            base_url,
            api_key,
            "PATCH",
            "/v1/settings/runtime",
            {"provider": orig[0], "model": orig[1]},
        )
    return {"project": project, "sessions": sessions}


def default_sandwalk_inputs() -> Path:
    return FIXTURES_DIR / "sandwalk_inputs"
