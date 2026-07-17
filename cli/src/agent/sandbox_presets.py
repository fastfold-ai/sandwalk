"""Modal compute presets — keep aligned with local-web ``sandbox-presets.ts``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agent.config import Config
from agent.sandbox_manage import get_sandbox_backend, set_sandbox_backend


@dataclass(frozen=True)
class CpuPreset:
    id: str
    cpu: float
    ram: float
    label: str
    short_label: str


@dataclass(frozen=True)
class GpuPreset:
    gpu: str
    vram: float
    cpu: float
    ram: float
    label: str
    short_label: str


CPU_PRESETS: list[CpuPreset] = [
    CpuPreset("2c8g", 2.0, 8.0, "2 CPU cores · 8 GB RAM", "2 CPU · 8 GB"),
    CpuPreset("4c16g", 4.0, 16.0, "4 CPU cores · 16 GB RAM", "4 CPU · 16 GB"),
    CpuPreset("8c32g", 8.0, 32.0, "8 CPU cores · 32 GB RAM", "8 CPU · 32 GB"),
    CpuPreset("16c64g", 16.0, 64.0, "16 CPU cores · 64 GB RAM", "16 CPU · 64 GB"),
]

GPU_PRESETS: list[GpuPreset] = [
    GpuPreset("T4", 16.0, 8.0, 32.0, "T4 · 16 GB VRAM · 8 CPU · 32 GB RAM", "T4 · 16GB"),
    GpuPreset("L4", 24.0, 8.0, 32.0, "L4 · 24 GB VRAM · 8 CPU · 32 GB RAM", "L4 · 24GB"),
    GpuPreset("A10", 24.0, 8.0, 32.0, "A10 · 24 GB VRAM · 8 CPU · 32 GB RAM", "A10 · 24GB"),
    GpuPreset("L40S", 48.0, 16.0, 64.0, "L40S · 48 GB VRAM · 16 CPU · 64 GB RAM", "L40S · 48GB"),
    GpuPreset("A100", 80.0, 16.0, 64.0, "A100 · 80 GB VRAM · 16 CPU · 64 GB RAM", "A100 · 80GB"),
    GpuPreset(
        "RTX-PRO-6000",
        48.0,
        16.0,
        64.0,
        "RTX-PRO-6000 · 48 GB VRAM · 16 CPU · 64 GB RAM",
        "RTX-PRO-6000 · 48GB",
    ),
    GpuPreset("H100", 80.0, 16.0, 64.0, "H100 · 80 GB VRAM · 16 CPU · 64 GB RAM", "H100 · 80GB"),
    GpuPreset("H200", 141.0, 16.0, 64.0, "H200 · 141 GB VRAM · 16 CPU · 64 GB RAM", "H200 · 141GB"),
]


SandboxPickKind = Literal["builtin", "modal_cpu", "modal_gpu"]


@dataclass(frozen=True)
class SandboxPickOption:
    kind: SandboxPickKind
    label: str
    detail: str
    cpu_cores: float | None = None
    ram_gb: float | None = None
    gpu_class: str | None = None


def sandbox_pick_options() -> list[SandboxPickOption]:
    """Same choices as the web composer sandbox picker."""
    options = [
        SandboxPickOption(
            kind="builtin",
            label="Local Sandbox",
            detail="This machine (builtin)",
        )
    ]
    for preset in CPU_PRESETS:
        options.append(
            SandboxPickOption(
                kind="modal_cpu",
                label=f"Modal · {preset.short_label}",
                detail=preset.label,
                cpu_cores=preset.cpu,
                ram_gb=preset.ram,
            )
        )
    for preset in GPU_PRESETS:
        options.append(
            SandboxPickOption(
                kind="modal_gpu",
                label=f"Modal · {preset.short_label}",
                detail=preset.label,
                cpu_cores=preset.cpu,
                ram_gb=preset.ram,
                gpu_class=preset.gpu,
            )
        )
    return options


def current_sandbox_pick_index(
    config: Config | None = None,
    options: list[SandboxPickOption] | None = None,
) -> int | None:
    """Return 0-based index of the option matching current config, if any."""
    cfg = config or Config.load()
    opts = options or sandbox_pick_options()
    backend = get_sandbox_backend(cfg)
    if backend == "builtin":
        for i, opt in enumerate(opts):
            if opt.kind == "builtin":
                return i
        return None

    from agent.sandbox_backend.profile import sandbox_compute_type, sandbox_gpu_class

    compute = sandbox_compute_type(cfg)
    cpu = float(cfg.get("sandbox.cpu_cores") or 2.0)
    ram = float(cfg.get("sandbox.ram_gb") or 8.0)
    gpu = sandbox_gpu_class(cfg)
    for i, opt in enumerate(opts):
        if compute == "cpu" and opt.kind == "modal_cpu":
            if opt.cpu_cores == cpu and opt.ram_gb == ram:
                return i
        if compute == "gpu" and opt.kind == "modal_gpu":
            if opt.gpu_class == gpu:
                return i
    return None


def apply_sandbox_pick(
    option: SandboxPickOption,
    config: Config | None = None,
) -> str:
    """Apply a picker choice. Returns the toolbar label for the backend."""
    cfg = config or Config.load()
    if option.kind == "builtin":
        set_sandbox_backend("builtin", cfg)
        return "Local Sandbox"

    set_sandbox_backend("modal", cfg)
    if option.kind == "modal_gpu":
        cfg.set("sandbox.compute_type", "gpu")
        cfg.set("sandbox.gpu_class", option.gpu_class or "T4")
    else:
        cfg.set("sandbox.compute_type", "cpu")
    if option.cpu_cores is not None:
        cfg.set("sandbox.cpu_cores", float(option.cpu_cores))
    if option.ram_gb is not None:
        cfg.set("sandbox.ram_gb", float(option.ram_gb))
    cfg.save()
    return "Modal Sandbox"


def format_current_sandbox_summary(config: Config | None = None) -> str:
    cfg = config or Config.load()
    backend = get_sandbox_backend(cfg)
    if backend == "builtin":
        return "Local Sandbox (builtin)"
    from agent.sandbox_backend.profile import (
        sandbox_compute_type,
        sandbox_gpu_class,
        sandbox_image_ref,
    )

    compute = sandbox_compute_type(cfg)
    cpu = float(cfg.get("sandbox.cpu_cores") or 2.0)
    ram = float(cfg.get("sandbox.ram_gb") or 8.0)
    image = sandbox_image_ref(cfg, compute_type=compute)
    if compute == "gpu":
        return (
            f"Modal Sandbox · GPU {sandbox_gpu_class(cfg)} · "
            f"{cpu:g} CPU · {ram:g} GB · {image}"
        )
    return f"Modal Sandbox · CPU · {cpu:g} CPU · {ram:g} GB · {image}"
