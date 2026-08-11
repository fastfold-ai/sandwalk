"""Server status, system metrics, and lifecycle helpers for the Status page.

Split package — re-exports the public surface previously defined in
``agent_server/status_service.py`` so existing imports keep working.
"""

from __future__ import annotations

import os
import platform
import time
from datetime import UTC, datetime

from agent.config import CONFIG_DIR
from agent_server.models import ServerStatusReport, ServerSystemInfo
from agent_server.status_service.cache import _cache_info, cache_dir, clear_cache
from agent_server.status_service.gpu_metrics import (
    _chip_name,
    _gpu_core_count_from_profiler,
    _gpu_metrics_darwin,
)
from agent_server.status_service.host_metrics import (
    _format_platform_label,
    _load_average,
    _ram_bytes,
    _thermal_state,
)
from agent_server.status_service.lifecycle import (
    _build_restart_command,
    _lifecycle_allowed,
    schedule_restart,
    schedule_stop,
)

__all__ = [
    "cache_dir",
    "clear_cache",
    "get_status_report",
    "schedule_restart",
    "schedule_stop",
]

# Set when the process first imports this module (app boot).
_STARTED_AT = time.time()
_STARTED_AT_ISO = datetime.now(UTC).isoformat()


def get_status_report(*, version: str, service: str = "sandwalk") -> ServerStatusReport:
    used, total = _ram_bytes()
    chip_name = _chip_name()
    gpu = _gpu_metrics_darwin()
    host = os.environ.get("FASTFOLD_SERVE_HOST") or None
    port_raw = os.environ.get("FASTFOLD_SERVE_PORT")
    port: int | None = None
    if port_raw:
        try:
            port = int(port_raw)
        except ValueError:
            port = None
    bind = None
    if host and port is not None:
        bind = f"{host}:{port}"
    elif host:
        bind = host

    gpu_mem_total = gpu.get("gpu_memory_total_bytes")
    if not isinstance(gpu_mem_total, int) or gpu_mem_total <= 0:
        gpu_mem_total = total if total > 0 else None

    return ServerStatusReport(
        status="running",
        service=service,
        version=version,
        message=f"Listening on {bind}" if bind else "Server is running",
        host=host,
        port=port,
        pid=os.getpid(),
        started_at=_STARTED_AT_ISO,
        uptime_seconds=max(0.0, time.time() - _STARTED_AT),
        system=ServerSystemInfo(
            label=_format_platform_label(chip_name=chip_name),
            platform=platform.system(),
            arch=platform.machine(),
            os_version=(
                platform.mac_ver()[0]
                if platform.system() == "Darwin"
                else platform.release()
            ),
            python_version=platform.python_version(),
            ram_used_bytes=used,
            ram_total_bytes=total,
            thermal_state=_thermal_state(),
            load_average=_load_average(),
            chip_name=chip_name,
            gpu_cores=(
                gpu_cores_raw if isinstance(gpu_cores_raw := gpu.get("gpu_cores"), int) else None
            ),
            gpu_utilization_percent=(
                float(gpu_util_raw)
                if isinstance(gpu_util_raw := gpu.get("gpu_utilization_percent"), (int, float))
                else None
            ),
            gpu_memory_used_bytes=(
                int(gpu_mem_used_raw)
                if isinstance(gpu_mem_used_raw := gpu.get("gpu_memory_used_bytes"), int)
                else None
            ),
            gpu_memory_total_bytes=(
                int(gpu_mem_total) if isinstance(gpu_mem_total, int) else None
            ),
        ),
        cache=_cache_info(),
        checked_at=datetime.now(UTC).isoformat(),
    )
