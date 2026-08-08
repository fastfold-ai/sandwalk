"""Modal CLI + credentials check for the modal-auto-research-skills skills.

Covers ``modal-basic-skills``, ``modal-gpu-dev``, ``modal-gpu-experiment``, and
``sub-agents`` (installed from ``modal-projects/modal-auto-research-skills``).
All four call the ``modal`` CLI directly and need the same Modal credentials
already used by Modal Sandbox (``MODAL_TOKEN_ID`` / ``MODAL_TOKEN_SECRET``),
so this adapter reuses ``agent.sandbox_deps`` / ``agent.sandbox_probe.tokens``
rather than re-implementing install/credential checks.
"""

from __future__ import annotations

import importlib
import shutil

from agent.skills.deps.models import (
    SkillDepCheck,
    SkillDepInstallResult,
    SkillDepSetupStep,
    SkillDepStatus,
)

ADAPTER_ID = "modal-research"
SKILL_NAMES = frozenset(
    {"modal-basic-skills", "modal-gpu-dev", "modal-gpu-experiment", "sub-agents"}
)


def _modal_importable() -> tuple[bool, str]:
    try:
        importlib.import_module("modal")
    except ImportError as exc:
        return False, str(exc)
    return True, "modal Python package importable"


def _modal_cli_path() -> str | None:
    return shutil.which("modal")


def preferred_command() -> str:
    """Shell command agents should prefer for the Modal CLI."""
    if _modal_cli_path():
        return "modal"
    return "python -m modal"


def setup_steps() -> list[SkillDepSetupStep]:
    return [
        SkillDepSetupStep(
            title="Install the Modal CLI",
            body=(
                "These skills call the `modal` CLI directly (run / deploy / "
                "volume / sandbox commands). Sandwalk installs the `modal` "
                "Python package, which ships the CLI — click Install "
                "dependencies below, or run `pip install modal` yourself."
            ),
        ),
        SkillDepSetupStep(
            title="Set Modal credentials",
            body=(
                "MODAL_TOKEN_ID / MODAL_TOKEN_SECRET are shared with Modal "
                "Sandbox — set them once in Integrations → Modal (or "
                "Sandbox → Modal Sandbox). Get a token at "
                "https://modal.com/settings/tokens."
            ),
        ),
        SkillDepSetupStep(
            title="Run health check",
            body="Verify the CLI is on PATH and credentials are configured.",
        ),
    ]


def doctor() -> SkillDepStatus:
    from agent.sandbox_probe.tokens import modal_tokens_present

    checks: list[SkillDepCheck] = []

    importable, detail = _modal_importable()
    cli_path = _modal_cli_path()
    if importable:
        suffix = f" ({cli_path})" if cli_path else ""
        checks.append(
            SkillDepCheck(
                name="modal_package",
                status="ok",
                detail=f"modal package importable{suffix}",
            )
        )
    else:
        checks.append(
            SkillDepCheck(
                name="modal_package",
                status="missing",
                detail=detail,
                fix="pip install modal",
            )
        )

    if cli_path:
        checks.append(
            SkillDepCheck(
                name="modal_cli", status="ok", detail=f"modal CLI: {cli_path}"
            )
        )
    elif importable:
        checks.append(
            SkillDepCheck(
                name="modal_cli",
                status="warn",
                detail="modal CLI not found on PATH; falling back to `python -m modal`",
                fix="Ensure the environment's script/bin directory is on PATH",
            )
        )
    else:
        checks.append(
            SkillDepCheck(
                name="modal_cli",
                status="missing",
                detail="modal CLI not found on PATH",
                fix="pip install modal",
            )
        )

    tokens_ok, tokens_detail = modal_tokens_present()
    checks.append(
        SkillDepCheck(
            name="modal_credentials",
            status="ok" if tokens_ok else "missing",
            detail=tokens_detail,
            fix=(
                ""
                if tokens_ok
                else "Set MODAL_TOKEN_ID / MODAL_TOKEN_SECRET in Integrations → Modal"
            ),
        )
    )

    if any(c.status == "error" for c in checks):
        status: str = "error"
        summary = "Modal research skills health check failed"
    elif any(c.status == "missing" for c in checks):
        status = "missing"
        summary = "Modal CLI and/or credentials are not configured"
    else:
        status = "ok"
        summary = "Modal CLI and credentials are healthy"

    return SkillDepStatus(
        adapter_id=ADAPTER_ID,
        skill_name="modal-basic-skills",
        status=status,  # type: ignore[arg-type]
        summary=summary,
        command=preferred_command(),
        checks=checks,
        setup_steps=setup_steps(),
    )


def install(*, force: bool = False) -> SkillDepInstallResult:
    from agent.sandbox_deps import ensure_modal_deps

    ok, detail = ensure_modal_deps(auto_install=True)
    if not ok:
        status = doctor()
        return SkillDepInstallResult(ok=False, summary=detail, status=status)

    status = doctor()
    verb = "Reinstalled" if force else "Installed"
    return SkillDepInstallResult(
        ok=status.status != "error",
        summary=f"{verb} the Modal CLI ({detail})",
        status=status,
    )
