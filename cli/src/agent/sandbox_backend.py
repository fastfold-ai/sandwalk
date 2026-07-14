"""Resolve deepagents filesystem backends (builtin vs Modal).

Modal is the compute runtime (execute + /workspace). Skills stay on the host via
CompositeBackend routing — they are never uploaded into Modal.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeVar

from deepagents.backends import CompositeBackend, FilesystemBackend

from agent.sandbox_sync import (
    SKILLS_REMOTE_ROOT,
    WORKSPACE_REMOTE_ROOT,
    pull_tree,
    push_paths,
    push_tree,
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

_SKILLS_EXECUTE_HINT = (
    "Skill scripts are not available inside the Modal sandbox. "
    "Use the shell_run tool with the absolute host path to the skill script "
    "(from the Skills listing), e.g. "
    "`python3 /path/to/skills/<name>/scripts/<script>.py ...`. "
    "Modal `execute` is only for /workspace compute."
)


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
        # Prefer the Modal default when wrapped in CompositeBackend.
        target = getattr(self.backend, "default", self.backend)
        return pull_tree(target, self.workspace_root)

    def push(self, relative_paths: list[str] | None = None) -> int:
        if self.kind != "modal":
            return 0
        target = getattr(self.backend, "default", self.backend)
        if relative_paths:
            return push_paths(target, self.workspace_root, relative_paths)
        return push_tree(target, self.workspace_root)

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
    target = getattr(handle.backend, "default", handle.backend)
    return push_paths(target, root, relative_paths)


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


def _build_modal_image(config: Any, *, compute_type: str = "cpu"):
    from agent.sandbox_deps import require_modal_deps

    require_modal_deps()
    import modal

    packages = parse_pip_packages(config.get("sandbox.pip_packages"))
    python_version = "3.11"
    is_gpu = str(compute_type).strip().lower() == "gpu"
    image_key = "sandbox.gpu_image" if is_gpu else "sandbox.cpu_image"
    default_ref = (
        "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime"
        if is_gpu
        else "python:3.12-slim"
    )
    ref = str(config.get(image_key) or default_ref).strip() or default_ref
    # debian_slim is Modal's helper (Image.debian_slim), not a Docker Hub tag.
    if ref in {"debian_slim", "debian-slim"}:
        image = modal.Image.debian_slim(python_version=python_version)
    else:
        image = modal.Image.from_registry(ref)
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
    cpu = float(config.get("sandbox.cpu_cores") or 2.0)
    ram_gb = float(config.get("sandbox.ram_gb") or 8.0)
    memory_mb = max(512, int(ram_gb * 1024))
    compute_type = str(config.get("sandbox.compute_type") or "cpu").strip().lower()
    image = _build_modal_image(config, compute_type=compute_type)

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


def _skills_filesystem_root(sources: list[str]) -> Path | None:
    """Build a single host root for CompositeBackend ``/skills/`` routing.

    Later sources override earlier ones on name collision (bundled -> npx -> global).
    """
    existing: list[Path] = []
    for raw in sources:
        path = Path(str(raw)).expanduser().resolve()
        if path.is_dir():
            existing.append(path)
    if not existing:
        return None
    if len(existing) == 1:
        return existing[0]

    staging = Path(tempfile.mkdtemp(prefix="sandwalk-skills-route-"))
    for src in existing:
        try:
            children = list(src.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            dest = staging / child.name
            if dest.exists() or dest.is_symlink():
                if dest.is_symlink() or dest.is_file():
                    dest.unlink(missing_ok=True)
                elif dest.is_dir():
                    shutil.rmtree(dest, ignore_errors=True)
            try:
                dest.symlink_to(child, target_is_directory=True)
            except OSError:
                try:
                    shutil.copytree(child, dest, dirs_exist_ok=True)
                except OSError as exc:
                    logger.warning("Could not stage skill %s: %s", child, exc)
    return staging


def _command_targets_skills(command: str) -> bool:
    text = str(command or "")
    if f"{SKILLS_REMOTE_ROOT}/" in text:
        return True
    # Bare relative forms agents sometimes try.
    return bool(re.search(r"(^|[\s'\"])skills/", text))


def _wrap_composite_execute_for_skills(backend: CompositeBackend, skills_root: Path) -> None:
    """Reject Modal execute for skill paths; optionally rewrite + run on host.

    Prefer host ``shell_run`` (prompted). If the model still uses ``execute`` with
    a ``/skills/...`` path, rewrite to the host skills root and run locally so
    FastFold API scripts keep working with host env/secrets.
    """
    from deepagents.backends.protocol import ExecuteResponse

    original_execute = backend.execute
    host_prefix = str(skills_root.resolve()).rstrip("/") + "/"

    def execute(command: str, *, timeout: int | None = None) -> Any:
        if not _command_targets_skills(command):
            if timeout is not None:
                return original_execute(command, timeout=timeout)
            return original_execute(command)

        host_cmd = str(command).replace(f"{SKILLS_REMOTE_ROOT}/", host_prefix)
        host_cmd = re.sub(r"(^|[\s'\"])skills/", rf"\1{host_prefix}", host_cmd)
        try:
            completed = subprocess.run(
                host_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout or 600,
                check=False,
            )
            output = (completed.stdout or "") + (completed.stderr or "")
            return ExecuteResponse(output=output, exit_code=completed.returncode)
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + (exc.stderr or "")
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            return ExecuteResponse(
                output=(output or "") + f"\nTimed out. {_SKILLS_EXECUTE_HINT}",
                exit_code=124,
            )
        except Exception as exc:  # noqa: BLE001
            return ExecuteResponse(
                output=f"{exc}\n{_SKILLS_EXECUTE_HINT}",
                exit_code=1,
            )

    backend.execute = execute  # type: ignore[method-assign]


def _compose_modal_with_local_skills(
    modal_backend: Any,
    skill_source_dirs: list[str],
) -> tuple[Any, list[str], Path | None]:
    """Wrap Modal with a local ``/skills/`` FilesystemBackend route."""
    skills_root = _skills_filesystem_root(skill_source_dirs)
    if skills_root is None:
        return modal_backend, [], None

    skills_fs = FilesystemBackend(root_dir=str(skills_root), virtual_mode=True)
    composite = CompositeBackend(
        default=modal_backend,
        routes={f"{SKILLS_REMOTE_ROOT}/": skills_fs},
    )
    _wrap_composite_execute_for_skills(composite, skills_root)
    return composite, [f"{SKILLS_REMOTE_ROOT}/"], skills_root


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


def _seed_modal_workspace(handle: SandboxHandle) -> None:
    """Push local session workspace into Modal. Never uploads skills."""
    if handle.kind != "modal":
        return
    with _seed_lock_for(handle.session_id):
        if handle.seeded:
            return
        target = getattr(handle.backend, "default", handle.backend)
        try:
            try:
                target.execute(
                    f"mkdir -p {WORKSPACE_REMOTE_ROOT}",
                    timeout=60,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Modal mkdir failed: %s", exc)
            push_tree(target, handle.workspace_root)
        except Exception as exc:  # noqa: BLE001
            # Mark seeded anyway so a failed/partial sync does not retry forever.
            logger.warning("Modal workspace sync failed: %s", exc)
        finally:
            handle.seeded = True


def wait_until_seeded(
    handle: SandboxHandle,
    *,
    timeout: float = 120.0,
    poll_interval: float = 0.25,
) -> bool:
    """Block until Modal workspace seed finishes (or ``timeout`` elapses).

    Returns True when ``handle.seeded`` is True. Built-in handles always return
    True immediately. Used by the agent runner so the first Modal ``execute``
    sees a synced ``/workspace``.
    """
    if handle.kind != "modal":
        return True
    if handle.seeded:
        return True
    deadline = time.monotonic() + max(0.0, float(timeout))
    while not handle.seeded:
        if time.monotonic() >= deadline:
            logger.warning(
                "Timed out waiting for Modal workspace seed (session=%s)",
                handle.session_id,
            )
            return False
        time.sleep(max(0.05, float(poll_interval)))
    return True
