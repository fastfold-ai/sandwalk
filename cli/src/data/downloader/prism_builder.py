"""Builds the long-form PRISM LFC table from DepMap Repurposing 24Q2 figshare files."""

from pathlib import Path

from agent.config import Config
from data.downloader.catalog import console
from data.downloader.util import _format_size

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
    from data.downloader import _download_file

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
