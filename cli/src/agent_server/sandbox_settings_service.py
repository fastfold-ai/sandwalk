"""Sandbox settings shared by terminal and web presentation layers."""

from __future__ import annotations

from agent.config import Config
from agent_server.models import (
    SandboxProbeReport,
    SandboxProbeStep,
    SandboxSettings,
    UpdateSandboxSettingsRequest,
)

_VALID_BACKENDS = frozenset({"builtin", "modal"})
_VALID_COMPUTE = frozenset({"cpu", "gpu"})
_MODAL_TOKENS_REQUIRED = (
    "Modal sandbox requires compute.modal_token_id and "
    "compute.modal_token_secret (Integrations → Modal)."
)


def _clamp_float(value: object, *, minimum: float, maximum: float, default: float) -> float:
    try:
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            return default
        return max(minimum, min(maximum, float(value)))
    except (TypeError, ValueError):
        return default


def _clamp_int(value: object, *, minimum: int, maximum: int, default: int) -> int:
    try:
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            return default
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


def _pip_packages_str(raw: object) -> str:
    if raw is None:
        return str(Config.load().get("sandbox.pip_packages") or "")
    if isinstance(raw, (list, tuple)):
        return ",".join(str(x).strip() for x in raw if str(x).strip())
    return str(raw).strip()


class SandboxSettingsService:
    @staticmethod
    def get() -> SandboxSettings:
        from agent.sandbox_probe import modal_tokens_present

        config = Config.load()
        backend = str(config.get("sandbox.backend") or "builtin").strip().lower()
        if backend not in _VALID_BACKENDS:
            backend = "builtin"
        compute_type = str(config.get("sandbox.compute_type") or "cpu").strip().lower()
        if compute_type not in _VALID_COMPUTE:
            compute_type = "cpu"
        configured, _detail = modal_tokens_present(config)
        return SandboxSettings(
            backend=backend,
            modal_app=str(config.get("sandbox.modal_app") or "sandwalk"),
            cpu_image=str(config.get("sandbox.cpu_image") or "python:3.12-slim"),
            gpu_image=str(config.get("sandbox.gpu_image") or "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime"),
            pip_packages=_pip_packages_str(config.get("sandbox.pip_packages")),
            compute_type=compute_type,
            gpu_class=str(config.get("sandbox.gpu_class") or "T4"),
            cpu_cores=_clamp_float(
                config.get("sandbox.cpu_cores", 2.0),
                minimum=0.25,
                maximum=64.0,
                default=2.0,
            ),
            ram_gb=_clamp_float(
                config.get("sandbox.ram_gb", 8.0),
                minimum=0.5,
                maximum=256.0,
                default=8.0,
            ),
            idle_ttl_seconds=_clamp_int(
                config.get("sandbox.idle_ttl_seconds", 600),
                minimum=60,
                maximum=86400,
                default=600,
            ),
            modal_configured=configured,
        )

    @staticmethod
    def update(payload: UpdateSandboxSettingsRequest) -> SandboxSettings:
        from agent.sandbox_probe import modal_tokens_present

        config = Config.load()
        if payload.backend is not None:
            backend = str(payload.backend).strip().lower()
            if backend not in _VALID_BACKENDS:
                raise ValueError("sandbox.backend must be 'builtin' or 'modal'")
            if backend == "modal":
                configured, _detail = modal_tokens_present(config)
                if not configured:
                    raise ValueError(_MODAL_TOKENS_REQUIRED)
            config.set("sandbox.backend", backend)
        if payload.modal_app is not None:
            app = str(payload.modal_app).strip() or "sandwalk"
            config.set("sandbox.modal_app", app)
        if payload.cpu_image is not None:
            config.set("sandbox.cpu_image", str(payload.cpu_image).strip() or "python:3.12-slim")
        if payload.gpu_image is not None:
            config.set(
                "sandbox.gpu_image",
                str(payload.gpu_image).strip() or "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime",
            )
        if payload.pip_packages is not None:
            config.set("sandbox.pip_packages", _pip_packages_str(payload.pip_packages))
        if payload.compute_type is not None:
            compute_type = str(payload.compute_type).strip().lower()
            if compute_type not in _VALID_COMPUTE:
                raise ValueError("sandbox.compute_type must be 'cpu' or 'gpu'")
            config.set("sandbox.compute_type", compute_type)
        if payload.gpu_class is not None:
            config.set("sandbox.gpu_class", str(payload.gpu_class).strip() or "T4")
        if payload.cpu_cores is not None:
            config.set(
                "sandbox.cpu_cores",
                _clamp_float(
                    payload.cpu_cores, minimum=0.25, maximum=64.0, default=2.0
                ),
            )
        if payload.ram_gb is not None:
            config.set(
                "sandbox.ram_gb",
                _clamp_float(payload.ram_gb, minimum=0.5, maximum=256.0, default=8.0),
            )
        if payload.idle_ttl_seconds is not None:
            config.set(
                "sandbox.idle_ttl_seconds",
                _clamp_int(
                    payload.idle_ttl_seconds,
                    minimum=60,
                    maximum=86400,
                    default=600,
                ),
            )
        config.save()
        return SandboxSettingsService.get()

    @staticmethod
    def probe(*, terminate: bool = True) -> SandboxProbeReport:
        from agent.sandbox_probe import run_modal_sandbox_probe

        report = run_modal_sandbox_probe(terminate=terminate)
        return SandboxProbeReport(
            ok=report.ok,
            skipped=report.skipped,
            steps=[
                SandboxProbeStep(name=step.name, ok=step.ok, detail=step.detail)
                for step in report.steps
            ],
        )
