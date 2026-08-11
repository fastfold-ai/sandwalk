"""Key-dataset presence and downloads-directory writability checks."""

from __future__ import annotations

from pathlib import Path

from agent.config import CONFIG_DIR, Config
from agent.doctor.models import DoctorCheck

# Key datasets and the file patterns used by loaders
_KEY_DATASETS = {
    "depmap": ("CRISPRGeneEffect.csv", ["", "depmap"]),
    "prism": ("prism_LFC_COLLAPSED.csv", ["", "prism"]),
    "l1000": ("l1000_landmark_only.parquet", ["", "l1000"]),
}


def _check_data_availability(cfg: Config) -> DoctorCheck:
    """Check whether key datasets can be found on disk."""
    data_base = Path(cfg.get("data.base", str(CONFIG_DIR / "data")))
    search_dirs = [data_base]
    # Also check ct-data sister project
    ct_data = Path.home() / "Projects" / "CellType" / "ct-data"
    if ct_data.exists():
        search_dirs.append(ct_data)

    found = []
    missing = []
    for name, (filename, subdirs) in _KEY_DATASETS.items():
        located = False
        stem = Path(filename).stem
        for base_dir in search_dirs:
            for sub in subdirs:
                d = base_dir / sub if sub else base_dir
                if (d / filename).exists():
                    located = True
                    break
                parquet = d / f"{stem}.parquet"
                if parquet.exists():
                    located = True
                    break
            if located:
                break
        if located:
            found.append(name)
        else:
            missing.append(name)

    if not missing:
        return DoctorCheck(
            name="data_availability",
            status="ok",
            detail=f"Key datasets found: {', '.join(sorted(found))}",
        )
    if found:
        return DoctorCheck(
            name="data_availability",
            status="warn",
            detail=f"Missing datasets: {', '.join(sorted(missing))} (found: {', '.join(sorted(found))}). Run: sandwalk data pull <name>",
        )
    return DoctorCheck(
        name="data_availability",
        status="warn",
        detail=f"No key datasets found ({', '.join(sorted(missing))}). Run: sandwalk data pull depmap",
    )


def _check_downloads_dir() -> DoctorCheck:
    """Verify ~/.sandwalk/downloads/ exists and is writable."""
    downloads = CONFIG_DIR / "downloads"
    try:
        downloads.mkdir(parents=True, exist_ok=True)
        return DoctorCheck(
            name="downloads_dir",
            status="ok",
            detail=f"Writable: {downloads}",
        )
    except OSError as exc:
        return DoctorCheck(
            name="downloads_dir",
            status="warn",
            detail=f"{downloads}: {exc}",
        )
