"""Server status, system metrics, and lifecycle helpers for the Status page."""

from __future__ import annotations

import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from agent.config import CONFIG_DIR
from agent_server.models import (
    ServerCacheInfo,
    ServerLifecycleResult,
    ServerStatusReport,
    ServerSystemInfo,
)
from agent_server.storage_service import _path_size_bytes

# Set when the process first imports this module (app boot).
_STARTED_AT = time.time()
_STARTED_AT_ISO = datetime.now(UTC).isoformat()


def _format_platform_label(*, chip_name: str | None = None) -> str:
    system = platform.system()
    release = platform.mac_ver()[0] if system == "Darwin" else platform.release()
    machine = platform.machine().lower()
    if system == "Darwin":
        chip = chip_name or (
            "Apple Silicon" if machine in {"arm64", "aarch64"} else "Intel"
        )
        os_label = f"macOS {release}" if release else "macOS"
        return f"{chip} · {os_label}"
    if system == "Linux":
        arch = "ARM64" if machine in {"arm64", "aarch64"} else machine.upper()
        return f"Linux · {arch}"
    return f"{system} · {platform.machine()}"


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


def _ram_bytes() -> tuple[int, int]:
    """Return (used_bytes, total_bytes). Best-effort; zeros if unavailable."""
    total = 0
    used = 0
    system = platform.system()
    try:
        if system == "Darwin":
            total_out = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if total_out.returncode == 0 and total_out.stdout.strip():
                total = int(total_out.stdout.strip())
            vm = subprocess.run(
                ["vm_stat"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if vm.returncode == 0:
                page_size = 4096
                match = re.search(r"page size of (\d+) bytes", vm.stdout)
                if match:
                    page_size = int(match.group(1))
                stats: dict[str, int] = {}
                for line in vm.stdout.splitlines():
                    if ":" not in line:
                        continue
                    key, value = line.split(":", 1)
                    digits = re.sub(r"[^\d]", "", value)
                    if digits:
                        stats[key.strip()] = int(digits)
                free_pages = stats.get("Pages free", 0) + stats.get(
                    "Pages speculative", 0
                )
                free = free_pages * page_size
                if total > 0:
                    used = max(0, total - free)
        elif system == "Linux":
            meminfo = Path("/proc/meminfo").read_text(encoding="utf-8")
            values: dict[str, int] = {}
            for line in meminfo.splitlines():
                if ":" not in line:
                    continue
                key, rest = line.split(":", 1)
                parts = rest.strip().split()
                if parts:
                    values[key] = int(parts[0]) * 1024
            total = values.get("MemTotal", 0)
            available = values.get("MemAvailable", values.get("MemFree", 0))
            used = max(0, total - available)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return used, total


def _thermal_state() -> str | None:
    """Best-effort thermal label (macOS via `pmset`)."""
    if platform.system() != "Darwin":
        return None
    try:
        result = subprocess.run(
            ["pmset", "-g", "therm"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0:
            return None
        text = result.stdout.lower()
        if "cpu_speed_limit" in text:
            match = re.search(r"cpu_speed_limit\s*=\s*(\d+)", text)
            if match and int(match.group(1)) < 100:
                return "Fair"
        if "thermal level" in text or "nominal" in text:
            return "Nominal"
        return "Nominal"
    except (OSError, subprocess.TimeoutExpired):
        return None


def _load_average() -> list[float] | None:
    try:
        return [round(value, 2) for value in os.getloadavg()]
    except (AttributeError, OSError):
        return None


def cache_dir() -> Path:
    return CONFIG_DIR / "cache"


def _cache_info() -> ServerCacheInfo:
    path = cache_dir()
    file_count = 0
    if path.is_dir():
        try:
            for child in path.rglob("*"):
                try:
                    if child.is_file():
                        file_count += 1
                except OSError:
                    continue
        except OSError:
            pass
    return ServerCacheInfo(
        file_count=file_count,
        total_bytes=_path_size_bytes(path),
        path=str(path),
    )


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


def clear_cache() -> ServerCacheInfo:
    path = cache_dir()
    if path.is_dir():
        for child in path.iterdir():
            try:
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink(missing_ok=True)
            except OSError:
                continue
    path.mkdir(parents=True, exist_ok=True)
    return _cache_info()


def _lifecycle_allowed() -> bool:
    if os.environ.get("FASTFOLD_DISABLE_SERVER_LIFECYCLE") == "1":
        return False
    if "PYTEST_CURRENT_TEST" in os.environ:
        return False
    return True


def _build_restart_command() -> list[str] | None:
    host = os.environ.get("FASTFOLD_SERVE_HOST", "127.0.0.1")
    port = os.environ.get("FASTFOLD_SERVE_PORT", "8787")
    public = os.environ.get("FASTFOLD_SERVE_PUBLIC") == "1"
    api_key = (os.environ.get("FASTFOLD_SERVER_API_KEY") or "").strip()
    origins = [
        part.strip()
        for part in os.environ.get("FASTFOLD_SERVE_ORIGINS", "").split(",")
        if part.strip()
    ]
    hosts = [
        part.strip()
        for part in os.environ.get("FASTFOLD_SERVE_HOSTS", "").split(",")
        if part.strip()
    ]
    uds = (os.environ.get("FASTFOLD_SERVE_UDS") or "").strip()

    binary = shutil.which("sandwalk") or shutil.which("fastfold")
    if binary:
        cmd = [binary, "serve"]
    else:
        cmd = [sys.executable, "-m", "cli", "serve"]

    if uds:
        cmd.extend(["--uds", uds])
    else:
        cmd.extend(["--host", host, "--port", port])
    if public:
        cmd.append("--public")
        if api_key:
            cmd.extend(["--api-key", api_key])
        for origin in origins:
            cmd.extend(["--allowed-origin", origin])
        for allowed in hosts:
            cmd.extend(["--allowed-host", allowed])
    return cmd


def schedule_stop() -> ServerLifecycleResult:
    if not _lifecycle_allowed():
        return ServerLifecycleResult(
            ok=True,
            action="stop",
            message="Stop scheduled (dry-run; lifecycle disabled).",
        )

    def _stop() -> None:
        time.sleep(0.35)
        os.kill(os.getpid(), signal.SIGTERM)

    import threading

    threading.Thread(target=_stop, name="server-stop", daemon=True).start()
    return ServerLifecycleResult(
        ok=True,
        action="stop",
        message="Server is shutting down.",
    )


def schedule_restart() -> ServerLifecycleResult:
    cmd = _build_restart_command()
    if cmd is None:
        return ServerLifecycleResult(
            ok=False,
            action="restart",
            message="Unable to build restart command.",
        )
    if not _lifecycle_allowed():
        return ServerLifecycleResult(
            ok=True,
            action="restart",
            message="Restart scheduled (dry-run; lifecycle disabled).",
        )

    def _restart() -> None:
        time.sleep(0.4)
        try:
            subprocess.Popen(  # noqa: S603 — intentional self-relaunch
                cmd,
                start_new_session=True,
                env=os.environ.copy(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        finally:
            os.kill(os.getpid(), signal.SIGTERM)

    import threading

    threading.Thread(target=_restart, name="server-restart", daemon=True).start()
    return ServerLifecycleResult(
        ok=True,
        action="restart",
        message="Server is restarting.",
    )

