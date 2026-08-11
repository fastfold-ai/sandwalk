"""Removal of locally cached dataset files and config."""

from pathlib import Path
from typing import Any

from data.downloader.catalog import DATASETS


def remove_dataset(name: str) -> dict[str, Any]:
    """Delete local files for a dataset and clear its ``data.<name>`` config.

    Returns a status dict compatible with ``list_dataset_records`` entries after
    removal. Raises ``KeyError`` for unknown dataset ids.
    """
    import shutil

    from data.downloader import Config, list_dataset_records as _list_dataset_records

    if name not in DATASETS:
        raise KeyError(name)

    cfg = Config.load()
    base = Path(str(cfg.get("data.base") or "")).expanduser().resolve()
    custom_raw = cfg.get(f"data.{name}")
    custom = str(custom_raw or "").strip()
    path = Path(custom).expanduser().resolve() if custom else (base / name).resolve()

    # Only delete paths that belong to this dataset under the data base, or the
    # explicitly configured dataset path.
    allowed = {(base / name).resolve()}
    if custom:
        allowed.add(Path(custom).expanduser().resolve())
    try:
        path.relative_to(base)
        under_base = True
    except ValueError:
        under_base = False
    if path not in allowed and not under_base:
        raise ValueError(
            f"Refusing to remove dataset path outside data base: {path}"
        )

    removed_anything = False
    if path.exists():
        if path.is_dir():
            shutil.rmtree(path)
            removed_anything = True
        else:
            path.unlink()
            removed_anything = True

    if custom:
        cfg.unset(f"data.{name}")
        cfg.save()

    after = next(
        (rec for rec in _list_dataset_records() if rec["id"] == name),
        None,
    )
    if after is None:
        after = {
            "id": name,
            "description": str(DATASETS[name].get("description") or ""),
            "status": "missing",
            "files_found": 0,
            "files_expected": len(DATASETS[name].get("files") or {}),
            "size_bytes": None,
            "size_display": "-",
            "auto_download": bool(DATASETS[name].get("auto_download")),
            "path": str(base / name),
            "source": DATASETS[name].get("source"),
            "note": DATASETS[name].get("note"),
        }
    after["removed"] = removed_anything
    return after
