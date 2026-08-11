"""Resolve deepagents filesystem backends (builtin vs Modal).

Modal is the compute runtime (execute + /workspace). Skills stay on the host via
CompositeBackend routing — they are never uploaded into Modal.

Split across sibling modules (handle registry, provisioning, Modal image/
lifecycle, filesystem I/O patching, skills routing, workspace seeding, and
backend resolution) to stay under the file-length cap. A few call sites
(``_build_modal_image``, ``resolve_deepagents_backend``) look up sibling
names via a lazy ``from agent.sandbox_backend import ...`` *inside* their
function bodies instead of at module scope, so tests that monkeypatch
``agent.sandbox_backend.<name>`` (e.g. ``parse_pip_packages``,
``_create_or_reuse_modal_sandbox``, ``_seed_modal_workspace``) still take
effect even though the implementation now lives in a submodule.
"""

from __future__ import annotations

from agent.sandbox_backend.handle import (
    SandboxHandle,
    clear_active_handles,
    get_active_handle,
    push_paths_for_session,
    register_handle,
    unregister_handle,
)
from agent.sandbox_backend.image import _build_modal_image
from agent.sandbox_backend.lifecycle import (
    _create_or_reuse_modal_sandbox,
    _create_or_reuse_modal_sandbox_impl,
    _wrap_modal_backend_for_async,
)
from agent.sandbox_backend.provisioning import (
    _ensure_modal_tokens,
    _safe_sandbox_name,
    _seed_lock_for,
    parse_pip_packages,
    sandbox_backend_from_config,
)
from agent.sandbox_backend.resolve import resolve_deepagents_backend
from agent.sandbox_backend.runtime import _run_modal_blocking
from agent.sandbox_backend.seed import _seed_modal_workspace, wait_until_seeded
from agent.sandbox_backend.skills_route import (
    _command_targets_skills,
    _compose_modal_with_local_skills,
    _skills_filesystem_root,
    _wrap_composite_execute_for_skills,
)
from agent.sandbox_backend.workspace_route import (
    workspace_relative_tool_path,
    wrap_backend_for_host_workspace,
)

__all__ = [
    "SandboxHandle",
    "_build_modal_image",
    "_command_targets_skills",
    "_compose_modal_with_local_skills",
    "_create_or_reuse_modal_sandbox",
    "_create_or_reuse_modal_sandbox_impl",
    "_ensure_modal_tokens",
    "_run_modal_blocking",
    "_safe_sandbox_name",
    "_seed_lock_for",
    "_seed_modal_workspace",
    "_skills_filesystem_root",
    "_wrap_composite_execute_for_skills",
    "_wrap_modal_backend_for_async",
    "clear_active_handles",
    "get_active_handle",
    "parse_pip_packages",
    "push_paths_for_session",
    "register_handle",
    "resolve_deepagents_backend",
    "sandbox_backend_from_config",
    "unregister_handle",
    "wait_until_seeded",
    "wrap_backend_for_host_workspace",
    "workspace_relative_tool_path",
]
