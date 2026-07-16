"""Helper logic for `sandwalk fork`: trajectory reconstruction and file restore."""

import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from cli.agents_api import (
    _agents_api_get_json,
    _agents_api_request_json,
    _download_binary,
    _parse_unix_timestamp,
    _safe_workspace_relative_path,
)
from cli.app import spinner


def _fork_build_trajectory(messages: list, thread: dict, resolved_share_id: str, title: str):
    """Reconstruct a local Trajectory from shared-session messages."""
    from agent.trajectory import Trajectory, Turn

    turns: list[Turn] = []
    pending_query = ""
    pending_query_ts: float | None = None
    assistant_parts: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "").strip().lower()
        content = str(message.get("content") or "").strip()
        created_at = _parse_unix_timestamp(message.get("created_at"))
        if role == "user":
            if pending_query:
                turns.append(
                    Turn(
                        query=pending_query,
                        answer="\n\n".join(assistant_parts).strip(),
                        timestamp=pending_query_ts or created_at,
                    )
                )
            pending_query = content
            pending_query_ts = created_at
            assistant_parts = []
            continue
        if role == "assistant" and pending_query and content:
            assistant_parts.append(content)
    if pending_query:
        turns.append(
            Turn(
                query=pending_query,
                answer="\n\n".join(assistant_parts).strip(),
                timestamp=pending_query_ts or time.time(),
            )
        )

    session_id = str(uuid4())[:8]
    trajectory = Trajectory(session_id=session_id, title=title)
    trajectory.turns = turns
    if turns:
        trajectory.created_at = turns[0].timestamp
        trajectory.updated_at = turns[-1].timestamp
    trajectory.model = str(
        (thread.get("metadata") or {}).get("inspect_base_model_key")
        if isinstance(thread.get("metadata"), dict)
        else ""
    ).strip() or "cloud-shared-session"
    trajectory.usage_data = {
        "imported_from_share_id": resolved_share_id,
        "imported_from_thread_id": str(thread.get("id") or "").strip(),
        "imported_at": datetime.now(UTC).isoformat(),
        "messages_count": len(messages),
        "turns_count": len(turns),
    }
    # Treat the fork as freshly added so CLI + Web UI sort it to the top.
    trajectory.updated_at = time.time()
    trajectory.save()
    return trajectory, session_id


def _fork_restore_files(
    base_url: str,
    encoded_share_id: str,
    headers: dict,
    cfg,
    resolved_share_id: str,
    session_id: str,
    console,
) -> tuple[int, int, int, Path]:
    """Download shared files and mirror them into the session workspace."""
    with spinner("Loading shared file manifest..."):
        files_payload = _agents_api_get_json(base_url, f"/shares/{encoded_share_id}/files", headers=headers)
    listed_files = files_payload.get("data") if isinstance(files_payload.get("data"), list) else []
    share_files_count = len(listed_files)
    unique_parent_dirs: set[str] = set()
    output_root = Path(str(cfg.get("sandbox.output_dir") or Path.cwd() / "outputs")).expanduser().resolve()
    restored_root = output_root / "shared_forks" / resolved_share_id
    restored_files = 0
    with spinner(f"Downloading {share_files_count} shared files..."):
        for row in listed_files:
            if not isinstance(row, dict):
                continue
            rel_path = _safe_workspace_relative_path(str(row.get("path") or ""))
            if rel_path is None:
                continue
            parent = str(rel_path.parent).strip()
            if parent and parent != ".":
                unique_parent_dirs.add(parent)
            encoded_path = quote(str(rel_path).replace("\\", "/"), safe="")
            download_payload = _agents_api_get_json(
                base_url,
                f"/shares/{encoded_share_id}/files/download?path={encoded_path}",
                headers=headers,
            )
            signed_url = str(download_payload.get("url") or "").strip()
            if not signed_url:
                continue
            content = _download_binary(signed_url)
            target_path = restored_root / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(content)
            restored_files += 1
    share_folders_count = len(unique_parent_dirs)

    # Mirror restored files into the canonical per-session workspace so
    # the local Agents UI file tree can list them after sync/resume.
    try:
        import shutil

        from agent.config import CONFIG_DIR

        workspace_root = (CONFIG_DIR / "workspaces" / session_id).resolve()
        workspace_root.mkdir(parents=True, exist_ok=True)
        for child in restored_root.iterdir():
            destination = workspace_root / child.name
            if child.is_dir():
                shutil.copytree(child, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(child, destination)
        console.print(f"  [dim]Session workspace:[/dim] {workspace_root}")
    except Exception:
        pass

    return share_files_count, share_folders_count, restored_files, restored_root


def _fork_track_analytics(base_url: str, encoded_share_id: str, headers: dict) -> int | None:
    """Best-effort fork-count analytics; never raises."""
    try:
        tracked = _agents_api_request_json(
            base_url,
            f"/shares/{encoded_share_id}/fork/local",
            headers=headers,
            method="POST",
            timeout=12.0,
        )
        raw_count = tracked.get("fork_count")
        if raw_count is not None:
            return max(0, int(raw_count))
    except Exception:
        pass
    return None
