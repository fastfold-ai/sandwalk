"""Config file, LLM readiness, and output/data directory checks."""

from __future__ import annotations

from pathlib import Path

from agent.config import CONFIG_DIR, CONFIG_FILE, Config
from agent.doctor.models import DoctorCheck


def check_config_and_paths(cfg: Config) -> list[DoctorCheck]:
    """Checks 1-4: config file, LLM readiness, output dir, data base dir."""
    checks: list[DoctorCheck] = []

    # 1) Config file readability (best-effort: load already handled parse errors)
    if CONFIG_FILE.exists():
        checks.append(
            DoctorCheck(
                name="config_file",
                status="ok",
                detail=f"Using {CONFIG_FILE}",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="config_file",
                status="warn",
                detail=f"No config file yet at {CONFIG_FILE} (defaults/env vars are used)",
            )
        )

    # 2) LLM configuration readiness
    llm_issue = cfg.llm_preflight_issue()
    if llm_issue:
        checks.append(DoctorCheck(name="llm", status="error", detail=llm_issue))
    else:
        checks.append(
            DoctorCheck(name="llm", status="ok", detail=cfg.llm_selection_summary())
        )

    # 3) Output directory availability
    out_dir = Path(cfg.get("sandbox.output_dir", str(Path.cwd() / "outputs")))
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        checks.append(
            DoctorCheck(name="output_dir", status="ok", detail=f"Writable: {out_dir}")
        )
    except OSError as exc:
        checks.append(
            DoctorCheck(name="output_dir", status="error", detail=f"{out_dir}: {exc}")
        )

    # 4) Data base directory availability
    data_base = Path(cfg.get("data.base", str(CONFIG_DIR / "data")))
    try:
        data_base.mkdir(parents=True, exist_ok=True)
        checks.append(
            DoctorCheck(name="data_base", status="ok", detail=f"Writable: {data_base}")
        )
    except OSError as exc:
        checks.append(
            DoctorCheck(name="data_base", status="warn", detail=f"{data_base}: {exc}")
        )

    return checks
