"""Resolve deepagents filesystem backends (builtin vs Modal)."""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeVar

from deepagents.backends import FilesystemBackend

from agent.sandbox_sync import (
    SKILLS_REMOTE_ROOT,
    WORKSPACE_REMOTE_ROOT,
    pull_tree,
    push_paths,
    push_tree,
    seed_skills,
)

logger = logging.getLogger(__name__)

_SESSION_LOCK = threading.RLock()
_ACTIVE_SESSIONS: dict[str, "SandboxHandle"] = {}
_SEED_LOCKS: dict[str, threading.Lock] = {}
_SEED_LOCKS_GUARD = threading.Lock()
# Modal sync APIs must not run on a thread that already has an asyncio loop
# (LangGraph / FastAPI). Offload to this pool so Modal's client sees a plain
# sync context and we avoid AsyncUsageWarning + event-loop stalls.
_MODAL_IO_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="sandwalk-modal",
)
_T = TypeVar("_T")


def _run_modal_blocking(fn: Callable[[], _T]) -> _T:
    """Run Modal-blocking work off the asyncio event-loop thread when needed."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return fn()
    return _MODAL_IO_EXECUTOR.submit(fn).result()


def _seed_lock_for(session_id: str | None) -> threading.Lock:
    key = (session_id or "default").strip() or "default"
    with _SEED_LOCKS_GUARD:
        lock = _SEED_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _SEED_LOCKS[key] = lock
        return lock

_DEFAULT_PIP = (
    "pandas",
    "numpy",
    "matplotlib",
    "scipy",
    "pillow",
)


@dataclass
class SandboxHandle:
    """Session-scoped backend handle with optional Modal lifecycle helpers."""

    kind: str  # "builtin" | "modal"
    backend: Any
    workspace_root: str
    skills_sources: list[str]
    session_id: str | None = None
    provider_sandbox_name: str | None = None
    modal_sandbox: Any | None = None
    seeded: bool = False
    extras: dict[str, Any] = field(default_factory=dict)

    def pull(self) -> int:
        if self.kind != "modal":
            return 0
        return pull_tree(self.backend, self.workspace_root)

    def push(self, relative_paths: list[str] | None = None) -> int:
        if self.kind != "modal":
            return 0
        if relative_paths:
            return push_paths(self.backend, self.workspace_root, relative_paths)
        return push_tree(self.backend, self.workspace_root)

    def terminate(self) -> None:
        if self.kind != "modal" or self.modal_sandbox is None:
            return
        sandbox = self.modal_sandbox
        try:
            _run_modal_blocking(sandbox.terminate)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Modal sandbox terminate failed: %s", exc)


def get_active_handle(session_id: str | None) -> SandboxHandle | None:
    if not session_id:
        return None
    with _SESSION_LOCK:
        return _ACTIVE_SESSIONS.get(session_id)


def register_handle(handle: SandboxHandle) -> None:
    if not handle.session_id:
        return
    with _SESSION_LOCK:
        _ACTIVE_SESSIONS[handle.session_id] = handle


def unregister_handle(session_id: str | None) -> None:
    if not session_id:
        return
    with _SESSION_LOCK:
        _ACTIVE_SESSIONS.pop(session_id, None)


def clear_active_handles() -> None:
    with _SESSION_LOCK:
        _ACTIVE_SESSIONS.clear()


def push_paths_for_session(
    session_id: str | None,
    local_root: str | Path,
    relative_paths: list[str],
) -> int:
    handle = get_active_handle(session_id)
    if handle is None or handle.kind != "modal":
        return 0
    # Prefer the live handle workspace; fall back to caller root.
    root = handle.workspace_root or str(local_root)
    return push_paths(handle.backend, root, relative_paths)


def sandbox_backend_from_config(config: Any) -> str:
    raw = str(getattr(config, "get", lambda _k, _d=None: "builtin")("sandbox.backend", "builtin") or "builtin")
    value = raw.strip().lower()
    return value if value in {"builtin", "modal"} else "builtin"


def parse_pip_packages(raw: Any) -> list[str]:
    if raw is None:
        return list(_DEFAULT_PIP)
    if isinstance(raw, (list, tuple)):
        items = [str(x).strip() for x in raw]
    else:
        text = str(raw).strip()
        if not text:
            return list(_DEFAULT_PIP)
        items = [part.strip() for part in text.replace(";", ",").split(",")]
    return [item for item in items if item]


def _safe_sandbox_name(session_id: str | None) -> str:
    base = (session_id or "default").strip() or "default"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:14]
    # Modal sandbox names: alphanumeric + hyphen.
    slug = re.sub(r"[^a-zA-Z0-9-]", "-", base.lower())[:24].strip("-") or "session"
    return f"sandwalk-{slug}-{digest}"


def _ensure_modal_tokens(config: Any) -> None:
    from agent.config import sync_process_env_from_config

    sync_process_env_from_config(
        config,
        only_missing=False,
        config_keys=["compute.modal_token_id", "compute.modal_token_secret"],
    )
    token_id = (os.environ.get("MODAL_TOKEN_ID") or "").strip()
    token_secret = (os.environ.get("MODAL_TOKEN_SECRET") or "").strip()
    if not token_id or not token_secret:
        raise RuntimeError(
            "Modal sandbox requires compute.modal_token_id and "
            "compute.modal_token_secret (Integrations → Modal)."
        )


def _build_modal_image(config: Any):
    from agent.sandbox_deps import require_modal_deps

    require_modal_deps()
    import modal

    packages = parse_pip_packages(config.get("sandbox.pip_packages"))
    python_version = "3.11"
    image = modal.Image.debian_slim(python_version=python_version)
    if packages:
        image = image.pip_install(*packages)
    return image


def _create_or_reuse_modal_sandbox(config: Any, *, session_id: str | None):
    return _run_modal_blocking(
        lambda: _create_or_reuse_modal_sandbox_impl(config, session_id=session_id)
    )


def _create_or_reuse_modal_sandbox_impl(config: Any, *, session_id: str | None):
    from agent.sandbox_deps import require_modal_deps

    require_modal_deps()
    import modal
    from langchain_modal import ModalSandbox

    _ensure_modal_tokens(config)
    app_name = str(config.get("sandbox.modal_app") or "sandwalk").strip() or "sandwalk"
    name = _safe_sandbox_name(session_id)
    idle_ttl = int(config.get("sandbox.idle_ttl_seconds") or 600)
    timeout = max(idle_ttl + 60, int(config.get("sandbox.timeout") or 30) * 60)
    cpu = float(config.get("sandbox.cpu_cores") or 1.0)
    ram_gb = float(config.get("sandbox.ram_gb") or 4.0)
    memory_mb = max(512, int(ram_gb * 1024))
    compute_type = str(config.get("sandbox.compute_type") or "cpu").strip().lower()
    image = _build_modal_image(config)

    app = modal.App.lookup(app_name, create_if_missing=True)
    modal_sandbox = None
    created = False
    try:
        modal_sandbox = modal.Sandbox.from_name(app_name, name)
        # Probe liveness with a cheap exec; recreate on failure.
        try:
            proc = modal_sandbox.exec("bash", "-c", "exit 0")
            proc.wait()
        except Exception:  # noqa: BLE001
            modal_sandbox = None
    except Exception:  # noqa: BLE001
        modal_sandbox = None

    if modal_sandbox is None:
        create_kwargs: dict[str, Any] = {
            "app": app,
            "name": name,
            "workdir": WORKSPACE_REMOTE_ROOT,
            "timeout": timeout,
            "idle_timeout": idle_ttl,
            "image": image,
            "cpu": cpu,
            "memory": memory_mb,
        }
        if compute_type == "gpu":
            gpu_class = str(config.get("sandbox.gpu_class") or "T4").strip() or "T4"
            create_kwargs["gpu"] = gpu_class
        modal_sandbox = modal.Sandbox.create(**create_kwargs)
        created = True

    backend = ModalSandbox(sandbox=modal_sandbox)
    _wrap_modal_backend_for_async(backend, modal_sandbox)
    return backend, modal_sandbox, name, created


def _wrap_modal_backend_for_async(backend: Any, modal_sandbox: Any) -> None:
    """Ensure langchain_modal sync methods never block an asyncio event loop."""
    original_execute = backend.execute

    def execute(command: str, *, timeout: int | None = None) -> Any:
        return _run_modal_blocking(
            lambda: original_execute(command, timeout=timeout)
        )

    backend.execute = execute  # type: ignore[method-assign]
    _patch_modal_filesystem_io(backend, modal_sandbox)


def _patch_modal_filesystem_io(backend: Any, modal_sandbox: Any) -> None:
    """Prefer Modal's non-deprecated filesystem APIs for upload/download.

    ``langchain_modal.ModalSandbox`` still uses ``Sandbox.open`` / ``FileIO.write``,
    which raise ``DeprecationError`` and can flood the ASGI event loop when seeding
    many workspace files in the background.
    """
    try:
        from deepagents.backends.protocol import (
            FileDownloadResponse,
            FileUploadResponse,
        )
    except Exception:  # noqa: BLE001
        return

    filesystem = getattr(modal_sandbox, "filesystem", None)
    if filesystem is None:
        return

    def upload_files(files: list[tuple[str, bytes]]) -> list[Any]:
        def _upload() -> list[Any]:
            responses: list[Any] = []
            for path, content in files:
                if not str(path).startswith("/"):
                    responses.append(
                        FileUploadResponse(path=path, error="invalid_path")
                    )
                    continue
                try:
                    filesystem.write_bytes(content, path)
                    responses.append(FileUploadResponse(path=path, error=None))
                except PermissionError:
                    responses.append(
                        FileUploadResponse(path=path, error="permission_denied")
                    )
                except FileNotFoundError:
                    responses.append(
                        FileUploadResponse(path=path, error="file_not_found")
                    )
                except Exception as exc:  # noqa: BLE001
                    responses.append(FileUploadResponse(path=path, error=str(exc)))
            return responses

        return _run_modal_blocking(_upload)

    def download_files(paths: list[str]) -> list[Any]:
        def _download() -> list[Any]:
            responses: list[Any] = []
            read_bytes = getattr(filesystem, "read_bytes", None)
            for path in paths:
                if not str(path).startswith("/"):
                    responses.append(
                        FileDownloadResponse(
                            path=path, content=None, error="invalid_path"
                        )
                    )
                    continue
                if not callable(read_bytes):
                    responses.append(
                        FileDownloadResponse(
                            path=path, content=None, error="read_unsupported"
                        )
                    )
                    continue
                try:
                    content = read_bytes(path)
                    if isinstance(content, memoryview):
                        content = content.tobytes()
                    elif isinstance(content, str):
                        content = content.encode()
                    responses.append(
                        FileDownloadResponse(path=path, content=content, error=None)
                    )
                except FileNotFoundError:
                    responses.append(
                        FileDownloadResponse(
                            path=path, content=None, error="file_not_found"
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    responses.append(
                        FileDownloadResponse(path=path, content=None, error=str(exc))
                    )
            return responses

        return _run_modal_blocking(_download)

    backend.upload_files = upload_files  # type: ignore[method-assign]
    backend.download_files = download_files  # type: ignore[method-assign]


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

    When ``sync_workspace`` is False, the Modal sandbox is created/reused and
    registered immediately without pushing local files (fast Start UX).
    When ``background_sync`` is True, seeding runs in a daemon thread after
    registration so callers can return ``running`` right away.
    """
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
        if sync_workspace and not existing.seeded:
            _seed_modal_handle(existing, sources)
        return existing

    backend, modal_sandbox, name, _created = _create_or_reuse_modal_sandbox(
        config, session_id=session_id
    )
    handle = SandboxHandle(
        kind="modal",
        backend=backend,
        workspace_root=workspace_root,
        skills_sources=[f"{SKILLS_REMOTE_ROOT}/"],
        session_id=session_id,
        provider_sandbox_name=name,
        modal_sandbox=modal_sandbox,
        seeded=False,
    )
    # Register before sync so status APIs can report "running" immediately.
    register_handle(handle)

    def _run_seed() -> None:
        try:
            backend.execute(
                f"mkdir -p {WORKSPACE_REMOTE_ROOT} {SKILLS_REMOTE_ROOT}",
                timeout=60,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Modal mkdir failed: %s", exc)
        _seed_modal_handle(handle, sources)

    if not sync_workspace:
        return handle
    if background_sync:
        threading.Thread(
            target=_run_seed,
            name=f"modal-seed-{session_id or 'default'}",
            daemon=True,
        ).start()
        return handle
    _run_seed()
    return handle


def _seed_modal_handle(handle: SandboxHandle, sources: list[str]) -> None:
    if handle.kind != "modal":
        return
    with _seed_lock_for(handle.session_id):
        if handle.seeded:
            return
        try:
            push_tree(handle.backend, handle.workspace_root)
            if sources:
                seed_skills(handle.backend, sources)
        except Exception as exc:  # noqa: BLE001
            # Mark seeded anyway so a failed/partial sync does not retry forever
            # and keep hammering Modal (or the local event loop).
            logger.warning("Modal seed sync failed: %s", exc)
        finally:
            handle.seeded = True
