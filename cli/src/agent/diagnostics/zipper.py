"""Assembles the diagnostics zip bundle from collected sections."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Any

from agent.config import Config

from .collectors import (
    _collect_log_files,
    _read_log_tail,
    _redacted_config,
    _skills_summary,
    _system_info,
)
from .logging_setup import ensure_logging_configured
from .redact import _redact_obj


def build_diagnostics_zip(
    *,
    version: str,
    doctor_report: dict[str, Any] | None = None,
    ui_diagnostics: dict[str, Any] | None = None,
) -> tuple[bytes, str]:
    """Return (zip_bytes, filename) for a diagnostics bundle."""
    ensure_logging_configured()
    cfg = Config.load()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
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
                "generated_at": datetime.now(UTC).isoformat(),
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
                "No log files found yet under ~/.sandwalk/logs.\n"
                "Restart `sandwalk serve` once to begin writing agent-server.log.\n",
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
