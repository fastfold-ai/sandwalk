"""omics.cytof_cluster: CyTOF/flow clustering. Split from tools/omics.py."""
from pathlib import Path

from tools import registry

from tools import omics as _omics


@registry.register(
    name="omics.cytof_cluster",
    description="Cluster CyTOF or flow cytometry data and characterize marker expression per cluster",
    category="omics",
    parameters={
        "path": "Path to CyTOF/flow data (CSV with markers as columns, cells as rows)",
        "n_clusters": "Number of clusters for KMeans (default 10). Use 0 for auto (Leiden).",
        "markers": "Comma-separated marker columns to use (default: all numeric columns)",
    },
    usage_guide=(
        "Cluster mass/flow cytometry data. Input is a cells x markers matrix. "
        "Identifies cell populations and characterizes each by marker expression."
    ),
)
def cytof_cluster(
    path: str,
    n_clusters: int = 10,
    markers: str = "",
    **kwargs,
) -> dict:
    """Cluster CyTOF/flow cytometry data."""
    import numpy as np

    df, error = _omics._load_tabular(path)
    if error:
        # Try without index_col since CyTOF data often has no row names
        import pandas as pd

        filepath = Path(path).expanduser()
        if not filepath.exists():
            return {"error": error, "summary": f"Could not load: {error}"}
        suffix = filepath.suffix.lower()
        sep = "," if suffix == ".csv" else "\t"
        try:
            df = pd.read_csv(filepath, sep=sep)
        except Exception as exc2:
            return {"error": str(exc2), "summary": f"Could not load: {str(exc2)[:100]}"}

    marker_cols = [m.strip() for m in markers.split(",") if m.strip()] if markers else []
    if not marker_cols:
        marker_cols = list(df.select_dtypes(include=[np.number]).columns)

    if not marker_cols:
        return {"error": "No numeric marker columns found", "summary": "No numeric columns in data"}

    data = df[marker_cols].dropna()
    n_cells = len(data)
    if n_cells < 10:
        return {"error": f"Too few cells ({n_cells}) for clustering", "summary": f"Only {n_cells} cells — need at least 10"}

    # Standardize
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler()
    scaled = scaler.fit_transform(data.values)

    # Cluster
    if n_clusters > 0:
        from sklearn.cluster import MiniBatchKMeans

        model = MiniBatchKMeans(n_clusters=min(n_clusters, n_cells), random_state=42, n_init=3)
        labels = model.fit_predict(scaled)
    else:
        # Use Leiden via scanpy on a neighbors graph
        sc = _omics._check_scanpy()
        if sc is not None:
            import anndata

            adata = anndata.AnnData(X=scaled)
            sc.pp.neighbors(adata, n_neighbors=15)
            sc.tl.leiden(adata, resolution=1.0)
            labels = adata.obs["leiden"].astype(int).values
        else:
            from sklearn.cluster import MiniBatchKMeans

            model = MiniBatchKMeans(n_clusters=10, random_state=42, n_init=3)
            labels = model.fit_predict(scaled)

    import pandas as pd

    data = data.copy()
    data["cluster"] = labels

    cluster_sizes = data["cluster"].value_counts().sort_index().to_dict()
    n_clusters_found = len(cluster_sizes)

    # Per-cluster marker expression (median)
    cluster_medians = data.groupby("cluster")[marker_cols].median()
    cluster_profiles = cluster_medians.to_dict("index")

    # Find defining markers per cluster (highest z-score)
    defining_markers = {}
    global_means = data[marker_cols].mean()
    global_stds = data[marker_cols].std().replace(0, 1)
    for cl in sorted(cluster_sizes.keys()):
        cl_means = cluster_medians.loc[cl]
        z_scores = ((cl_means - global_means) / global_stds).sort_values(ascending=False)
        defining_markers[str(cl)] = list(z_scores.head(5).index)

    return {
        "n_cells": n_cells,
        "n_markers": len(marker_cols),
        "n_clusters": n_clusters_found,
        "cluster_sizes": {str(k): v for k, v in cluster_sizes.items()},
        "defining_markers": defining_markers,
        "cluster_profiles": {str(k): {mk: round(v, 3) for mk, v in prof.items()} for k, prof in cluster_profiles.items()},
        "summary": (
            f"CyTOF clustering: {n_cells:,} cells x {len(marker_cols)} markers → "
            f"{n_clusters_found} clusters. Largest: {max(cluster_sizes.values()):,} cells. "
            f"Top defining markers per cluster identified."
        ),
    }


# ---------------------------------------------------------------------------
# 18. omics.hic_compartments
# ---------------------------------------------------------------------------
