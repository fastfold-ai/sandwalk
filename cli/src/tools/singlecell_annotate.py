"""singlecell.cell_type_annotate: marker-based or CellTypist cluster annotation.

Split from tools/singlecell.py. Calls ``_check_scanpy`` indirectly via the
``tools.singlecell`` hub module so that ``patch("tools.singlecell._check_scanpy")``
in tests continues to work regardless of which submodule performs the call.
"""

from __future__ import annotations

from tools import registry
from tools import singlecell as _singlecell


@registry.register(
    name="singlecell.cell_type_annotate",
    description="Annotate cell clusters with cell type labels using marker gene panels or CellTypist",
    category="singlecell",
    parameters={
        "data_path": "Path to h5ad file (should be clustered, e.g. from singlecell.cluster)",
        "reference": "Reference panel: 'immune', 'pbmc', 'tissue', or 'all' (default 'immune')",
        "method": "Annotation method: 'marker_based' (default) or 'celltypist'",
    },
    usage_guide="You have clustered single-cell data and need to assign cell type identities. Run after singlecell.cluster. Uses canonical marker genes to score each cluster against known cell type signatures.",
)
def cell_type_annotate(data_path: str, reference: str = "immune", method: str = "marker_based", **kwargs) -> dict:
    """Annotate clusters with cell type labels.

    marker_based: Score each cluster using canonical marker gene panels.
    celltypist: Use CellTypist automated annotation (requires celltypist package).
    """
    if method == "celltypist":
        try:
            import celltypist
        except ImportError:
            return {
                "error": "celltypist is required for automated annotation. Install with: pip install celltypist",
                "summary": "celltypist not installed. Use method='marker_based' or install with: pip install celltypist",
            }

    sc = _singlecell._check_scanpy()
    if sc is None:
        return {
            "error": "scanpy is required for cell type annotation. Install with: pip install scanpy",
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
                "error": f"Unsupported file format: {data_path}",
                "summary": f"Cannot read {data_path} — expected .h5ad or .csv",
            }
    except Exception as e:
        return {"error": f"Failed to load data: {e}", "summary": f"Could not read {data_path}"}

    # Find cluster key
    cluster_key = None
    for key in ["cluster", "leiden", "louvain", "cell_type"]:
        if key in adata.obs.columns:
            cluster_key = key
            break

    if cluster_key is None:
        return {
            "error": "No cluster assignments found. Run singlecell.cluster first.",
            "summary": "Pre-clustered data required for annotation",
        }

    clusters = adata.obs[cluster_key].astype(str)
    cluster_names = sorted(clusters.unique(), key=lambda x: int(x) if x.isdigit() else x)
    n_clusters = len(cluster_names)
    n_cells = adata.shape[0]

    # Select marker panels based on reference
    if reference in ("immune", "pbmc"):
        panels = {k: v for k, v in _singlecell.MARKER_PANELS.items()
                  if k not in ("Fibroblasts", "Endothelial", "Epithelial")}
    elif reference == "tissue":
        panels = _singlecell.MARKER_PANELS.copy()
    else:
        panels = _singlecell.MARKER_PANELS.copy()

    if method == "celltypist":
        # CellTypist annotation path
        try:
            import celltypist
            from celltypist import models as ct_models

            ct_models.download_models(force_update=False)
            model = ct_models.Model.load(model="Immune_All_Low.pkl")
            predictions = celltypist.annotate(adata, model=model, majority_voting=True)
            adata_result = predictions.to_adata()

            annotations = {}
            for cl in cluster_names:
                mask = clusters == cl
                cl_types = adata_result.obs.loc[mask, "majority_voting"].value_counts()
                top_type = cl_types.index[0] if len(cl_types) > 0 else "Unknown"
                confidence = float(cl_types.iloc[0] / cl_types.sum()) if len(cl_types) > 0 else 0.0
                annotations[cl] = {
                    "cell_type": top_type,
                    "confidence": round(confidence, 3),
                    "n_cells": int(mask.sum()),
                    "method": "celltypist",
                }

            annotation_list = list(annotations.values())
        except Exception as e:
            return {
                "error": f"CellTypist annotation failed: {e}",
                "summary": "CellTypist error — try method='marker_based' instead",
            }
    else:
        # Marker-based annotation
        gene_names = set(adata.var_names)

        annotations = {}
        for cl in cluster_names:
            mask = clusters == cl
            n_cells_cl = int(mask.sum())

            # Get mean expression for this cluster
            if hasattr(adata.X, "toarray"):
                cl_expr = np.array(adata.X[mask].toarray().mean(axis=0)).flatten()
            else:
                cl_expr = np.array(adata.X[mask].mean(axis=0)).flatten()

            gene_to_idx = {g: i for i, g in enumerate(adata.var_names)}

            # Score each cell type panel
            scores = {}
            for cell_type, markers in panels.items():
                present_markers = [m for m in markers if m in gene_names]
                if not present_markers:
                    continue
                marker_indices = [gene_to_idx[m] for m in present_markers]
                marker_expr = cl_expr[marker_indices]
                # Score = mean expression of present markers, weighted by fraction present
                score = float(np.mean(marker_expr)) * (len(present_markers) / len(markers))
                scores[cell_type] = round(score, 4)

            if scores:
                best_type = max(scores, key=scores.get)
                best_score = scores[best_type]
                # Confidence: ratio of best score to second-best
                sorted_scores = sorted(scores.values(), reverse=True)
                if len(sorted_scores) > 1 and sorted_scores[1] > 0:
                    specificity = sorted_scores[0] / sorted_scores[1]
                else:
                    specificity = float("inf") if best_score > 0 else 0.0
                confidence = min(1.0, best_score * min(specificity, 5.0) / 5.0) if best_score > 0 else 0.0
            else:
                best_type = "Unknown"
                best_score = 0.0
                confidence = 0.0
                scores = {}

            annotations[cl] = {
                "cell_type": best_type,
                "confidence": round(confidence, 3),
                "n_cells": n_cells_cl,
                "marker_score": round(best_score, 4),
                "all_scores": dict(sorted(scores.items(), key=lambda x: -x[1])[:5]),
                "method": "marker_based",
            }

        annotation_list = list(annotations.values())

    # Compute cell type distribution
    type_counts = {}
    for ann in annotation_list:
        ct = ann["cell_type"]
        type_counts[ct] = type_counts.get(ct, 0) + ann["n_cells"]

    total_cells = sum(type_counts.values())
    type_distribution = {
        ct: f"{count / total_cells:.0%}" for ct, count in
        sorted(type_counts.items(), key=lambda x: -x[1])
    }

    # Summary
    dist_str = ", ".join(f"{ct} ({pct})" for ct, pct in list(type_distribution.items())[:5])
    summary = f"Annotated {n_clusters} clusters: {dist_str}"

    return {
        "summary": summary,
        "n_cells": n_cells,
        "n_clusters": n_clusters,
        "method": method,
        "reference": reference,
        "annotations": annotations,
        "cell_type_distribution": type_distribution,
    }
