"""Static dataset catalog for the ct downloader."""

from typing import Any

from rich.console import Console

console = Console()

# Download timeout in seconds (large files like CRISPRGeneEffect ~700MB need more time)
DOWNLOAD_TIMEOUT = 600

DATASETS: dict[str, dict[str, Any]] = {
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
