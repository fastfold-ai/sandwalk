"""Background Bench dataset installs that survive leaving the page."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Literal

from agent_server.bench_service.dataset_install import (
    INSTALLABLE_SUITE_IDS,
    BenchInstallError,
    install_suite,
    resolve_hf_token,
)
from agent_server.models.bench import BenchInstallResponse

logger = logging.getLogger(__name__)

InstallStatus = Literal["installing", "done", "error"]


@dataclass
class InstallJob:
    suite_id: str
    status: InstallStatus
    summary: str = ""
    error: str | None = None
    needs_hf_token: bool = False
    path: str | None = None


_lock = threading.Lock()
_jobs: dict[str, InstallJob] = {}


def get_install_job(suite_id: str) -> InstallJob | None:
    with _lock:
        job = _jobs.get(suite_id)
        if job is None:
            return None
        return InstallJob(
            suite_id=job.suite_id,
            status=job.status,
            summary=job.summary,
            error=job.error,
            needs_hf_token=job.needs_hf_token,
            path=job.path,
        )


def is_installing(suite_id: str) -> bool:
    job = get_install_job(suite_id)
    return bool(job and job.status == "installing")


def install_error(suite_id: str) -> str | None:
    job = get_install_job(suite_id)
    if job is None or job.status != "error":
        return None
    return job.error or job.summary or "Install failed."


def start_install(suite_id: str, *, force: bool = False) -> BenchInstallResponse:
    """Kick off a daemon install and return immediately."""
    key = (suite_id or "").strip()
    if key not in INSTALLABLE_SUITE_IDS:
        raise BenchInstallError(
            f"Suite '{key}' is not installable from the dashboard.",
            status_code=404,
        )
    if key == "bixbench-verified-50" and not resolve_hf_token():
        raise BenchInstallError(
            "Hugging Face token required. Save it under Integrations → Hugging Face "
            "(or set HF_TOKEN), accept the dataset terms, then Install again.",
            status_code=400,
            needs_hf_token=True,
        )

    with _lock:
        existing = _jobs.get(key)
        if existing and existing.status == "installing":
            return BenchInstallResponse(
                ok=True,
                suite_id=key,
                summary="Install already in progress.",
                status="installing",
            )
        _jobs[key] = InstallJob(
            suite_id=key,
            status="installing",
            summary="Downloading dataset…",
        )

    thread = threading.Thread(
        target=_run_install,
        args=(key, force),
        name=f"bench-install-{key}",
        daemon=True,
    )
    thread.start()
    return BenchInstallResponse(
        ok=True,
        suite_id=key,
        summary="Install started in the background.",
        status="installing",
    )


def _run_install(suite_id: str, force: bool) -> None:
    try:
        result = install_suite(suite_id, force=force)
    except BenchInstallError as exc:
        logger.warning("Bench install failed for %s: %s", suite_id, exc)
        with _lock:
            _jobs[suite_id] = InstallJob(
                suite_id=suite_id,
                status="error",
                summary=str(exc),
                error=str(exc),
                needs_hf_token=exc.needs_hf_token,
            )
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bench install crashed for %s", suite_id)
        with _lock:
            _jobs[suite_id] = InstallJob(
                suite_id=suite_id,
                status="error",
                summary=str(exc),
                error=str(exc),
            )
        return

    with _lock:
        _jobs[suite_id] = InstallJob(
            suite_id=suite_id,
            status="done",
            summary=result.summary,
            path=result.path,
        )
