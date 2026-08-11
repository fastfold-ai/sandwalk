"""Low-level file download with a progress bar."""

from pathlib import Path

import httpx
from rich.progress import BarColumn, DownloadColumn, Progress, SpinnerColumn, TransferSpeedColumn

from data.downloader.catalog import DOWNLOAD_TIMEOUT, console


def _download_file(url: str, dest: Path, desc: str | None = None) -> bool:
    """Download a file with progress bar. Returns True on success."""
    desc = desc or dest.name
    try:
        with httpx.stream("GET", url, timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as resp:
            if resp.status_code != 200:
                console.print(f"  [red]HTTP {resp.status_code} for {url}[/red]")
                return False

            total = int(resp.headers.get("content-length", 0))

            with Progress(
                SpinnerColumn(),
                "[progress.description]{task.description}",
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(f"  {desc}", total=total or None)
                with open(dest, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        progress.advance(task, len(chunk))

        return True
    except httpx.HTTPError as e:
        console.print(f"  [red]Download failed: {e}[/red]")
        if dest.exists():
            dest.unlink()
        return False
