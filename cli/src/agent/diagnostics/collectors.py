"""System/config/skills/log collectors for the diagnostics bundle."""

from __future__ import annotations

import os
import platform
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.config import CONFIG_DIR, CONFIG_FILE, Config

from .logging_setup import LOGS_DIR, MAX_LOG_BYTES, MAX_LOG_FILES
from .redact import _redact_obj, _redact_text


def _system_info(version: str) -> dict[str, Any]:
    return {
        "service": "sandwalk",
        "version": version,
        "generated_at": datetime.now(UTC).isoformat(),
        "platform": platform.system().lower(),
        "arch": platform.machine(),
        "os_release": platform.release(),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "executable": _redact_text(sys.executable),
        "hostname": _redact_text(socket.gethostname()),
        "cwd": _redact_text(str(Path.cwd())),
        "config_dir": _redact_text(str(CONFIG_DIR)),
        "config_file_exists": CONFIG_FILE.exists(),
        "pid": os.getpid(),
    }


def _redacted_config(cfg: Config) -> dict[str, Any]:
    raw = dict(getattr(cfg, "_data", {}) or {})
    return _redact_obj(raw)


def _skills_summary() -> dict[str, Any]:
    try:
        from agent.skills import list_skills

        skills = list_skills()
        by_source: dict[str, int] = {}
        enabled = 0
        for skill in skills:
            if skill.enabled:
                enabled += 1
            source = str(skill.source or "unknown")
            by_source[source] = by_source.get(source, 0) + 1
        return {
            "total": len(skills),
            "enabled": enabled,
            "disabled": len(skills) - enabled,
            "by_source": by_source,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def _collect_log_files() -> list[Path]:
    if not LOGS_DIR.exists():
        return []
    candidates = [
        path
        for path in LOGS_DIR.iterdir()
        if path.is_file()
        and (
            path.suffix in {".log", ".txt"}
            or path.name.startswith("agent-server.log")
        )
    ]
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[:MAX_LOG_FILES]


def _read_log_tail(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return f"<unable to read {path.name}: {exc}>"
    if len(data) > MAX_LOG_BYTES:
        data = data[-MAX_LOG_BYTES:]
        prefix = b"<truncated to last 2MiB>\n"
        data = prefix + data
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        text = data.decode("latin-1", errors="replace")
    return _redact_text(text)
