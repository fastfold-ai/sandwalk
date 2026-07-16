"""Top-level download orchestration: single dataset and "download all"."""

from pathlib import Path

from data.downloader.catalog import console, DATASETS


def download_dataset(name: str, output: Path | None = None) -> None:
    """Download a dataset."""
    from data.downloader import Config, _download_file, _download_prism, download_all

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
        console.print("  Files needed:")
        files = ds["files"]
        assert isinstance(files, dict)
        for fname in files:
            fpath = dest / fname
            status = "[green]found[/green]" if fpath.exists() else "[red]missing[/red]"
            console.print(f"    {fname} — {status}")
        console.print(f"\n  Download from {ds['source']} and place in {dest}/")
        console.print(f"  Then run: [cyan]sandwalk config set data.{name} {dest}[/cyan]")
        return

    # Automatic download
    downloaded = 0
    skipped = 0
    failed = 0

    files = ds["files"]
    assert isinstance(files, dict)
    for fname, url in files.items():
        fpath = dest / fname
        if fpath.exists():
            console.print(f"  [dim]{fname} — already exists, skipping[/dim]")
            skipped += 1
            continue

        if url is None:
            console.print(f"  [yellow]{fname} — no download URL, skip[/yellow]")
            failed += 1
            continue

        if _download_file(str(url), fpath, str(fname)):
            downloaded += 1
        else:
            failed += 1

    # Summary
    console.print(f"\n  [green]{downloaded} downloaded[/green], {skipped} skipped, ", end="")
    if failed:
        console.print(f"[red]{failed} failed[/red]")
    else:
        console.print("0 failed")

    # Auto-configure data path after successful download
    if downloaded > 0 or skipped > 0:
        cfg.set(f"data.{name}", str(dest))
        cfg.save()
        console.print(f"  [green]Auto-configured data.{name} = {dest}[/green]")


def download_all(output: Path | None = None) -> None:
    """Download all auto-downloadable datasets."""
    from data.downloader import download_dataset as _download_dataset

    auto_datasets = [name for name, ds in DATASETS.items() if ds.get("auto_download")]
    console.print(f"[cyan]Downloading {len(auto_datasets)} datasets: {', '.join(auto_datasets)}[/cyan]")
    for name in auto_datasets:
        _download_dataset(name, output=output)
