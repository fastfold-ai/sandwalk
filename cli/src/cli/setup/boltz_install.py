"""Boltz skill + boltz-api CLI installation for the setup wizard."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from cli.app import console, spinner
from cli.constants import BOLTZ_INSTALL_SCRIPT, BOLTZ_SKILL_SOURCE


def _find_boltz_cli_path() -> Path | None:
    """Return the first available boltz-api executable path."""
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
    """Return a compact boltz-api version string when available."""
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


def _install_boltz_skill_from_setup() -> bool:
    """Install Fastfold's boltz skill if not already present."""
    from agent.skills import install_skill, installed_skill_names

    installed = set(installed_skill_names())
    if "boltz" in installed:
        console.print("  [green]Boltz skill already installed.[/green]")
        return True

    with spinner("Installing Fastfold Boltz skill..."):
        result = install_skill(BOLTZ_SKILL_SOURCE, prefer_npx=True)
    if result.get("ok"):
        console.print(f"  [green]{result.get('summary', 'Installed boltz skill.')}[/green]")
        return True

    console.print(
        "  [yellow]Could not auto-install Boltz skill.[/yellow] "
        f"[dim]{result.get('summary', '')}[/dim]"
    )
    console.print(f"  [dim]Install manually with:[/dim] sandwalk skills add {BOLTZ_SKILL_SOURCE}")
    return False


def _ensure_boltz_cli_installed_from_setup() -> bool:
    """Install boltz-api CLI when missing."""
    current = _find_boltz_cli_path()
    if current:
        version = _boltz_cli_version(current)
        console.print(f"  [green]boltz-api ready:[/green] {current} [dim]({version})[/dim]")
        return True

    if not shutil.which("curl") or not shutil.which("sh"):
        console.print(
            "  [yellow]Could not install boltz-api automatically (missing curl/sh).[/yellow]"
        )
        console.print(
            "  [dim]Install manually:[/dim] curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"
        )
        return False

    with spinner("Installing boltz-api CLI..."):
        proc = subprocess.run(
            ["sh", "-lc", BOLTZ_INSTALL_SCRIPT],
            capture_output=True,
            text=True,
            timeout=180,
        )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        detail = detail.splitlines()[-1] if detail else "installer exited with a non-zero code"
        console.print(f"  [yellow]boltz-api install failed:[/yellow] {detail}")
        console.print(
            "  [dim]Retry manually:[/dim] curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"
        )
        return False

    installed = _find_boltz_cli_path()
    if not installed:
        console.print(
            "  [yellow]boltz-api installer completed, but executable was not found on disk.[/yellow]"
        )
        return False
    version = _boltz_cli_version(installed)
    console.print(f"  [green]Installed boltz-api:[/green] {installed} [dim]({version})[/dim]")
    return True


def _prompt_install_boltz_stack(boltz_key: str | None) -> None:
    """Offer Boltz skill + CLI installation when a Boltz key is configured."""
    if not boltz_key:
        return

    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:
        console.print(
            "  [dim]Boltz key configured. Optional setup:[/dim] "
            f"`sandwalk skills add {BOLTZ_SKILL_SOURCE}` and "
            "`curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh`."
        )
        return

    try:
        answer = input("\n  Install Boltz skill + boltz-api CLI now? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Skipped Boltz install step.[/dim]")
        return
    if answer in {"n", "no"}:
        console.print("  [dim]Skipped Boltz install step.[/dim]")
        return

    _install_boltz_skill_from_setup()
    _ensure_boltz_cli_installed_from_setup()
