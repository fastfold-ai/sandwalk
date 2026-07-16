"""Best-effort GPU metrics (Apple ioreg/system_profiler) for the Status page."""

from __future__ import annotations

import platform
import re
import subprocess


def _chip_name() -> str | None:
    if platform.system() != "Darwin":
        return None
    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        value = result.stdout.strip()
        return value or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _gpu_core_count_from_profiler() -> int | None:
    if platform.system() != "Darwin":
        return None
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            if "Total Number of Cores" in line:
                match = re.search(r"(\d+)", line)
                if match:
                    return int(match.group(1))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    return None


def _gpu_metrics_darwin() -> dict[str, int | float | None]:
    """Read Apple GPU utilization / memory / core count via ioreg (no sudo)."""
    metrics: dict[str, int | float | None] = {
        "gpu_cores": None,
        "gpu_utilization_percent": None,
        "gpu_memory_used_bytes": None,
        "gpu_memory_total_bytes": None,
    }
    if platform.system() != "Darwin":
        return metrics
    try:
        import plistlib

        result = subprocess.run(
            ["ioreg", "-a", "-r", "-d", "1", "-c", "IOAccelerator"],
            check=False,
            capture_output=True,
            timeout=3,
        )
        if result.returncode != 0 or not result.stdout:
            metrics["gpu_cores"] = _gpu_core_count_from_profiler()
            return metrics
        payload = plistlib.loads(result.stdout)
        item = payload[0] if isinstance(payload, list) and payload else payload
        if not isinstance(item, dict):
            metrics["gpu_cores"] = _gpu_core_count_from_profiler()
            return metrics

        cores = item.get("gpu-core-count")
        if isinstance(cores, int) and cores > 0:
            metrics["gpu_cores"] = cores
        else:
            metrics["gpu_cores"] = _gpu_core_count_from_profiler()

        stats = item.get("PerformanceStatistics")
        if isinstance(stats, dict):
            util = stats.get("Device Utilization %")
            if isinstance(util, (int, float)):
                metrics["gpu_utilization_percent"] = float(
                    max(0.0, min(100.0, util))
                )
            used = stats.get("In use system memory")
            if isinstance(used, int) and used >= 0:
                metrics["gpu_memory_used_bytes"] = used
            allocated = stats.get("Alloc system memory")
            if isinstance(allocated, int) and allocated > 0:
                metrics["gpu_memory_total_bytes"] = allocated
    except (OSError, ValueError, subprocess.TimeoutExpired, Exception):
        metrics["gpu_cores"] = _gpu_core_count_from_profiler()
    return metrics
