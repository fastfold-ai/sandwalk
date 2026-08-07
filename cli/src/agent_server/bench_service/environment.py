"""Capture a reproducibility snapshot for a bench run."""

from __future__ import annotations

import logging
import platform
import time
from typing import Any

from agent_server.app_deps import AppDeps

logger = logging.getLogger(__name__)

_CORE_PACKAGES = (
    "deepagents",
    "langchain",
    "langchain-core",
    "langgraph",
    "langchain-anthropic",
    "langchain-openai",
    "langchain-mcp-adapters",
)


def capture_bench_environment(
    deps: AppDeps | None = None,
    *,
    model_id: str,
    provider: str | None = None,
    specialist_id: str | None = None,
    thinking: bool = False,
    suite_id: str | None = None,
    sample_size: int | None = None,
    pack_id: str | None = None,
    matrix: str | None = None,
) -> dict[str, Any]:
    """Best-effort env snapshot at run start. Failures never abort a bench run."""
    captured_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        return {
            "captured_at": captured_at,
            "started_at": captured_at,
            "sandwalk_version": _sandwalk_version(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.system(),
            "arch": platform.machine(),
            "os_version": platform.release(),
            "packages": _core_packages(),
            "model": {
                "provider": provider,
                "model_id": model_id,
                "specialist_id": specialist_id,
                "thinking": bool(thinking),
            },
            "runtime": _runtime_settings(),
            "sandbox": _sandbox_settings(),
            "skills": _skills_snapshot(),
            "mcp_servers": _mcp_snapshot(deps),
            "suite": {
                "suite_id": suite_id,
                "sample_size": sample_size,
                "pack_id": pack_id,
                "matrix": matrix,
            },
        }
    except Exception as exc:  # noqa: BLE001 — never block the run
        logger.warning("bench environment capture failed: %s", exc)
        return {
            "captured_at": captured_at,
            "started_at": captured_at,
            "error": str(exc),
            "model": {
                "provider": provider,
                "model_id": model_id,
                "specialist_id": specialist_id,
                "thinking": bool(thinking),
            },
        }


def _sandwalk_version() -> str:
    try:
        from _version import __version__

        return str(__version__)
    except Exception:  # noqa: BLE001
        return "unknown"


def _core_packages() -> dict[str, str]:
    try:
        from importlib import metadata as importlib_metadata
    except Exception:  # noqa: BLE001
        return {}
    out: dict[str, str] = {}
    for name in _CORE_PACKAGES:
        try:
            out[name] = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            continue
        except Exception:  # noqa: BLE001
            continue
    return out


def _runtime_settings() -> dict[str, Any]:
    try:
        from agent_server.settings_service import SettingsService

        settings = SettingsService.get()
        return {
            "provider": settings.provider,
            "model": settings.model,
            "agent_profile": settings.agent_profile,
            "tool_mode": settings.tool_mode,
            "knowledge_level": settings.knowledge_level,
            "reasoning_effort": settings.reasoning_effort,
            "reasoning_fast": settings.reasoning_fast,
            "recursion_limit": settings.recursion_limit,
            "max_sdk_turns": settings.max_sdk_turns,
            "file_access": settings.file_access,
            "plan_mode": settings.plan_mode,
            "openai_base_url": settings.openai_base_url,
            "openai_profile_id": settings.openai_profile_id,
        }
    except Exception as exc:  # noqa: BLE001
        logger.debug("runtime settings capture failed: %s", exc)
        return {}


def _sandbox_settings() -> dict[str, Any]:
    try:
        from agent_server.sandbox_settings_service import SandboxSettingsService

        settings = SandboxSettingsService.get()
        return {
            "backend": settings.backend,
            "compute_type": settings.compute_type,
            "modal_app": settings.modal_app,
            "cpu_image": settings.cpu_image,
            "gpu_image": settings.gpu_image,
            "pip_packages": settings.pip_packages,
            "gpu_class": settings.gpu_class,
            "cpu_cores": settings.cpu_cores,
            "ram_gb": settings.ram_gb,
        }
    except Exception as exc:  # noqa: BLE001
        logger.debug("sandbox settings capture failed: %s", exc)
        return {}


def _skills_snapshot() -> list[dict[str, Any]]:
    try:
        from agent.skills import list_skills

        skills = list(list_skills(enabled_only=False))
    except Exception as exc:  # noqa: BLE001
        logger.debug("skills capture failed: %s", exc)
        return []
    rows: list[dict[str, Any]] = []
    for skill in skills:
        rows.append(
            {
                "name": getattr(skill, "name", "") or "",
                "version": getattr(skill, "version", None),
                "source": getattr(skill, "source", "") or "",
                "enabled": bool(getattr(skill, "enabled", True)),
                "commit": getattr(skill, "commit", None),
            }
        )
    rows.sort(key=lambda row: str(row.get("name") or "").lower())
    return rows


def _mcp_snapshot(deps: AppDeps | None) -> list[dict[str, Any]]:
    if deps is None:
        return []
    try:
        servers = list(deps.store.list_mcp_servers(enabled_only=False))
    except Exception as exc:  # noqa: BLE001
        logger.debug("mcp capture failed: %s", exc)
        return []
    rows: list[dict[str, Any]] = []
    for server in servers:
        rows.append(
            {
                "id": getattr(server, "id", None),
                "name": getattr(server, "name", "") or "",
                "transport": getattr(server, "transport", None),
                "catalog_id": getattr(server, "catalog_id", None),
                "enabled": bool(getattr(server, "enabled", True)),
                # Intentionally omit command/url/headers/auth.
            }
        )
    rows.sort(key=lambda row: str(row.get("name") or "").lower())
    return rows
