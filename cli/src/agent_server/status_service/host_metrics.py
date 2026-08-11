"""Best-effort platform label, RAM, thermal, and load-average metrics."""

from __future__ import annotations

import os
import platform
import re
import subprocess
from pathlib import Path


def _hw_model() -> str | None:
    """macOS hardware model id (e.g. ``Macmini9,1``)."""
    if platform.system() != "Darwin":
        return None
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.model"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        value = result.stdout.strip()
        return value or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _mac_product_family(hw_model: str | None) -> str | None:
    """Map Apple ``hw.model`` / Model Name to a product family label."""
    if hw_model:
        key = hw_model.split(",", 1)[0].lower()
        mapping = (
            ("macmini", "Mac mini"),
            ("macbookpro", "MacBook Pro"),
            ("macbookair", "MacBook Air"),
            ("macbook", "MacBook"),
            ("macpro", "Mac Pro"),
            ("macstudio", "Mac Studio"),
            ("imacpro", "iMac Pro"),
            ("imac", "iMac"),
            ("virtualmac", "Virtual Mac"),
        )
        for prefix, label in mapping:
            if key.startswith(prefix):
                return label
    # Newer Apple Silicon ids are ``Mac14,3`` / ``Mac17,6`` — use Model Name.
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "Model Name:" in line:
                    name = line.split(":", 1)[1].strip()
                    return name or None
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


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


def format_device_label(*, chip_name: str | None = None) -> str:
    """Public LAN-discover label: product family + chip/OS (or Linux/Windows)."""
    system = platform.system()
    if system == "Darwin":
        family = _mac_product_family(_hw_model())
        base = _format_platform_label(chip_name=chip_name)
        if family:
            return f"{family} · {base}"
        return base
    return _format_platform_label(chip_name=chip_name)


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
