"""singlecell.cluster: Leiden/Louvain clustering with PCA + UMAP.

Split from tools/singlecell.py. Calls ``_check_scanpy`` indirectly via the
``tools.singlecell`` hub module so that ``patch("tools.singlecell._check_scanpy")``
in tests continues to work regardless of which submodule performs the call.
"""

from __future__ import annotations

from tools import registry
from tools import singlecell as _singlecell


@registry.register(
    name="singlecell.cluster",
    description="Cluster single-cell RNA-seq data using Leiden/Louvain community detection with PCA and UMAP embedding",
    category="singlecell",
    parameters={
        "data_path": "Path to h5ad or CSV file with single-cell expression data",
        "resolution": "Clustering resolution (higher = more clusters, default 1.0)",
        "method": "Clustering method: 'leiden' or 'louvain' (default 'leiden')",
    },
    usage_guide="You have single-cell RNA-seq data and need to identify cell populations. Run this first in any single-cell analysis workflow. Produces cluster assignments and UMAP coordinates for downstream annotation.",
)
def cluster(data_path: str, resolution: float = 1.0, method: str = "leiden", **kwargs) -> dict:
    """Cluster single-cell data: load -> normalize -> PCA -> neighbors -> clustering -> UMAP.

    Supports h5ad (AnnData) and CSV input formats. Returns cluster assignments,
    top marker genes per cluster, and UMAP coordinate summary.
    """
    sc = _singlecell._check_scanpy()
    if sc is None:
        return {
            "error": "scanpy is required for single-cell clustering. Install with: pip install scanpy",
            "summary": "scanpy not installed. Install with: pip install scanpy",
        }

    import numpy as np

    # Load data
    try:
        if data_path.endswith(".h5ad"):
            adata = sc.read_h5ad(data_path)
        elif data_path.endswith(".csv"):
            import pandas as pd
            df = pd.read_csv(data_path, index_col=0)
            from anndata import AnnData
            adata = AnnData(df)
        else:
            return {
                "error": f"Unsupported file format: {data_path}. Use .h5ad or .csv",
                "summary": f"Cannot read {data_path} — expected .h5ad or .csv format",
            }
    except Exception as e:
        return {
            "error": f"Failed to load data: {e}",
            "summary": f"Could not read single-cell data from {data_path}",
        }

    n_cells, n_genes = adata.shape

    # Store raw counts for marker gene detection
    adata.layers["counts"] = adata.X.copy()

    # Standard preprocessing pipeline
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)

    # Identify highly variable genes
    if n_genes > 2000:
        sc.pp.highly_variable_genes(adata, n_top_genes=min(2000, n_genes))
        adata_hvg = adata[:, adata.var["highly_variable"]].copy()
    else:
        adata_hvg = adata.copy()

    # Scale and PCA
    sc.pp.scale(adata_hvg, max_value=10)
    n_pcs = min(50, adata_hvg.shape[1] - 1, adata_hvg.shape[0] - 1)
    sc.tl.pca(adata_hvg, n_comps=n_pcs)

    # Transfer PCA to full adata
    adata.obsm["X_pca"] = adata_hvg.obsm["X_pca"]

    # Neighbors and clustering
    n_neighbors = min(15, n_cells - 1)
    sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs)

    if method == "leiden":
        try:
            sc.tl.leiden(adata, resolution=resolution, key_added="cluster")
        except Exception:
            # Fall back to louvain if leiden not available
            sc.tl.louvain(adata, resolution=resolution, key_added="cluster")
            method = "louvain"
    else:
        sc.tl.louvain(adata, resolution=resolution, key_added="cluster")

    # UMAP
    sc.tl.umap(adata)

    # Get cluster assignments
    clusters = adata.obs["cluster"].astype(str)
    n_clusters = clusters.nunique()
    cluster_sizes = clusters.value_counts().to_dict()

    # Find marker genes per cluster
    try:
        sc.tl.rank_genes_groups(adata, groupby="cluster", method="wilcoxon", layer="counts")
        marker_genes = {}
        for cl in sorted(clusters.unique(), key=lambda x: int(x) if x.isdigit() else x):
            names = adata.uns["rank_genes_groups"]["names"][cl][:5]
            scores = adata.uns["rank_genes_groups"]["scores"][cl][:5]
            marker_genes[str(cl)] = [
                {"gene": str(n), "score": round(float(s), 3)}
                for n, s in zip(names, scores)
            ]
    except Exception:
        marker_genes = {}

    # UMAP summary statistics
    umap_coords = adata.obsm["X_umap"]
    umap_summary = {
        "min_x": round(float(np.min(umap_coords[:, 0])), 3),
        "max_x": round(float(np.max(umap_coords[:, 0])), 3),
        "min_y": round(float(np.min(umap_coords[:, 1])), 3),
        "max_y": round(float(np.max(umap_coords[:, 1])), 3),
    }

    # Build summary text
    marker_str_parts = []
    for cl in sorted(marker_genes.keys(), key=lambda x: int(x) if x.isdigit() else x)[:5]:
        genes = ", ".join(m["gene"] for m in marker_genes[cl][:3])
        marker_str_parts.append(f"cluster {cl}: {genes}")
    marker_summary = "; ".join(marker_str_parts) if marker_str_parts else "N/A"

    summary = (
        f"Clustered {n_cells} cells into {n_clusters} clusters "
        f"({method} r={resolution}). "
        f"Top markers: {marker_summary}"
    )

    return {
        "summary": summary,
        "n_cells": n_cells,
        "n_genes": n_genes,
        "n_clusters": n_clusters,
        "method": method,
        "resolution": resolution,
        "cluster_sizes": cluster_sizes,
        "marker_genes": marker_genes,
        "umap_summary": umap_summary,
    }
