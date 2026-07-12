"""Build a shareable diagnostics zip for support (Operon-style).

Includes system info, doctor report, redacted config, and recent log files.
Excludes conversations and credential values.
"""

from __future__ import annotations

import io
import json
import logging
import os
import platform
import re
import socket
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from agent.config import CONFIG_DIR, CONFIG_FILE, Config

logger = logging.getLogger("diagnostics")

LOGS_DIR = CONFIG_DIR / "logs"
MAX_LOG_FILES = 12
MAX_LOG_BYTES = 2 * 1024 * 1024  # 2 MiB per log file

_SECRET_KEY_RE = re.compile(
    r"(key|token|secret|password|passwd|authorization|api[_-]?key|oidc)",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(sk-[A-Za-z0-9_\-]{8,}|sk_ant-[A-Za-z0-9_\-]{8,}|"
    r"sk_bc_[A-Za-z0-9_\-]{8,}|sk-fdg[A-Za-z0-9_\-]{8,}|"
    r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,})"
)
_HOME = str(Path.home())


def ensure_logging_configured() -> Path:
    """Attach a rotating file handler under ~/.fastfold-cli/logs if missing.

    Captures app + uvicorn loggers. Quiets noisy HTTP client libraries so doctor
    connectivity probes do not flood the diagnostics bundle.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / "agent-server.log"
    root = logging.getLogger()
    marker = "fastfold-agent-server-file"
    for handler in root.handlers:
        if getattr(handler, "_fastfold_marker", None) == marker:
            _quiet_noisy_loggers()
            return log_path

    from logging.handlers import RotatingFileHandler

    handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    handler._fastfold_marker = marker  # type: ignore[attr-defined]
    root.addHandler(handler)
    if root.level > logging.INFO or root.level == logging.NOTSET:
        root.setLevel(logging.INFO)

    # Make sure uvicorn loggers propagate into the root file handler.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "agent_server", "fastapi"):
        logger_obj = logging.getLogger(name)
        logger_obj.setLevel(logging.INFO)
        logger_obj.propagate = True

    _quiet_noisy_loggers()
    logging.getLogger("agent_server").info(
        "File logging enabled at %s", log_path
    )
    return log_path


def _quiet_noisy_loggers() -> None:
    for name in ("httpx", "httpcore", "urllib3", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)


def uvicorn_log_config(log_path: Path) -> dict:
    """Logging dict for uvicorn that mirrors console + file handlers."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": None,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
            },
            "file": {
                "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "formatter": "file",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(log_path),
                "maxBytes": 5 * 1024 * 1024,
                "backupCount": 5,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default", "file"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["default", "file"], "level": "INFO", "propagate": False},
            "uvicorn.access": {"handlers": ["access", "file"], "level": "INFO", "propagate": False},
            "httpx": {"level": "WARNING", "propagate": True},
            "httpcore": {"level": "WARNING", "propagate": True},
        },
        "root": {"handlers": ["default", "file"], "level": "INFO"},
    }


def _redact_text(text: str) -> str:
    value = text.replace(_HOME, "~")
    value = _SECRET_VALUE_RE.sub("<redacted-secret>", value)
    # Common absolute project paths → keep basename-ish but hide username home.
    value = re.sub(r"/Users/[^/\s]+", "~", value)
    value = re.sub(r"/home/[^/\s]+", "~", value)
    return value


def _redact_obj(value: Any, *, key: str = "") -> Any:
    if isinstance(value, dict):
        return {k: _redact_obj(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_obj(item, key=key) for item in value]
    if isinstance(value, str):
        if _SECRET_KEY_RE.search(key) and value.strip():
            return "<redacted>"
        return _redact_text(value)
    return value


def _system_info(version: str) -> dict[str, Any]:
    return {
        "service": "fastfold-agent-cli",
        "version": version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
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


def build_diagnostics_zip(
    *,
    version: str,
    doctor_report: Optional[dict[str, Any]] = None,
    ui_diagnostics: Optional[dict[str, Any]] = None,
) -> tuple[bytes, str]:
    """Return (zip_bytes, filename) for a diagnostics bundle."""
    ensure_logging_configured()
    cfg = Config.load()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root_name = f"fastfold-diagnostics-{stamp}"
    filename = f"{root_name}.zip"

    if doctor_report is None:
        from agent.doctor import to_report

        doctor_report = to_report(config=cfg)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        def write_json(rel: str, payload: Any) -> None:
            zf.writestr(
                f"{root_name}/{rel}",
                json.dumps(payload, indent=2, default=str) + "\n",
            )

        write_json("system-info.json", _system_info(version))
        write_json("doctor-report.json", doctor_report)
        write_json("config.redacted.json", _redacted_config(cfg))
        write_json("skills-summary.json", _skills_summary())
        write_json(
            "manifest.json",
            {
                "format": "fastfold-diagnostics/v1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "includes": [
                    "system-info.json",
                    "doctor-report.json",
                    "config.redacted.json",
                    "skills-summary.json",
                    "logs/",
                ],
                "excludes": [
                    "conversation transcripts",
                    "raw API keys / secrets",
                    "full skill contents",
                ],
                "note": (
                    "Paths and hostnames are redacted. Review the bundle before sharing."
                ),
            },
        )
        if ui_diagnostics:
            write_json("ui-diagnostics.json", _redact_obj(ui_diagnostics))

        log_files = _collect_log_files()
        if not log_files:
            zf.writestr(
                f"{root_name}/logs/README.txt",
                "No log files found yet under ~/.fastfold-cli/logs.\n"
                "Restart `fastfold serve` once to begin writing agent-server.log.\n",
            )
        for path in log_files:
            zf.writestr(f"{root_name}/logs/{path.name}", _read_log_tail(path))

        zf.writestr(
            f"{root_name}/README.md",
            (
                "# Fastfold diagnostics\n\n"
                "Bundles system info, doctor checks, redacted config, skill counts, "
                "and recent server logs for support.\n\n"
                "- File paths and host names are redacted.\n"
                "- Conversations and credentials are not included.\n"
                "- Review the bundle before sharing.\n"
            ),
        )

    return buf.getvalue(), filename
