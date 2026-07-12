#!/usr/bin/env python3
"""
Prepare L1000 landmark gene expression data from GEO.

Downloads the raw Level 5 GCTx file from GEO (GSE92742) and extracts
the 978 landmark gene subset into a compact Parquet file for use with ct.

Usage:
    python scripts/prepare_l1000.py [--output ~/.ct/data/l1000]

Requirements:
    pip install cmapPy pandas pyarrow
"""

import argparse
import gzip
import os
import sys
from pathlib import Path

import httpx
import pandas as pd


# GEO download URL for GSE92742 Level 5 (MODZ signatures)
GEO_URL = (
    "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE92nnn/GSE92742/suppl/"
    "GSE92742_Broad_LINCS_Level5_COMPZ.MODZ_n473647x12328.gctx.gz"
)

# Gene metadata (small) used to identify the 978 landmark genes (pr_is_lm == 1).
GENE_INFO_URL = (
    "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE92nnn/GSE92742/suppl/"
    "GSE92742_Broad_LINCS_gene_info.txt.gz"
)


def download_gctx(output_dir: Path) -> Path:
    """Download the raw GCTx file from GEO."""
    gz_path = output_dir / "GSE92742_Level5.gctx.gz"
    gctx_path = output_dir / "GSE92742_Level5.gctx"

    if gctx_path.exists():
        print(f"GCTx file already exists: {gctx_path}")
        return gctx_path

    if not gz_path.exists():
        print(f"Downloading from GEO (~20GB; decompresses to ~22GB)...")
        print(f"URL: {GEO_URL}")
        with httpx.stream("GET", GEO_URL, timeout=3600, follow_redirects=True) as resp:
            if resp.status_code != 200:
                print(f"Download failed: HTTP {resp.status_code}")
                sys.exit(1)
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(gz_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        print(f"\r  {downloaded / 1e9:.1f} / {total / 1e9:.1f} GB ({pct:.0f}%)", end="")
            print()

    print("Decompressing...")
    with gzip.open(gz_path, "rb") as f_in:
        with open(gctx_path, "wb") as f_out:
            while True:
                chunk = f_in.read(65536)
                if not chunk:
                    break
                f_out.write(chunk)

    # Clean up gz
    gz_path.unlink()
    return gctx_path


def _landmark_gene_ids(output_dir: Path) -> list[str]:
    """Return the 978 landmark gene ids (pr_is_lm == 1) from GEO gene_info."""
    gi_path = output_dir / "GSE92742_gene_info.txt.gz"
    if not gi_path.exists():
        print("Fetching gene_info to identify landmark genes...")
        with httpx.stream("GET", GENE_INFO_URL, timeout=120, follow_redirects=True) as resp:
            resp.raise_for_status()
            with open(gi_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)
    landmark: list[str] = []
    with gzip.open(gi_path, "rt") as f:
        header = f.readline().rstrip("\n").split("\t")
        gid = header.index("pr_gene_id")
        is_lm = header.index("pr_is_lm")
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if parts[is_lm] == "1":
                landmark.append(parts[gid])
    return landmark


def extract_landmarks(gctx_path: Path, output_dir: Path) -> Path:
    """Extract the 978 landmark genes from the GCTx into Parquet."""
    out_path = output_dir / "l1000_landmark_only.parquet"

    if out_path.exists():
        print(f"Landmark parquet already exists: {out_path}")
        return out_path

    try:
        from cmapPy.pandasGEXpress.parse import parse
    except ImportError:
        print("cmapPy required: pip install cmapPy")
        sys.exit(1)

    landmark_ids = _landmark_gene_ids(output_dir)
    print(f"Parsing GCTx and extracting {len(landmark_ids)} landmark genes...")
    # Subset by row id (gene) so we only pull landmark rows out of the HDF5.
    gctoo = parse(str(gctx_path), rid=landmark_ids)
    df = gctoo.data_df

    print(f"Extracted: {df.shape[0]} genes x {df.shape[1]} signatures")

    # Save as parquet
    df.to_parquet(out_path)
    print(f"Saved: {out_path} ({out_path.stat().st_size / 1e6:.0f} MB)")

    return out_path


def main():
    parser = argparse.ArgumentParser(description="Prepare L1000 landmark data from GEO")
    parser.add_argument("--output", type=Path, default=Path.home() / ".ct" / "data" / "l1000",
                        help="Output directory (default: ~/.ct/data/l1000)")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {args.output}")

    gctx_path = download_gctx(args.output)
    parquet_path = extract_landmarks(gctx_path, args.output)

    # Auto-configure ct
    try:
        from agent.config import Config
        cfg = Config.load()
        cfg.set("data.l1000", str(args.output))
        cfg.save()
        print(f"\nAuto-configured data.l1000 = {args.output}")
    except ImportError:
        print(f"\nManual config: fastfold config set data.l1000 {args.output}")

    # Clean up raw GCTx (large)
    if gctx_path.exists() and parquet_path.exists():
        size_gb = gctx_path.stat().st_size / 1e9
        resp = input(f"\nDelete raw GCTx ({size_gb:.1f} GB) to save space? [y/N] ")
        if resp.lower() == "y":
            gctx_path.unlink()
            print("Deleted raw GCTx file.")

    print("\nDone! L1000 landmark data is ready.")


if __name__ == "__main__":
    main()
