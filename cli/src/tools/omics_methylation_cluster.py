"""omics.methylation_cluster: episcanpy-based clustering. Split from tools/omics.py."""
import logging
from pathlib import Path

from tools import registry

from tools import omics as _omics

logger = logging.getLogger("tools.omics")


@registry.register(
    name="omics.methylation_cluster",
    description="Cluster samples by methylation patterns using episcanpy",
    category="omics",
    parameters={
        "path": "Path to methylation matrix (h5ad or CSV, CpG sites as rows, samples as columns)",
        "n_top_features": "Number of most variable CpGs to use (default 5000)",
        "resolution": "Leiden clustering resolution (default 1.0)",
    },
    usage_guide=(
        "Cluster cells/samples by DNA methylation profiles. Uses episcanpy for "
        "methylation-aware preprocessing if available, falls back to scanpy/sklearn. "
        "Works on Illumina 450K/EPIC beta-value matrices or single-cell methylation h5ad."
    ),
)
def methylation_cluster(
    path: str,
    n_top_features: int = 5000,
    resolution: float = 1.0,
    **kwargs,
) -> dict:
    """Cluster samples by methylation patterns."""
    import numpy as np

    filepath = Path(path).expanduser()
    if not filepath.exists():
        return {"error": f"File not found: {path}", "summary": f"File not found: {path}"}

    epi = _omics._check_episcanpy()
    sc = _omics._check_scanpy()

    # Load data
    adata = None
    if filepath.suffix.lower() == ".h5ad":
        if sc is None and epi is None:
            return {"error": "scanpy or episcanpy required for h5ad", "summary": "Install scanpy or episcanpy"}
        reader = epi if epi else sc
        try:
            adata = reader.read_h5ad(filepath)
        except Exception as exc:
            return {"error": f"Failed to load h5ad: {str(exc)[:200]}", "summary": f"Load error: {str(exc)[:100]}"}
    else:
        # Tabular: load as AnnData
        import pandas as pd

        df, error = _omics._load_tabular(str(filepath))
        if error:
            return {"error": error, "summary": f"Could not load: {error}"}
        try:
            import anndata

            # Transpose so samples are obs and CpGs are var
            adata = anndata.AnnData(X=df.T.values, obs=pd.DataFrame(index=df.columns), var=pd.DataFrame(index=df.index))
        except ImportError:
            return {"error": "anndata required: pip install anndata", "summary": "Install anndata"}

    n_obs, n_vars = adata.n_obs, adata.n_vars

    # Use episcanpy pipeline if available
    if epi is not None:
        try:
            # episcanpy variable feature selection
            epi.pp.filter_features(adata, min_cells=max(1, int(n_obs * 0.05)))
            epi.pp.select_var_feature(adata, nb_features=min(n_top_features, adata.n_vars))
            adata_use = adata[:, adata.var["highly_variable"]] if "highly_variable" in adata.var else adata
            epi.pp.pca(adata_use, n_comps=min(50, adata_use.n_vars - 1, adata_use.n_obs - 1))
            epi.pp.neighbors(adata_use, n_neighbors=15)
            epi.tl.leiden(adata_use, resolution=resolution)

            clusters = adata_use.obs["leiden"].value_counts().to_dict()

            result = {
                "method": "episcanpy",
                "n_samples": n_obs,
                "n_features_input": n_vars,
                "n_features_used": adata_use.n_vars,
                "n_clusters": len(clusters),
                "cluster_sizes": clusters,
                "summary": (
                    f"Methylation clustering (episcanpy): {n_obs} samples, {adata_use.n_vars} variable CpGs → "
                    f"{len(clusters)} clusters."
                ),
            }

            # Try to find marker CpGs
            try:
                epi.tl.rank_features(adata_use, groupby="leiden")
                markers = {}
                for cl in adata_use.obs["leiden"].unique():
                    markers[str(cl)] = list(adata_use.uns["rank_features_groups"]["names"][cl][:5])
                result["cluster_markers"] = markers
            except Exception:
                pass

            return result

        except Exception as exc:
            logger.warning("episcanpy pipeline failed, falling back to scanpy: %s", exc)

    # Fallback: scanpy or sklearn
    if sc is not None:
        try:
            sc.pp.highly_variable_genes(adata, n_top_genes=min(n_top_features, adata.n_vars))
            adata_use = adata[:, adata.var["highly_variable"]]
            sc.tl.pca(adata_use, n_comps=min(50, adata_use.n_vars - 1, adata_use.n_obs - 1))
            sc.pp.neighbors(adata_use, n_neighbors=15)
            sc.tl.leiden(adata_use, resolution=resolution)

            clusters = adata_use.obs["leiden"].value_counts().to_dict()
            return {
                "method": "scanpy (episcanpy not installed)",
                "n_samples": n_obs,
                "n_features_input": n_vars,
                "n_features_used": adata_use.n_vars,
                "n_clusters": len(clusters),
                "cluster_sizes": clusters,
                "summary": (
                    f"Methylation clustering (scanpy fallback): {n_obs} samples → "
                    f"{len(clusters)} clusters. Install episcanpy for methylation-specific analysis."
                ),
            }
        except Exception as exc:
            logger.warning("scanpy fallback failed: %s", exc)

    # Last resort: sklearn KMeans
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    X = adata.X
    X = np.nan_to_num(X, nan=0.0)
    X = StandardScaler().fit_transform(X)
    n_comps = min(50, X.shape[0] - 1, X.shape[1] - 1)
    X_pca = PCA(n_components=n_comps).fit_transform(X)
    n_k = min(10, X.shape[0] // 2)
    labels = KMeans(n_clusters=max(n_k, 2), random_state=42, n_init=3).fit_predict(X_pca)

    import pandas as pd

    cluster_counts = pd.Series(labels).value_counts().to_dict()
    return {
        "method": "sklearn (install episcanpy or scanpy for better results)",
        "n_samples": n_obs,
        "n_features_input": n_vars,
        "n_clusters": len(cluster_counts),
        "cluster_sizes": {str(k): v for k, v in cluster_counts.items()},
        "summary": (
            f"Methylation clustering (sklearn fallback): {n_obs} samples → "
            f"{len(cluster_counts)} clusters. Install episcanpy for methylation-specific analysis."
        ),
    }
