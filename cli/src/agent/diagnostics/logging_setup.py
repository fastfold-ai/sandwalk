"""File logging setup shared by the CLI server and uvicorn."""

from __future__ import annotations

import logging
from pathlib import Path

from agent.config import CONFIG_DIR

LOGS_DIR = CONFIG_DIR / "logs"
MAX_LOG_FILES = 12
MAX_LOG_BYTES = 2 * 1024 * 1024  # 2 MiB per log file


def _quiet_noisy_loggers() -> None:
    for name in ("httpx", "httpcore", "urllib3", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)


def ensure_logging_configured() -> Path:
    """Attach a rotating file handler under ~/.sandwalk/logs if missing.

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
