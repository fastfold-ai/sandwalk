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
    bytes_done: int = 0
    bytes_total: int | None = None
    files_done: int = 0
    files_total: int = 0
    label: str = ""


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
            bytes_done=job.bytes_done,
            bytes_total=job.bytes_total,
            files_done=job.files_done,
            files_total=job.files_total,
            label=job.label,
        )


def is_installing(suite_id: str) -> bool:
    job = get_install_job(suite_id)
    return bool(job and job.status == "installing")


def install_error(suite_id: str) -> str | None:
    job = get_install_job(suite_id)
    if job is None or job.status != "error":
        return None
    return job.error or job.summary or "Install failed."


def install_progress_text(suite_id: str) -> str | None:
    """Human progress line for catalog / UI while installing."""
    job = get_install_job(suite_id)
    if job is None or job.status != "installing":
        return None
    return _format_progress(job)


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
                summary=install_progress_text(key) or "Install already in progress.",
                status="installing",
            )
        _jobs[key] = InstallJob(
            suite_id=key,
            status="installing",
            summary="Starting download…",
            label="Starting…",
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
    def on_progress(
        *,
        summary: str | None = None,
        bytes_done: int | None = None,
        bytes_total: int | None = None,
        files_done: int | None = None,
        files_total: int | None = None,
        label: str | None = None,
    ) -> None:
        with _lock:
            job = _jobs.get(suite_id)
            if job is None or job.status != "installing":
                return
            if summary is not None:
                job.summary = summary
            if bytes_done is not None:
                job.bytes_done = max(0, int(bytes_done))
            if bytes_total is not None:
                job.bytes_total = int(bytes_total) if bytes_total > 0 else None
            if files_done is not None:
                job.files_done = max(0, int(files_done))
            if files_total is not None:
                job.files_total = max(0, int(files_total))
            if label is not None:
                job.label = label
            job.summary = _format_progress(job)

    try:
        result = install_suite(suite_id, force=force, on_progress=on_progress)
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


def _format_progress(job: InstallJob) -> str:
    parts: list[str] = []
    if job.files_total > 0:
        parts.append(f"file {min(job.files_done + 1, job.files_total)}/{job.files_total}")
    if job.label and job.label not in {"Starting…", "Starting..."}:
        parts.append(job.label)
    size = _format_bytes(job.bytes_done)
    if job.bytes_total and job.bytes_total > 0:
        parts.append(f"{size} / {_format_bytes(job.bytes_total)}")
        pct = min(100.0, (100.0 * job.bytes_done) / job.bytes_total)
        parts.append(f"{pct:.0f}%")
    elif job.bytes_done > 0:
        parts.append(f"{size} downloaded")
    if not parts:
        return job.summary or "Downloading dataset…"
    return " · ".join(parts)


def _format_bytes(n: int) -> str:
    value = float(max(0, n))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{n} B"
