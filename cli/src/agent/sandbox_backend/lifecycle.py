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


def _create_or_reuse_modal_sandbox_impl(config: Any, *, session_id: str | None):
    from agent.sandbox_backend.image import _build_modal_image
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
