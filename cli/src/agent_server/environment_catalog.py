"""Allowlists for Environment page package management.

Core CLI dependencies are locked. Skill/tool extras (+ known tool orphans)
are the only packages users may install or uninstall from the dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass

# Normalized PyPI names for [project.dependencies] in pyproject.toml.
# Keep in sync when core deps change.
CORE_PACKAGE_NAMES: frozenset[str] = frozenset(
    {
        "typer",
        "rich",
        "prompt-toolkit",
        "anthropic",
        "openai",
        "deepagents",
        "langchain",
        "langchain-anthropic",
        "langchain-openai",
        "langgraph",
        "httpx",
        "pandas",
        "numpy",
        "scipy",
        "python-dotenv",
        "markdown",
        "nbformat",
        "questionary",
        "termaid",
        "fastapi",
        "uvicorn",
        "pydantic",
        "python-multipart",
        "langchain-mcp-adapters",
        "mcp",
        # Runtime stack packages often pulled with the above (treat as locked).
        "starlette",
        "pydantic-core",
        "pydantic-settings",
        "anyio",
        "sniffio",
        "h11",
        "httpcore",
        "certifi",
        "idna",
        "click",
        "typing-extensions",
        "annotated-types",
        "packaging",
        "pyyaml",
        "orjson",
        "tenacity",
        "jsonpatch",
        "langsmith",
        "langgraph-checkpoint",
        "langgraph-prebuilt",
        "langgraph-sdk",
        "langchain-core",
        "uuid-utils",
        "xxhash",
        "ormsgpack",
        "zstandard",
        "requests",
        "urllib3",
        "charset-normalizer",
        "fastfold-agent-cli",
    }
)


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


def normalize_package_name(name: str) -> str:
    """Normalize a PyPI name for comparison (PEP 503-ish)."""
    return name.strip().lower().replace("_", "-")


def manageable_package_names() -> frozenset[str]:
    names: set[str] = set()
    for group in MANAGEABLE_GROUPS:
        for pkg in group.packages:
            names.add(normalize_package_name(pkg))
    return frozenset(names)


def is_core_package(name: str) -> bool:
    return normalize_package_name(name) in {
        normalize_package_name(item) for item in CORE_PACKAGE_NAMES
    }


def is_manageable_package(name: str) -> bool:
    return normalize_package_name(name) in manageable_package_names()
