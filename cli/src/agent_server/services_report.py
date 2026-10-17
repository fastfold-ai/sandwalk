"""Daemon snapshot for Settings → Logs: pid, port, memory, and recent log lines."""

from __future__ import annotations

import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from agent.diagnostics.logging_setup import LOGS_DIR
from agent.diagnostics.redact import _redact_text
from agent_server.models import ServiceLogTail, ServiceProcess, ServicesReport

_LLAMA_PORT = 9931
_LOG_LINES = 120


def _process_stats(pid: int) -> tuple[int | None, float | None, str | None]:
    try:
        completed = subprocess.run(
            ["ps", "-p", str(pid), "-o", "rss=,pcpu=,command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, None, None
    line = (completed.stdout or "").strip()
    if not line:
        return None, None, None
    rss_text, _, rest = line.partition(" ")
    rest = rest.strip()
    cpu_text, _, command = rest.partition(" ")
    rss = int(rss_text) * 1024 if rss_text.isdigit() else None
    try:
        cpu = float(cpu_text)
    except ValueError:
        cpu = None
        command = rest
    return rss, cpu, command.strip() or None


def _listen_port(pid: int) -> int | None:
    try:
        completed = subprocess.run(
            ["lsof", "-nP", "-a", "-p", str(pid), "-iTCP", "-sTCP:LISTEN"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in (completed.stdout or "").splitlines():
        match = re.search(r":(\d+)\s+\(LISTEN\)", line)
        if match:
            return int(match.group(1))
    return None


def _pid_on_port(port: int) -> int | None:
    try:
        completed = subprocess.run(
            ["lsof", "-nP", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in (completed.stdout or "").splitlines():
        token = line.strip()
        if token.isdigit():
            return int(token)
    return None


def _sandwalk_port(pid: int) -> int | None:
    found = _listen_port(pid)
    if found is not None:
        return found
    raw = os.environ.get("FASTFOLD_SERVE_PORT") or os.environ.get("SANDWALK_PORT")
    if raw and raw.isdigit():
        return int(raw)
    return None


def _llama_process() -> ServiceProcess:
    from agent_server.llama_runtime import llama_binary, serve_pid

    pid = serve_pid() or _pid_on_port(_LLAMA_PORT)
    binary = llama_binary()
    if pid is None:
        detail = binary or "llama CLI is not installed"
        return ServiceProcess(
            id="llama",
            name="Llama",
            status="stopped",
            port=_LLAMA_PORT,
            command=f"{binary} serve --host 127.0.0.1 --port {_LLAMA_PORT}" if binary else None,
            detail=detail,
        )
    rss, cpu, command = _process_stats(pid)
    return ServiceProcess(
        id="llama",
        name="Llama",
        status="running",
        pid=pid,
        port=_LLAMA_PORT,
        rss_bytes=rss,
        cpu_percent=cpu,
        command=command or (f"{binary} serve" if binary else None),
        detail=f"127.0.0.1:{_LLAMA_PORT}",
    )


def _log_tails() -> list[ServiceLogTail]:
    if not LOGS_DIR.exists():
        return []
    preferred = ["agent-server.log", "llama.log", "cli.log"]
    ordered: list[Path] = []
    for name in preferred:
        path = LOGS_DIR / name
        if path.is_file():
            ordered.append(path)
    extras = [
        path
        for path in LOGS_DIR.iterdir()
        if path.is_file()
        and path not in ordered
        and (path.suffix == ".log" or path.name.startswith("agent-server.log"))
    ]
    extras.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    ordered.extend(extras)
    return [ServiceLogTail(name=path.name, tail=_tail(path)) for path in ordered[:6]]


def _tail(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return f"<unable to read {path.name}: {exc}>"
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()[-_LOG_LINES:]
    return _redact_text("\n".join(lines))


def build_services_report(*, version: str) -> ServicesReport:
    pid = os.getpid()
    rss, cpu, command = _process_stats(pid)
    port = _sandwalk_port(pid)
    api = ServiceProcess(
        id="sandwalk",
        name="Sandwalk API",
        status="running",
        pid=pid,
        port=port,
        rss_bytes=rss,
        cpu_percent=cpu,
        command=command,
        detail=f"v{version}" + (f" · 127.0.0.1:{port}" if port else ""),
    )
    return ServicesReport(
        processes=[api, _llama_process()],
        logs=_log_tails(),
        checked_at=datetime.now(UTC).isoformat(),
    )
