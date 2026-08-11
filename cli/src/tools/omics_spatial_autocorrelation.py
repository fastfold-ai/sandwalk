"""omics.spatial_autocorrelation: Moran's I spatial autocorrelation. Split from tools/omics.py."""
from pathlib import Path

from tools import omics as _omics
from tools import registry


@registry.register(
    name="omics.spatial_autocorrelation",
    description="Compute spatial autocorrelation (Moran's I) for gene expression patterns",
    category="omics",
    parameters={
        "path": "Path to h5ad file with spatial coordinates",
        "genes": "Comma-separated gene names to test (default: top variable genes)",
        "n_genes": "Number of top variable genes to test if genes not specified (default 50)",
    },
    usage_guide=(
        "Test whether gene expression shows spatial patterning using Moran's I. "
        "High Moran's I = spatially clustered expression. Requires scanpy."
    ),
)
def spatial_autocorrelation(
    path: str,
    genes: str = "",
    n_genes: int = 50,
    **kwargs,
) -> dict:
    """Compute Moran's I spatial autocorrelation for genes."""
    filepath = Path(path).expanduser()
    if not filepath.exists():
        return {"error": f"File not found: {path}", "summary": f"File not found: {path}"}

    sc = _omics._check_scanpy()
    if sc is None:
        return {"error": "scanpy required", "summary": "Install scanpy: pip install scanpy"}

    try:
        adata = sc.read_h5ad(filepath)
    except Exception as exc:
        return {"error": f"Failed to load: {str(exc)[:200]}", "summary": f"Read error: {str(exc)[:100]}"}

    has_spatial = "spatial" in (adata.obsm or {})
    if not has_spatial:
        return {"error": "No spatial coordinates found in .obsm['spatial']", "summary": "Not spatial data: no coordinates found"}

    # Try squidpy
    try:
        import squidpy as sq
    except ImportError:
        return {"error": "squidpy required for Moran's I. Install: pip install squidpy", "summary": "Install squidpy: pip install squidpy"}

    # Preprocess if needed
    if adata.X.max() > 50:
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)

    # Build spatial graph
    sq.gr.spatial_neighbors(adata)

    # Select genes
    gene_list = [g.strip() for g in genes.split(",") if g.strip()] if genes else []
    if not gene_list:
        sc.pp.highly_variable_genes(adata, n_top_genes=min(n_genes, adata.n_vars))
        gene_list = list(adata.var_names[adata.var["highly_variable"]])[:n_genes]

    # Filter to genes present in data
    valid_genes = [g for g in gene_list if g in adata.var_names]
    if not valid_genes:
        return {"error": "None of the specified genes found in dataset", "summary": "No matching genes in data"}

    # Compute Moran's I
    sq.gr.spatial_autocorr(adata, mode="moran", genes=valid_genes)

    moranI = adata.uns.get("moranI")
    if moranI is None:
        return {"error": "Moran's I computation failed", "summary": "Spatial autocorrelation computation failed"}

    results = moranI.sort_values("I", ascending=False)
    top_spatial = results.head(20).to_dict("index")

    highly_spatial = results[results["pval_norm"] < 0.05]
    n_spatial = len(highly_spatial)

    return {
        "n_genes_tested": len(valid_genes),
        "n_spatially_patterned": n_spatial,
        "top_spatial_genes": top_spatial,
        "summary": (
            f"Moran's I on {len(valid_genes)} genes: {n_spatial} show significant spatial "
            f"patterning (p<0.05). Top: "
            + ", ".join(f"{g} (I={row['I']:.3f})" for g, row in list(results.head(5).iterrows()))
        ),
    }
