"""
Dataset downloader for ct.

Manages downloading and caching of common drug discovery datasets.
Supports automatic downloads for open-access datasets and guided
instructions for datasets requiring portal authentication.
"""

import gzip
import hashlib
import shutil
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, DownloadColumn, TransferSpeedColumn
from rich.table import Table

from agent.config import Config

console = Console()

# Download timeout in seconds (large files like CRISPRGeneEffect ~700MB need more time)
DOWNLOAD_TIMEOUT = 600

DATASETS = {
    "depmap": {
        "description": "DepMap CRISPR gene dependencies, mutations, cell line metadata (24Q4)",
        "files": {
            "CRISPRGeneEffect.csv": "https://ndownloader.figshare.com/files/51064667",
            "Model.csv": "https://ndownloader.figshare.com/files/51065297",
            "OmicsSomaticMutationsMatrixDamaging.csv": "https://ndownloader.figshare.com/files/51065747",
        },
        "source": "https://plus.figshare.com/articles/dataset/DepMap_24Q4_Public/27993248",
        "auto_download": True,
        "size_hint": "~550MB",
    },
    "prism": {
        "description": "PRISM cell viability screening data (Repurposing 24Q2)",
        "files": {
            "prism_LFC_COLLAPSED.csv": None,
        },
        "source": "https://depmap.org/portal/data_page/?release=PRISM+Repurposing+Public+24Q2",
        "auto_download": True,
        "note": "Built from DepMap PRISM Repurposing 24Q2 (LFC + treatment + cell-line metadata) into a long LFC table. Downloads ~150MB, produces ~80MB.",
        "size_hint": "~80MB",
    },
    "l1000": {
        "description": "L1000 landmark gene expression signatures (978 genes)",
        "files": {
            "l1000_landmark_only.parquet": None,
        },
        "source": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE92742",
        "auto_download": False,
        "note": "Run: python scripts/prepare_l1000.py to download from GEO and extract the landmark subset. The raw GEO Level-5 archive is ~20GB; the extracted landmark parquet is ~2.6GB.",
        "size_hint": "~2.6GB",
    },
    "msigdb": {
        "description": "MSigDB gene set collections (Hallmark, KEGG, Reactome, GO)",
        "files": {
            "h.all.v2024.1.Hs.json": "https://data.broadinstitute.org/gsea-msigdb/msigdb/release/2024.1.Hs/h.all.v2024.1.Hs.json",
            "c2.cp.kegg_legacy.v2024.1.Hs.json": "https://data.broadinstitute.org/gsea-msigdb/msigdb/release/2024.1.Hs/c2.cp.kegg_legacy.v2024.1.Hs.json",
            "c2.cp.reactome.v2024.1.Hs.json": "https://data.broadinstitute.org/gsea-msigdb/msigdb/release/2024.1.Hs/c2.cp.reactome.v2024.1.Hs.json",
            "c5.go.bp.v2024.1.Hs.json": "https://data.broadinstitute.org/gsea-msigdb/msigdb/release/2024.1.Hs/c5.go.bp.v2024.1.Hs.json",
        },
        "source": "https://www.gsea-msigdb.org/gsea/msigdb/",
        "auto_download": True,
        "size_hint": "~10MB",
    },
    "string": {
        "description": "STRING protein-protein interaction network (human)",
        "files": {
            "9606.protein.links.v12.0.txt.gz": "https://stringdb-downloads.org/download/protein.links.v12.0/9606.protein.links.v12.0.txt.gz",
        },
        "source": "https://string-db.org/",
        "auto_download": True,
        "size_hint": "~80MB",
    },
    "alphafold": {
        "description": "AlphaFold predicted protein structures (downloaded on demand per-protein)",
        "files": {},
        "source": "https://alphafold.ebi.ac.uk/",
        "auto_download": False,
        "note": "Structures are fetched on-demand by structure.alphafold_fetch tool.",
    },
}


