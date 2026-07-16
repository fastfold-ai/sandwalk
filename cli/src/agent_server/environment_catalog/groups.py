"""Manageable package groups shown on the Environment page."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PackageGroup:
    id: str
    label: str
    description: str
    packages: tuple[str, ...]


MANAGEABLE_GROUPS: tuple[PackageGroup, ...] = (
    PackageGroup(
        id="chemistry",
        label="Chemistry",
        description="RDKit for structure, chemistry, and design tools.",
        packages=("rdkit",),
    ),
    PackageGroup(
        id="biology",
        label="Biology",
        description="Biopython for sequence and structure utilities.",
        packages=("biopython",),
    ),
    PackageGroup(
        id="singlecell",
        label="Single-cell",
        description="Scanpy stack and CELLxGENE Census access.",
        packages=(
            "scanpy",
            "anndata",
            "celltypist",
            "cellxgene-census",
            "tiledbsoma",
        ),
    ),
    PackageGroup(
        id="ml",
        label="Machine learning",
        description="Torch / Transformers / ESM for protein embeddings.",
        packages=("torch", "transformers", "fair-esm"),
    ),
    PackageGroup(
        id="analysis",
        label="Analysis",
        description="Plotting and classical ML helpers for the sandbox.",
        packages=("seaborn", "scikit-learn"),
    ),
    PackageGroup(
        id="notebook",
        label="Notebooks",
        description="Convert and export Jupyter notebooks.",
        packages=("nbconvert",),
    ),
    PackageGroup(
        id="api",
        label="API / SQL",
        description="DuckDB for local analytical queries.",
        packages=("duckdb",),
    ),
    PackageGroup(
        id="extended",
        label="Extended tools",
        description="Optional packages referenced by omics and code tools.",
        packages=(
            "squidpy",
            "pydeseq2",
            "muon",
            "mudata",
            "episcanpy",
            "rpy2",
            "gseapy",
            "pysam",
            "xlrd",
        ),
    ),
)
