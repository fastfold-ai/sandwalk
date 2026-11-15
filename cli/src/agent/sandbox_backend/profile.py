"""Helpers for Modal sandbox compute profile / base image selection."""

from __future__ import annotations

from typing import Any

DEFAULT_CPU_IMAGE = "python:3.12-slim"
DEFAULT_GPU_IMAGE = "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime"


# Modal's ceiling for one sandbox. Past this it recommends filesystem snapshots.
MODAL_MAX_LIFETIME_SECONDS = 24 * 60 * 60
DEFAULT_IDLE_TIMEOUT_SECONDS = 600


def _int_or(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def sandbox_idle_timeout_seconds(config: Any) -> int:
    """Seconds without a running command before Modal stops the sandbox."""
    value = _int_or(config.get("sandbox.idle_ttl_seconds"), 0)
    if value <= 0:
        value = DEFAULT_IDLE_TIMEOUT_SECONDS
    return min(max(value, 60), MODAL_MAX_LIFETIME_SECONDS)


def sandbox_max_lifetime_seconds(config: Any) -> int:
    """Seconds after creation when Modal stops the sandbox, busy or not.

    ``sandbox.max_lifetime_seconds`` is the setting. Before it existed the
    limit was derived from ``sandbox.timeout`` (the code-execution timeout)
    read as minutes; that stays the fallback so nothing changes for a config
    that never set the new key. Always longer than the idle timeout, and never
    past Modal's 24 hours.
    """
    idle = sandbox_idle_timeout_seconds(config)
    lifetime = _int_or(config.get("sandbox.max_lifetime_seconds"), 0)
    if lifetime <= 0:
        lifetime = (_int_or(config.get("sandbox.timeout"), 0) or 30) * 60
    return min(max(lifetime, idle + 60), MODAL_MAX_LIFETIME_SECONDS)


def sandbox_compute_type(config: Any) -> str:
    value = str(config.get("sandbox.compute_type") or "cpu").strip().lower()
    return value if value in {"cpu", "gpu"} else "cpu"


def sandbox_gpu_class(config: Any) -> str:
    return str(config.get("sandbox.gpu_class") or "T4").strip() or "T4"


def sandbox_image_ref(config: Any, *, compute_type: str | None = None) -> str:
    kind = (compute_type or sandbox_compute_type(config)).strip().lower()
    if kind == "gpu":
        return (
            str(config.get("sandbox.gpu_image") or DEFAULT_GPU_IMAGE).strip()
            or DEFAULT_GPU_IMAGE
        )
    return (
        str(config.get("sandbox.cpu_image") or DEFAULT_CPU_IMAGE).strip()
        or DEFAULT_CPU_IMAGE
    )


def sandbox_profile_fingerprint(config: Any) -> str:
    compute_type = sandbox_compute_type(config)
    cpu = float(config.get("sandbox.cpu_cores") or 2.0)
    ram_gb = float(config.get("sandbox.ram_gb") or 8.0)
    gpu = sandbox_gpu_class(config) if compute_type == "gpu" else "-"
    image = sandbox_image_ref(config, compute_type=compute_type)
    return f"{compute_type}|{gpu}|{cpu}|{ram_gb}|{image}"
