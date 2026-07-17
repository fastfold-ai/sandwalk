"""Create-or-reuse the per-session Modal sandbox and wrap it for async safety."""

from __future__ import annotations

from typing import Any

from agent.sandbox_backend.filesystem_io import _patch_modal_filesystem_io
from agent.sandbox_backend.provisioning import _ensure_modal_tokens, _safe_sandbox_name
from agent.sandbox_backend.runtime import _run_modal_blocking
from agent.sandbox_sync import WORKSPACE_REMOTE_ROOT


def _create_or_reuse_modal_sandbox(config: Any, *, session_id: str | None):
    return _run_modal_blocking(
        lambda: _create_or_reuse_modal_sandbox_impl(config, session_id=session_id)
    )


def _existing_sandbox_matches_profile(modal_sandbox: Any, *, compute_type: str) -> bool:
    """Return False when a reused sandbox cannot satisfy the requested profile.

    Modal reuses sandboxes by name across starts. Switching CPU → GPU (or to a
    CUDA image) must recreate; otherwise the container stays on the old
    python:3.12-slim image without nvidia-smi / CUDA.
    """
    try:
        if compute_type == "gpu":
            proc = modal_sandbox.exec(
                "bash",
                "-c",
                "command -v nvidia-smi >/dev/null 2>&1 || test -e /dev/nvidia0",
            )
            proc.wait()
            return int(getattr(proc, "returncode", 1) or 0) == 0
        proc = modal_sandbox.exec("bash", "-c", "exit 0")
        proc.wait()
        return True
    except Exception:  # noqa: BLE001
        return False


def _create_or_reuse_modal_sandbox_impl(config: Any, *, session_id: str | None):
    from agent.sandbox_backend.image import _build_modal_image
    from agent.sandbox_backend.profile import (
        sandbox_compute_type,
        sandbox_gpu_class,
        sandbox_profile_fingerprint,
    )
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
    compute_type = sandbox_compute_type(config)
    image = _build_modal_image(config, compute_type=compute_type)
    fingerprint = sandbox_profile_fingerprint(config)

    app = modal.App.lookup(app_name, create_if_missing=True)
    modal_sandbox = None
    try:
        modal_sandbox = modal.Sandbox.from_name(app_name, name)
        if not _existing_sandbox_matches_profile(
            modal_sandbox, compute_type=compute_type
        ):
            try:
                modal_sandbox.terminate()
            except Exception:  # noqa: BLE001
                pass
            modal_sandbox = None
    except Exception:  # noqa: BLE001
        modal_sandbox = None

    created = False
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
            create_kwargs["gpu"] = sandbox_gpu_class(config)
        modal_sandbox = modal.Sandbox.create(**create_kwargs)
        created = True

    backend = ModalSandbox(sandbox=modal_sandbox)
    _wrap_modal_backend_for_async(backend, modal_sandbox)
    # Fingerprint is attached by resolve() onto SandboxHandle.extras.
    backend._sandwalk_profile_fingerprint = fingerprint  # type: ignore[attr-defined]
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
