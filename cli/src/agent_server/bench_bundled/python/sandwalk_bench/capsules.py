"""Lazy download/extract of BixBench CapsuleFolder zips from Hugging Face."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

from sandwalk_bench.bixbench import REPO_ID, cache_dir

HF_FILE = "https://huggingface.co/datasets/{repo}/resolve/main/{name}"


def ensure_capsule(data_folder: str, token: str | None = None) -> Path | None:
    """Download + extract ``data_folder`` zip; return CapsuleData path if found."""
    if not data_folder:
        return None
    tok = (
        token
        or os.environ.get("HF_TOKEN")
        or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        or ""
    ).strip()
    cache = cache_dir()
    zip_path = cache / data_folder
    extract_root = cache / data_folder.replace(".zip", "")
    if not zip_path.is_file():
        if not tok:
            raise RuntimeError("HF_TOKEN required to download BixBench capsules")
        url = HF_FILE.format(repo=REPO_ID, name=data_folder)
        req = Request(url, headers={"Authorization": f"Bearer {tok}"})
        with urlopen(req, timeout=300) as resp:  # noqa: S310 — fixed HF URL
            zip_path.write_bytes(resp.read())
    if not extract_root.is_dir():
        extract_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_root)
    for child in extract_root.rglob("CapsuleData-*"):
        if child.is_dir():
            return child
    return extract_root if extract_root.is_dir() else None
