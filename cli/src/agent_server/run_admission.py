"""Admission control for agent runs: how many at once, and how much RAM to keep.

Every chat turn is a worker thread in this process. Without a gate, a 4×4
grid plus Capy starts sixteen of them at once; they all build their agent,
all open model streams, and all hold their sandboxes, so a laptop with 16 GB
can swap itself to a crawl. The gate lets ``max_concurrent_runs`` proceed and
parks the rest in a queue. A run also waits while available memory is below
``min_free_memory_mb`` so a tight machine does not take on more work.

Defaults scale with the host: the slot count follows the core count, the
memory floor is fixed at 2 GB. Both are settings (Runtime → Capacity) and
environment overrides for benches.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("agent_server")

ENV_MAX_RUNS = "SANDWALK_MAX_CONCURRENT_RUNS"
ENV_MIN_FREE_MB = "SANDWALK_MIN_FREE_MEMORY_MB"
DEFAULT_MIN_FREE_MB = 2048
DEFAULT_QUEUE_TIMEOUT_S = 900.0
_POLL_S = 0.5


def default_max_runs() -> int:
    """Core count, bounded: 4 on small machines, 16 at the top."""
    cores = os.cpu_count() or 4
    return max(4, min(16, cores))


def _sysctl_int(name: str) -> int | None:
    try:
        out = subprocess.run(
            ["sysctl", "-n", name], capture_output=True, text=True, timeout=2, check=False
        ).stdout.strip()
        return int(out) if out else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def available_memory_mb() -> int | None:
    """Memory the OS could hand out now, in MiB. None when unknown."""
    try:
        import psutil

        return int(psutil.virtual_memory().available // (1024 * 1024))
    except Exception:  # noqa: BLE001 — psutil is optional
        pass
    if sys.platform == "darwin":
        try:
            out = subprocess.run(
                ["vm_stat"], capture_output=True, text=True, timeout=2, check=False
            ).stdout
        except (OSError, subprocess.TimeoutExpired):
            return None
        page = 4096
        free = inactive = speculative = 0
        for line in out.splitlines():
            if "page size of" in line:
                digits = "".join(ch for ch in line if ch.isdigit())
                page = int(digits) if digits else page
            elif line.startswith("Pages free:"):
                free = int(line.split()[-1].rstrip("."))
            elif line.startswith("Pages inactive:"):
                inactive = int(line.split()[-1].rstrip("."))
            elif line.startswith("Pages speculative:"):
                speculative = int(line.split()[-1].rstrip("."))
        return int((free + inactive + speculative) * page // (1024 * 1024))
    if platform.system() == "Linux":
        try:
            with open("/proc/meminfo", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) // 1024
        except OSError:
            return None
    return None


def total_memory_mb() -> int | None:
    if sys.platform == "darwin":
        total = _sysctl_int("hw.memsize")
        return total // (1024 * 1024) if total else None
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        size = os.sysconf("SC_PAGE_SIZE")
        return int(pages) * int(size) // (1024 * 1024)
    except (ValueError, OSError, AttributeError):
        return None


@dataclass
class CapacitySnapshot:
    running: int
    queued: int
    max_concurrent_runs: int
    min_free_memory_mb: int
    available_memory_mb: int | None
    total_memory_mb: int | None


class RunAdmission:
    """Thread-safe gate. ``acquire`` blocks in the caller's worker thread."""

    def __init__(
        self,
        *,
        max_runs: int | None = None,
        min_free_mb: int | None = None,
        memory_probe: Callable[[], int | None] = available_memory_mb,
    ) -> None:
        self._lock = threading.Lock()
        self._changed = threading.Condition(self._lock)
        self._running = 0
        self._queued = 0
        self._max_runs = max_runs
        self._min_free_mb = min_free_mb
        self._memory_probe = memory_probe

    # -- limits ---------------------------------------------------------------

    def configure(self, *, max_runs: int | None, min_free_mb: int | None) -> None:
        with self._changed:
            self._max_runs = max_runs
            self._min_free_mb = min_free_mb
            self._changed.notify_all()

    def max_runs(self) -> int:
        raw = os.environ.get(ENV_MAX_RUNS, "").strip()
        if raw:
            try:
                return max(1, int(raw))
            except ValueError:
                pass
        if self._max_runs is not None:
            return max(1, int(self._max_runs))
        return default_max_runs()

    def min_free_mb(self) -> int:
        raw = os.environ.get(ENV_MIN_FREE_MB, "").strip()
        if raw:
            try:
                return max(0, int(raw))
            except ValueError:
                pass
        if self._min_free_mb is not None:
            return max(0, int(self._min_free_mb))
        return DEFAULT_MIN_FREE_MB

    # -- state ----------------------------------------------------------------

    def snapshot(self) -> CapacitySnapshot:
        with self._lock:
            running, queued = self._running, self._queued
        return CapacitySnapshot(
            running=running,
            queued=queued,
            max_concurrent_runs=self.max_runs(),
            min_free_memory_mb=self.min_free_mb(),
            available_memory_mb=self._memory_probe(),
            total_memory_mb=total_memory_mb(),
        )

    def _blocker(self) -> tuple[str, int] | None:
        """Why a new run cannot start right now, or None. Caller holds the lock."""
        limit = self.max_runs()
        if self._running >= limit:
            return "slots", self._running - limit + 1 + self._queued
        floor = self.min_free_mb()
        if floor > 0:
            available = self._memory_probe()
            if available is not None and available < floor:
                return "memory", available
        return None

    # -- acquire / release ----------------------------------------------------

    def acquire(
        self,
        *,
        on_wait: Callable[[str], None] | None = None,
        timeout_s: float = DEFAULT_QUEUE_TIMEOUT_S,
    ) -> None:
        """Block until a slot and enough memory are free.

        ``on_wait`` receives a short message when the run is parked and again
        when the reason changes. Raises ``TimeoutError`` after ``timeout_s``.
        """
        deadline = time.monotonic() + timeout_s
        last_message: str | None = None
        with self._changed:
            blocker = self._blocker()
            if blocker is not None:
                self._queued += 1
            try:
                while blocker is not None:
                    kind, value = blocker
                    if kind == "slots":
                        ahead = max(0, self._queued - 1)
                        message = (
                            f"Waiting for a free agent slot ({self._running} of "
                            f"{self.max_runs()} running"
                            + (f", {ahead} ahead in the queue" if ahead else "")
                            + ")."
                        )
                    else:
                        message = (
                            f"Waiting for memory: {value / 1024:.1f} GB available, "
                            f"this server keeps {self.min_free_mb() / 1024:.1f} GB free."
                        )
                    if message != last_message:
                        last_message = message
                        if on_wait is not None:
                            try:
                                on_wait(message)
                            except Exception:  # noqa: BLE001 — never block on UI
                                pass
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError(
                            "This run waited too long for capacity. Stop some chats "
                            "or raise Max concurrent runs in Runtime settings."
                        )
                    self._changed.wait(timeout=min(_POLL_S, remaining))
                    blocker = self._blocker()
            finally:
                if last_message is not None:
                    self._queued = max(0, self._queued - 1)
            self._running += 1

    def release(self) -> None:
        with self._changed:
            self._running = max(0, self._running - 1)
            self._changed.notify_all()


_admission = RunAdmission()


def run_admission() -> RunAdmission:
    return _admission


def refresh_from_config(config: Any) -> None:
    """Pull the user's limits out of Config; called on startup and on save."""
    try:
        max_runs = config.get("agent.max_concurrent_runs")
        min_free = config.get("agent.min_free_memory_mb")
    except Exception:  # noqa: BLE001
        return
    _admission.configure(
        max_runs=int(max_runs) if max_runs not in (None, "", 0, "0") else None,
        min_free_mb=int(min_free) if min_free not in (None, "") else None,
    )


__all__ = [
    "CapacitySnapshot",
    "DEFAULT_MIN_FREE_MB",
    "RunAdmission",
    "available_memory_mb",
    "default_max_runs",
    "refresh_from_config",
    "run_admission",
    "total_memory_mb",
]
