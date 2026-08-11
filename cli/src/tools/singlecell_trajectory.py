"""singlecell.trajectory: diffusion map + PAGA trajectory/pseudotime inference.

Split from tools/singlecell.py. Calls ``_check_scanpy`` indirectly via the
``tools.singlecell`` hub module so that ``patch("tools.singlecell._check_scanpy")``
in tests continues to work regardless of which submodule performs the call.
"""

from __future__ import annotations

from tools import registry
from tools import singlecell as _singlecell


@registry.register(
    name="singlecell.trajectory",
    description="Infer developmental trajectories and pseudotime from single-cell data using diffusion maps and PAGA",
    category="singlecell",
    parameters={
        "data_path": "Path to h5ad file (ideally pre-clustered from singlecell.cluster)",
        "root_cluster": "Cluster to use as root for pseudotime (optional, auto-detected if not set)",
        "method": "Trajectory method: 'diffmap' (default) or 'paga'",
    },
    usage_guide="You have clustered single-cell data and want to understand differentiation trajectories, lineage relationships, or developmental ordering. Run after singlecell.cluster. Computes pseudotime and identifies branch points.",
)
def trajectory(data_path: str, root_cluster: str = None, method: str = "diffmap", **kwargs) -> dict:
    """Infer trajectories using diffusion map + PAGA.

    Computes diffusion pseudotime from a root cell (selected from root_cluster
    or auto-detected as the cluster with lowest diffusion component 1).
    PAGA provides a coarse-grained graph of cluster connectivity.
    """
    sc = _singlecell._check_scanpy()
    if sc is None:
        return {
            "error": "scanpy is required for trajectory analysis. Install with: pip install scanpy",
            "summary": "scanpy not installed. Install with: pip install scanpy",
        }

    import numpy as np

    # Load data
    try:
        if data_path.endswith(".h5ad"):
            adata = sc.read_h5ad(data_path)
        else:
            return {
                "error": "Trajectory analysis requires h5ad format with pre-computed neighbors",
                "summary": "Use singlecell.cluster first to generate an h5ad file",
            }
    except Exception as e:
        return {"error": f"Failed to load data: {e}", "summary": f"Could not read {data_path}"}

    n_cells = adata.shape[0]

    # Ensure neighbors are computed
    if "neighbors" not in adata.uns:
        n_neighbors = min(15, n_cells - 1)
        n_pcs = min(50, adata.shape[1] - 1, n_cells - 1)
        sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs)

    # Ensure clustering exists
    cluster_key = None
    for key in ["cluster", "leiden", "louvain"]:
        if key in adata.obs.columns:
            cluster_key = key
            break
    if cluster_key is None:
        return {
            "error": "No cluster assignments found. Run singlecell.cluster first.",
            "summary": "Pre-clustered data required for trajectory analysis",
        }

    # Compute diffusion map
    sc.tl.diffmap(adata, n_comps=15)

    # PAGA for coarse-grained connectivity
    sc.tl.paga(adata, groups=cluster_key)
    paga_connectivities = adata.uns["paga"]["connectivities"].toarray()

    # Determine root cell
    clusters = adata.obs[cluster_key].astype(str)
    if root_cluster is not None:
        root_cluster = str(root_cluster)
        if root_cluster not in clusters.values:
            return {
                "error": f"Root cluster '{root_cluster}' not found. Available: {sorted(clusters.unique())}",
                "summary": f"Invalid root cluster: {root_cluster}",
            }
        # Select root as cell in root_cluster with lowest DC1
        mask = clusters == root_cluster
        dc1_values = adata.obsm["X_diffmap"][mask, 0]
        root_idx_in_cluster = np.argmin(dc1_values)
        root_idx = np.where(mask)[0][root_idx_in_cluster]
    else:
        # Auto-detect: cell with lowest DC1 value
        root_idx = int(np.argmin(adata.obsm["X_diffmap"][:, 0]))
        root_cluster = str(clusters.iloc[root_idx])

    adata.uns["iroot"] = root_idx

    # Compute diffusion pseudotime
    sc.tl.dpt(adata)
    pseudotime = adata.obs["dpt_pseudotime"].values

    # Identify branches (clusters connected in PAGA)
    cluster_names = sorted(clusters.unique(), key=lambda x: int(x) if x.isdigit() else x)
    n_clusters = len(cluster_names)

    # Find branch points: clusters connected to 3+ other clusters in PAGA
    branch_points = []
    paga_threshold = 0.1
    for i, cl in enumerate(cluster_names):
        n_connections = np.sum(paga_connectivities[i] > paga_threshold)
        if n_connections >= 3:
            branch_points.append({
                "cluster": cl,
                "n_connections": int(n_connections),
                "connected_to": [
                    cluster_names[j]
                    for j in range(n_clusters)
                    if paga_connectivities[i, j] > paga_threshold and i != j
                ],
            })

    # Pseudotime statistics per cluster
    pseudotime_stats = {}
    for cl in cluster_names:
        mask = clusters == cl
        pt_values = pseudotime[mask]
        valid = pt_values[np.isfinite(pt_values)]
        if len(valid) > 0:
            pseudotime_stats[cl] = {
                "mean": round(float(np.mean(valid)), 4),
                "median": round(float(np.median(valid)), 4),
                "min": round(float(np.min(valid)), 4),
                "max": round(float(np.max(valid)), 4),
            }

    # Lineage ordering: sort clusters by mean pseudotime
    lineage_order = sorted(
        pseudotime_stats.keys(),
        key=lambda x: pseudotime_stats[x]["mean"],
    )

    valid_pt = pseudotime[np.isfinite(pseudotime)]
    pt_range = (round(float(np.min(valid_pt)), 4), round(float(np.max(valid_pt)), 4))

    summary = (
        f"Trajectory analysis: {len(branch_points)} branch point(s) from root "
        f"(cluster {root_cluster}), pseudotime range {pt_range[0]}-{pt_range[1]}"
    )

    return {
        "summary": summary,
        "n_cells": n_cells,
        "root_cluster": root_cluster,
        "root_cell_index": int(root_idx),
        "method": method,
        "pseudotime_range": pt_range,
        "pseudotime_per_cluster": pseudotime_stats,
        "lineage_order": lineage_order,
        "branch_points": branch_points,
        "n_branches": len(branch_points),
        "paga_connectivities": {
            cluster_names[i]: {
                cluster_names[j]: round(float(paga_connectivities[i, j]), 4)
                for j in range(n_clusters)
                if paga_connectivities[i, j] > paga_threshold and i != j
            }
            for i in range(n_clusters)
        },
    }
