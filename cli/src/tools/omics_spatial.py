"""omics.spatial_cluster: spatial transcriptomics clustering. Split from tools/omics.py."""
from pathlib import Path

from tools import registry

from tools import omics as _omics


@registry.register(
    name="omics.spatial_cluster",
    description="Spatial-aware clustering of spatial transcriptomics data",
    category="omics",
    parameters={
        "path": "Path to h5ad file with spatial coordinates in .obsm['spatial']",
        "resolution": "Leiden clustering resolution (default 1.0)",
        "n_neighbors": "Number of spatial neighbors (default 15)",
    },
    usage_guide=(
        "Cluster spatial transcriptomics data (Visium, MERFISH, etc.) using "
        "both expression similarity and spatial proximity. Requires scanpy; "
        "squidpy is optional for enhanced spatial analysis."
    ),
)
def spatial_cluster(
    path: str,
    resolution: float = 1.0,
    n_neighbors: int = 15,
    **kwargs,
) -> dict:
    """Spatial-aware clustering of spatial transcriptomics data."""
    filepath = Path(path).expanduser()
    if not filepath.exists():
        return {"error": f"File not found: {path}", "summary": f"File not found: {path}"}

    sc = _omics._check_scanpy()
    if sc is None:
        return {
            "error": "scanpy required. Install with: pip install scanpy",
            "summary": "Install scanpy for spatial clustering: pip install scanpy",
        }

    try:
        adata = sc.read_h5ad(filepath)
    except Exception as exc:
        return {"error": f"Failed to load h5ad: {str(exc)[:200]}", "summary": f"Could not read file: {str(exc)[:100]}"}

    has_spatial = "spatial" in (adata.obsm or {})

    # Standard preprocessing if raw
    if adata.X.max() > 50:  # likely raw counts
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)

    sc.pp.highly_variable_genes(adata, min_mean=0.0125, max_mean=3, min_disp=0.5)
    sc.tl.pca(adata, n_comps=min(50, adata.n_vars - 1, adata.n_obs - 1))
    sc.pp.neighbors(adata, n_neighbors=n_neighbors)

    # Try squidpy for spatial neighbors
    sq = None
    try:
        import squidpy as sq_mod
        sq = sq_mod
    except ImportError:
        pass

    if has_spatial and sq:
        try:
            sq.gr.spatial_neighbors(adata, n_neighs=n_neighbors)
            # Combine spatial + expression connectivity
            from scipy.sparse import csr_matrix
            expr_conn = adata.obsp.get("connectivities")
            spatial_conn = adata.obsp.get("spatial_connectivities")
            if expr_conn is not None and spatial_conn is not None:
                combined = 0.5 * expr_conn + 0.5 * spatial_conn
                adata.obsp["connectivities"] = csr_matrix(combined)
        except Exception:
            pass  # Fall back to expression-only neighbors

    sc.tl.leiden(adata, resolution=resolution, key_added="spatial_cluster")

    clusters = adata.obs["spatial_cluster"].value_counts().to_dict()
    n_clusters = len(clusters)

    result = {
        "n_cells": adata.n_obs,
        "n_genes": adata.n_vars,
        "n_clusters": n_clusters,
        "cluster_sizes": clusters,
        "has_spatial_coords": has_spatial,
        "used_squidpy": sq is not None and has_spatial,
        "resolution": resolution,
        "summary": (
            f"Spatial clustering: {adata.n_obs:,} cells → {n_clusters} clusters "
            f"(resolution={resolution}). "
            f"{'Used spatial+expression neighbors (squidpy).' if sq and has_spatial else 'Expression-based neighbors only.'} "
            f"Largest cluster: {max(clusters.values()):,} cells."
        ),
    }

    # Try to find marker genes per cluster
    try:
        sc.tl.rank_genes_groups(adata, "spatial_cluster", method="wilcoxon", n_genes=5)
        markers = {}
        for cl in adata.obs["spatial_cluster"].unique():
            genes = list(adata.uns["rank_genes_groups"]["names"][cl][:5])
            markers[str(cl)] = genes
        result["cluster_markers"] = markers
    except Exception:
        pass

    return result
