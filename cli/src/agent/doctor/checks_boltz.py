"""Boltz CLI + API key readiness check.

``_locate_boltz_cli_path`` and ``_boltz_cli_version`` are patched directly in
tests via ``agent.doctor.X``, so ``_check_boltz_cli`` looks them up through the
package namespace (not local bare names) to stay patchable regardless of which
submodule defines them.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from agent.config import Config
from agent.doctor.models import DoctorCheck


def _locate_boltz_cli_path() -> Path | None:
    """Locate the boltz-api executable across common install locations."""
    candidates: list[str] = []
    in_path = shutil.which("boltz-api")
    if in_path:
        candidates.append(in_path)
    candidates.extend(
        [
            str(Path.home() / ".local" / "bin" / "boltz-api"),
            str(Path.home() / ".boltz" / "bin" / "boltz-api"),
        ]
    )
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists() and path.is_file() and os.access(str(path), os.X_OK):
            return path
    return None


def _boltz_cli_version(path: Path) -> str:
    """Return boltz-api version text (best effort)."""
    try:
        proc = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:  # noqa: BLE001
        return "unknown version"
    output = (proc.stdout or proc.stderr or "").strip()
    if not output:
        return "unknown version"
    return output.splitlines()[0].strip()


def _check_boltz_cli(cfg: Config) -> DoctorCheck:
    """Report Boltz integration readiness (key + CLI)."""
    import agent.doctor as _doctor

    boltz_key = str(cfg.get("api.boltz_api_key") or os.environ.get("BOLTZ_API_KEY") or "").strip()
    cli_path = _doctor._locate_boltz_cli_path()

    if cli_path is None and not boltz_key:
        return DoctorCheck(
            name="boltz_cli",
            status="ok",
            detail="Boltz integration not configured (optional).",
        )

    if cli_path is None and boltz_key:
        return DoctorCheck(
            name="boltz_cli",
            status="warn",
            detail=(
                "BOLTZ_API_KEY is configured but `boltz-api` CLI is missing. "
                "Install with: curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"
            ),
        )

    version = _doctor._boltz_cli_version(cli_path)
    if boltz_key:
        return DoctorCheck(
            name="boltz_cli",
            status="ok",
            detail=f"boltz-api ready at {cli_path} ({version}); BOLTZ_API_KEY configured.",
        )
    return DoctorCheck(
        name="boltz_cli",
        status="warn",
        detail=(
            f"boltz-api found at {cli_path} ({version}) but BOLTZ_API_KEY is not configured. "
            "Set with: sandwalk config set api.boltz_api_key <key> or /keys set-boltz"
        ),
    )