def _format_size(num_bytes: int) -> str:
    """Render a byte count as a human-readable KB/MB/GB string."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{int(size)}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def _dataset_disk_size(path: Path, expected: set[str]) -> int:
    """Sum the on-disk bytes of a dataset's expected files that exist in ``path``."""
    if not path.exists():
        return 0
    total = 0
    for f in path.iterdir():
        if f.is_file() and (not expected or f.name in expected):
            try:
                total += f.stat().st_size
            except OSError:
                continue
    return total


def _download_file(url: str, dest: Path, desc: str = None) -> bool:
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


def download_dataset(name: str, output: Path = None):
    """Download a dataset."""
    if name == "--all" or name == "all":
        download_all(output)
        return

    if name not in DATASETS:
        console.print(f"[red]Unknown dataset: {name}[/red]")
        console.print(f"Available: {', '.join(DATASETS.keys())}")
        return

    ds = DATASETS[name]
    cfg = Config.load()
    dest = output or Path(cfg.get("data.base")) / name
    dest.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[cyan]{name}:[/cyan] {ds['description']}")
    if ds.get("size_hint"):
        console.print(f"  Size: {ds['size_hint']}")
    console.print(f"  Destination: {dest}")

    # PRISM needs a join of several figshare files into the long LFC table the
    # tools expect, so it uses a dedicated preparation path.
    if name == "prism":
        _download_prism(dest, cfg)
        return

    if not ds.get("auto_download"):
        # Manual download required
        if "note" in ds:
            console.print(f"  [yellow]{ds['note']}[/yellow]")
        console.print(f"  Source: {ds['source']}")
        console.print(f"  Files needed:")
        for fname in ds["files"]:
            fpath = dest / fname
            status = "[green]found[/green]" if fpath.exists() else "[red]missing[/red]"
            console.print(f"    {fname} — {status}")
        console.print(f"\n  Download from {ds['source']} and place in {dest}/")
        console.print(f"  Then run: [cyan]fastfold config set data.{name} {dest}[/cyan]")
        return

    # Automatic download
    downloaded = 0
    skipped = 0
    failed = 0

    for fname, url in ds["files"].items():
        fpath = dest / fname
        if fpath.exists():
            console.print(f"  [dim]{fname} — already exists, skipping[/dim]")
            skipped += 1
            continue

        if url is None:
            console.print(f"  [yellow]{fname} — no download URL, skip[/yellow]")
            failed += 1
            continue

        if _download_file(url, fpath, fname):
            downloaded += 1
        else:
            failed += 1

    # Summary
    total = len(ds["files"])
    console.print(f"\n  [green]{downloaded} downloaded[/green], {skipped} skipped, ", end="")
    if failed:
        console.print(f"[red]{failed} failed[/red]")
    else:
        console.print(f"0 failed")

    # Auto-configure data path after successful download
    if downloaded > 0 or skipped > 0:
        cfg.set(f"data.{name}", str(dest))
        cfg.save()
        console.print(f"  [green]Auto-configured data.{name} = {dest}[/green]")


# DepMap PRISM Repurposing 24Q2 figshare files (article 25917643).
_PRISM_FILES = {
    "lfc": (
        "Repurposing_Public_24Q2_LFC_COLLAPSED.csv",
        "https://ndownloader.figshare.com/files/46631056",
    ),
    "treatment": (
        "Repurposing_Public_24Q2_Treatment_Meta_Data.csv",
        "https://ndownloader.figshare.com/files/46631146",
    ),
    "cells": (
        "Repurposing_Public_24Q2_Cell_Line_Meta_Data.csv",
        "https://ndownloader.figshare.com/files/46630978",
    ),
}


