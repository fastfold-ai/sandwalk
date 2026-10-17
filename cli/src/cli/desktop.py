"""`sandwalk desktop` — install the latest Sandwalk desktop app for this OS."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import typer

from cli.app import app, console

LATEST_RELEASE = "https://api.github.com/repos/fastfold-ai/sandwalk/releases/latest"
MAC_DMG_NAME = "Sandwalk-macos-arm64.dmg"


class DesktopInstallError(Exception):
    """The desktop app cannot be installed on this machine."""


def select_desktop_asset(
    assets: list[dict],
    *,
    system: str,
    machine: str,
) -> dict:
    """Pick the latest-release asset for this operating system."""
    system_name = system
    system = system.lower()
    machine = machine.lower()
    if system == "darwin":
        if machine not in {"arm64", "aarch64"}:
            raise DesktopInstallError(
                "The Mac app is built for Apple Silicon. This Mac is not."
            )
        for asset in assets:
            if asset.get("name") == MAC_DMG_NAME:
                return asset
        raise DesktopInstallError(f"Latest release has no {MAC_DMG_NAME}.")

    if system == "linux":
        arch = {
            "x86_64": "amd64",
            "amd64": "amd64",
            "aarch64": "arm64",
            "arm64": "arm64",
        }.get(machine)
        if arch is None:
            raise DesktopInstallError(
                f"No Ubuntu package for this CPU ({machine}). "
                "Sandwalk publishes amd64 and arm64 .deb packages."
            )
        suffix = f"_{arch}.deb"
        for asset in assets:
            name = str(asset.get("name") or "")
            if name.endswith(suffix):
                return asset
        raise DesktopInstallError(f"Latest release has no Ubuntu {arch} .deb.")

    raise DesktopInstallError(
        "sandwalk desktop installs the Mac app or the Ubuntu .deb. "
        f"This system is {system_name}."
    )


def _fetch_latest_assets() -> list[dict]:
    import json

    request = urllib.request.Request(
        LATEST_RELEASE,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "sandwalk",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    assets = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(assets, list):
        raise DesktopInstallError("Could not read the latest GitHub release.")
    return [asset for asset in assets if isinstance(asset, dict)]


def _download(url: str, dest: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "sandwalk"})
    with urllib.request.urlopen(request, timeout=300) as response, dest.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        raise DesktopInstallError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")


def install_dmg(dmg: Path) -> None:
    """Mount a DMG and copy Sandwalk.app to /Applications."""
    mount = Path(tempfile.mkdtemp(prefix="sandwalk-dmg-"))
    _run(["hdiutil", "attach", "-nobrowse", "-mountpoint", str(mount), str(dmg)])
    try:
        app = mount / "Sandwalk.app"
        if not app.is_dir():
            raise DesktopInstallError("The disk image does not contain Sandwalk.app.")
        dest = Path("/Applications/Sandwalk.app")
        if dest.exists():
            shutil.rmtree(dest)
        _run(["ditto", str(app), str(dest)])
    finally:
        subprocess.run(["hdiutil", "detach", str(mount)], check=False)
        shutil.rmtree(mount, ignore_errors=True)


def install_deb(deb: Path) -> None:
    """Install a .deb with apt so its dependencies are pulled in."""
    cmd = ["apt-get", "install", "-y", str(deb)]
    if os.geteuid() != 0:
        cmd = ["sudo", *cmd]
    proc = subprocess.run(
        cmd,
        check=False,
        env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"},
    )
    if proc.returncode != 0:
        raise DesktopInstallError(
            "Could not install the .deb. On Ubuntu, rerun and allow sudo."
        )


def install_desktop_app() -> str:
    """Download and install the desktop app. Returns a short success line."""
    assets = _fetch_latest_assets()
    asset = select_desktop_asset(
        assets,
        system=platform.system(),
        machine=platform.machine(),
    )
    name = str(asset.get("name") or "sandwalk")
    url = str(asset.get("browser_download_url") or "")
    if not url:
        raise DesktopInstallError(f"{name} has no download URL.")

    with tempfile.TemporaryDirectory(prefix="sandwalk-desktop-") as tmp:
        dest = Path(tmp) / name
        console.print(f"[dim]Downloading {name}…[/dim]")
        _download(url, dest)
        if name.endswith(".dmg"):
            install_dmg(dest)
            return "Installed Sandwalk.app in /Applications."
        if name.endswith(".deb"):
            install_deb(dest)
            return "Installed the Sandwalk Ubuntu package. Open Sandwalk from the app menu."
    raise DesktopInstallError(f"Do not know how to install {name}.")


@app.command("desktop")
def desktop_cmd() -> None:
    """Install the latest Sandwalk desktop app for this Mac or Ubuntu machine."""
    try:
        message = install_desktop_app()
    except DesktopInstallError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]Could not install the desktop app: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]{message}[/green]")
