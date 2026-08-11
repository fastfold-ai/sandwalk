"""Dataset status/catalog reporting and removal."""

from pathlib import Path
from typing import Any

from rich.table import Table

from data.downloader.catalog import DATASETS
from data.downloader.util import _dataset_disk_size, _format_size


def dataset_catalog() -> Table:
    """List all known datasets with description, size, and download mode."""
    table = Table(title="Available Datasets")
    table.add_column("Dataset", style="cyan", no_wrap=True)
    table.add_column("Auto-DL")
    table.add_column("Size", style="dim")
    table.add_column("Description", style="white")

    for name, ds in DATASETS.items():
        auto = "[green]yes[/green]" if ds.get("auto_download") else "[dim]manual[/dim]"
        size = str(ds.get("size_hint") or "-")
        table.add_row(name, auto, size, str(ds.get("description") or ""))

    return table


def list_dataset_records() -> list[dict[str, Any]]:
    """Return structured status records for every known dataset.

    Shared by the CLI status table and the web ``/v1/datasets`` API so both stay
    consistent. Each record: id, description, status, files_found/expected,
    size_bytes, size_display, auto_download, path, source, note.
    """
    from data.downloader import Config

    cfg = Config.load()
    base = Path(cfg.get("data.base"))
    records: list[dict[str, Any]] = []

    for name, ds in DATASETS.items():
        custom_path = cfg.get(f"data.{name}")
        path = Path(custom_path) if custom_path else base / name

        files = ds["files"]
        assert isinstance(files, dict)
        expected = set(files.keys())
        found: set[str] = set()
        if path.exists():
            existing = {f.name for f in path.iterdir() if f.is_file()}
            found = expected & existing

        if not expected:
            status = "on-demand"
        elif found == expected:
            status = "complete"
        elif found:
            status = "partial"
        else:
            status = "missing"

        disk_bytes = _dataset_disk_size(path, expected)
        if disk_bytes > 0:
            size_display = _format_size(disk_bytes)
            size_bytes: int | None = disk_bytes
        else:
            size_display = str(ds.get("size_hint") or "-")
            size_bytes = None

        records.append(
            {
                "id": name,
                "description": str(ds.get("description") or ""),
                "status": status,
                "files_found": len(found),
                "files_expected": len(expected),
                "size_bytes": size_bytes,
                "size_display": size_display,
                "auto_download": bool(ds.get("auto_download")),
                "path": str(path),
                "source": str(ds.get("source") or "") or None,
                "note": str(ds.get("note") or "") or None,
            }
        )
    return records


def dataset_status() -> Table:
    """Check which datasets are available locally."""
    from data.downloader import Config

    cfg = Config.load()
    base = Path(cfg.get("data.base"))

    table = Table(title="Dataset Status")
    table.add_column("Dataset", style="cyan")
    table.add_column("Status")
    table.add_column("Files", style="dim")
    table.add_column("Size", style="dim")
    table.add_column("Auto-DL")

    for name, ds in DATASETS.items():
        # Check custom config path first, then default location
        custom_path = cfg.get(f"data.{name}")
        path = Path(custom_path) if custom_path else base / name

        files = ds["files"]
        assert isinstance(files, dict)
        expected = set(files.keys())
        found: set[str] = set()
        if path.exists():
            existing = {f.name for f in path.iterdir() if f.is_file()}
            found = expected & existing

        if not expected:
            status = "[dim]on-demand[/dim]"
            files_str = "-"
        elif found == expected:
            status = "[green]complete[/green]"
            files_str = f"{len(found)}/{len(expected)}"
        elif found:
            status = "[yellow]partial[/yellow]"
            files_str = f"{len(found)}/{len(expected)}"
        else:
            status = "[red]missing[/red]"
            files_str = f"0/{len(expected)}"

        # Prefer actual on-disk size when any files are present; otherwise fall
        # back to the published estimate, else "-".
        disk_bytes = _dataset_disk_size(path, expected)
        if disk_bytes > 0:
            size_str = _format_size(disk_bytes)
        else:
            size_str = str(ds.get("size_hint") or "-")

        auto = "[green]yes[/green]" if ds.get("auto_download") else "[dim]manual[/dim]"
        table.add_row(name, status, files_str, size_str, auto)

    return table


