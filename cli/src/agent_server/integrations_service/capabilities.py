"""Install and resolve integration-owned local capabilities."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from agent_server.models import IntegrationProvider

BOLTZ_INSTALLER_URL = "https://install.boltz.bio/boltz-api/install.sh"


def find_boltz_cli() -> Path | None:
    candidates = [
        shutil.which("boltz-api"),
        str(Path.home() / ".local" / "bin" / "boltz-api"),
        str(Path.home() / ".boltz" / "bin" / "boltz-api"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


def install_boltz_cli() -> Path:
    existing = find_boltz_cli()
    if existing:
        return existing
    shell = shutil.which("sh")
    if not shell:
        raise ValueError("A POSIX shell is required to install boltz-api.")
    try:
        response = httpx.get(BOLTZ_INSTALLER_URL, follow_redirects=True, timeout=30)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(f"Could not download the boltz-api installer: {exc}") from exc
    result = subprocess.run(
        [shell],
        input=response.text,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        if detail:
            detail = detail.splitlines()[-1]
        raise ValueError(
            f"boltz-api installation failed: {detail or 'installer exited with an error'}"
        )
    installed = find_boltz_cli()
    if installed is None:
        raise ValueError(
            "The boltz-api installer finished, but the executable was not found."
        )
    return installed


class CapabilityMixin:
    def install_capability(
        self,
        integration_key: str,
        capability_id: str,
    ) -> IntegrationProvider:
        if integration_key != "boltz" or capability_id != "boltz-api-cli":
            raise KeyError((integration_key, capability_id))
        install_boltz_cli()
        provider = self.get(integration_key)
        if provider is None:
            raise KeyError(integration_key)
        return provider
