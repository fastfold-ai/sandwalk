"""Helpers for Modal sandbox compute profile / base image selection."""

from __future__ import annotations

from typing import Any

DEFAULT_CPU_IMAGE = "python:3.12-slim"
DEFAULT_GPU_IMAGE = "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime"


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