def _download_prism(dest: Path, cfg: Config) -> bool:
    """Download PRISM Repurposing 24Q2 and build the long LFC table.

    Produces ``prism_LFC_COLLAPSED.csv`` with columns
    ``pert_name, pert_dose, ccle_name, LFC`` — the schema the viability/biomarker
    tools expect. Joins the raw LFC matrix with treatment (broad_id → name) and
    cell-line (depmap_id → ccle_name) metadata from figshare.
    """
    final = dest / "prism_LFC_COLLAPSED.csv"
    if final.exists():
        console.print("  [dim]prism_LFC_COLLAPSED.csv already exists, skipping[/dim]")
        cfg.set("data.prism", str(dest))
        cfg.save()
        return True

    raw_dir = dest / "_prism_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for key, (fname, url) in _PRISM_FILES.items():
        target = raw_dir / fname
        if not target.exists():
            if not _download_file(url, target, fname):
                console.print(f"  [red]Failed to download {fname}[/red]")
                return False
        paths[key] = target

    console.print("  Building prism_LFC_COLLAPSED.csv (joining metadata)…")
    try:
        import pandas as pd

        lfc = pd.read_csv(paths["lfc"])
        treatment = pd.read_csv(paths["treatment"], usecols=["broad_id", "name"])
        cells = pd.read_csv(paths["cells"], usecols=["depmap_id", "ccle_name"])

        name_map = treatment.drop_duplicates("broad_id")
        ccle_map = cells.drop_duplicates("depmap_id")

        # row_id looks like "ACH-000001::P946.2::PR500B::REP300"; the first
        # segment is the DepMap model id.
        lfc["depmap_id"] = lfc["row_id"].astype(str).str.split("::").str[0]

        merged = lfc.merge(name_map, on="broad_id", how="left").merge(
            ccle_map, on="depmap_id", how="left"
        )
        out = merged.rename(columns={"name": "pert_name", "dose": "pert_dose"})[
            ["pert_name", "pert_dose", "ccle_name", "LFC"]
        ]
        out = out.dropna(subset=["pert_name", "ccle_name"])
        out.to_csv(final, index=False)
    except Exception as exc:  # noqa: BLE001
        console.print(f"  [red]Failed to build PRISM table: {exc}[/red]")
        return False

    console.print(
        f"  [green]Wrote {final.name} ({_format_size(final.stat().st_size)})[/green]"
    )

    # Clean up the large intermediate files.
    try:
        for path in paths.values():
            path.unlink(missing_ok=True)
        raw_dir.rmdir()
    except OSError:
        pass

    cfg.set("data.prism", str(dest))
    cfg.save()
    console.print(f"  [green]Auto-configured data.prism = {dest}[/green]")
    return True


def download_all(output: Path = None):
    """Download all auto-downloadable datasets."""
    auto_datasets = [name for name, ds in DATASETS.items() if ds.get("auto_download")]
    console.print(f"[cyan]Downloading {len(auto_datasets)} datasets: {', '.join(auto_datasets)}[/cyan]")
    for name in auto_datasets:
        download_dataset(name, output=output)


def dataset_catalog() -> Table:
    """List all known datasets with description, size, and download mode."""
    table = Table(title="Available Datasets")
    table.add_column("Dataset", style="cyan", no_wrap=True)
    table.add_column("Auto-DL")
    table.add_column("Size", style="dim")
    table.add_column("Description", style="white")

    for name, ds in DATASETS.items():
        auto = "[green]yes[/green]" if ds.get("auto_download") else "[dim]manual[/dim]"
        size = ds.get("size_hint", "-") or "-"
        table.add_row(name, auto, size, ds.get("description", ""))

    return table


def list_dataset_records() -> list[dict]:
    """Return structured status records for every known dataset.

    Shared by the CLI status table and the web ``/v1/datasets`` API so both stay
    consistent. Each record: id, description, status, files_found/expected,
    size_bytes, size_display, auto_download, path, source, note.
    """
    cfg = Config.load()
    base = Path(cfg.get("data.base"))
    records: list[dict] = []

    for name, ds in DATASETS.items():
        custom_path = cfg.get(f"data.{name}")
        path = Path(custom_path) if custom_path else base / name

        expected = set(ds["files"].keys())
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
            size_display = ds.get("size_hint") or "-"
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

        expected = set(ds["files"].keys())
        found = set()
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
            size_str = ds.get("size_hint") or "-"

        auto = "[green]yes[/green]" if ds.get("auto_download") else "[dim]manual[/dim]"
        table.add_row(name, status, files_str, size_str, auto)

    return table
