"""Render doctor checks as a rich table or a JSON-serializable report."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from rich.table import Table

from agent.config import Config
from agent.doctor.models import DoctorCheck, _status_markup


def to_table(checks: list[DoctorCheck]) -> Table:
    """Render doctor checks as a rich table."""
    table = Table(title="Fastfold Doctor")
    table.add_column("Category", style="dim")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Details")

    for check in checks:
        detail = check.detail
        if check.fix:
            detail = f"{detail} — fix: {check.fix}"
        table.add_row(
            check.category,
            check.name,
            _status_markup(check.status),
            detail,
        )

    return table


def to_report(
    checks: list[DoctorCheck] | None = None,
    *,
    session=None,
    config: Config | None = None,
    scope: str = "full",
) -> dict[str, Any]:
    """Return a JSON-serializable doctor report for CLI/API/UI consumers.

    ``scope``:
      - ``full`` (default): full readiness suite
      - ``core``: config + selected LLM + Python + sandbox only
    """
    import agent.doctor as _doctor

    if checks is not None:
        resolved = checks
    elif str(scope or "full").strip().lower() == "core":
        resolved = _doctor.run_checks_core(config=config)
    else:
        resolved = _doctor.run_checks(config=config, session=session)
    errors = sum(1 for c in resolved if c.status == "error")
    warns = sum(1 for c in resolved if c.status == "warn")
    oks = sum(1 for c in resolved if c.status == "ok")
    return {
        "ok": errors == 0,
        "checked_at": datetime.now(UTC).isoformat(),
        "summary": {
            "ok": oks,
            "warn": warns,
            "error": errors,
            "total": len(resolved),
        },
        "checks": [
            {
                "name": c.name,
                "status": c.status,
                "detail": c.detail,
                "category": c.category,
                "fix": c.fix,
            }
            for c in resolved
        ],
    }
