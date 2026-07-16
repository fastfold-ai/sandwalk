"""Resolve the deepagents backend for a session (builtin vs Modal).

``_create_or_reuse_modal_sandbox`` and ``_seed_modal_workspace`` are looked up
via a lazy import of the package (rather than at module scope) so tests that
monkeypatch ``agent.sandbox_backend.<name>`` are honored here too.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from deepagents.backends import FilesystemBackend

from agent.sandbox_backend.handle import SandboxHandle, get_active_handle, register_handle
from agent.sandbox_backend.provisioning import sandbox_backend_from_config
from agent.sandbox_backend.skills_route import _compose_modal_with_local_skills


def resolve_deepagents_backend(
    config: Any,
    *,
    session_id: str | None,
    workspace_root: str,
    skill_source_dirs: list[str] | None = None,
    backend_override: str | None = None,
    sync_workspace: bool = True,
    background_sync: bool = False,
) -> SandboxHandle:
    """Return the deepagents backend for the current config + session.

    Modal mode uses CompositeBackend: Modal for ``/workspace`` + ``execute``,
    local FilesystemBackend for ``/skills/`` (no skills upload).

    Workspace sync never uploads skills. When ``background_sync`` is True (or
    when reusing an unseeded handle), workspace push runs in a daemon thread so
    Start / first message are not blocked.
    """
    from agent.sandbox_backend import _create_or_reuse_modal_sandbox, _seed_modal_workspace

    override = str(backend_override or "").strip().lower()
    if override in {"builtin", "modal"}:
        kind = override
    else:
        kind = sandbox_backend_from_config(config)
    sources = list(skill_source_dirs or [])
    workspace_root = str(Path(workspace_root).expanduser().resolve())

    if kind != "modal":
        backend = FilesystemBackend(root_dir=workspace_root, virtual_mode=False)
        handle = SandboxHandle(
            kind="builtin",
            backend=backend,
            workspace_root=workspace_root,
            skills_sources=sources,
            session_id=session_id,
        )
        register_handle(handle)
        return handle

    existing = get_active_handle(session_id)
    if (
        existing is not None
        and existing.kind == "modal"
        and existing.workspace_root == workspace_root
    ):
        # Refresh skills route sources if callers pass new dirs (specialist scope).
        if sources and existing.extras.get("skills_root") is None:
            composed, skill_paths, skills_root = _compose_modal_with_local_skills(
                getattr(existing.backend, "default", existing.backend),
                sources,
            )
            if skills_root is not None:
                existing.backend = composed
                existing.skills_sources = skill_paths
                existing.extras["skills_root"] = str(skills_root)
        if sync_workspace and not existing.seeded:
            # Never block the agent on workspace sync.
            threading.Thread(
                target=_seed_modal_workspace,
                args=(existing,),
                name=f"modal-seed-{session_id or 'default'}",
                daemon=True,
            ).start()
        return existing

    modal_backend, modal_sandbox, name, _created = _create_or_reuse_modal_sandbox(
        config, session_id=session_id
    )
    backend, skill_paths, skills_root = _compose_modal_with_local_skills(
        modal_backend, sources
    )
    handle = SandboxHandle(
        kind="modal",
        backend=backend,
        workspace_root=workspace_root,
        skills_sources=skill_paths,
        session_id=session_id,
        provider_sandbox_name=name,
        modal_sandbox=modal_sandbox,
        seeded=False,
        extras={"skills_root": str(skills_root)} if skills_root else {},
    )
    # Register before sync so status APIs can report "running" immediately.
    register_handle(handle)

    if not sync_workspace:
        return handle

    # Workspace-only sync (no skills upload). Prefer background so Start and
    # first message stay fast; empty workspaces finish almost instantly.
    if background_sync:
        threading.Thread(
            target=_seed_modal_workspace,
            args=(handle,),
            name=f"modal-seed-{session_id or 'default'}",
            daemon=True,
        ).start()
        return handle

    # Synchronous path still never uploads skills — only /workspace.
    _seed_modal_workspace(handle)
    return handle
