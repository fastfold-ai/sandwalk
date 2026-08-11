"""omics.multiomics_integrate: MOFA+ multi-omics integration. Split from tools/omics.py."""
from pathlib import Path

from tools import omics as _omics
from tools import registry


@registry.register(
    name="omics.multiomics_integrate",
    description="Integrate multiple omics modalities using MOFA+ (Multi-Omics Factor Analysis)",
    category="omics",
    parameters={
        "paths": "Comma-separated paths to h5ad files for each modality",
        "modality_names": "Comma-separated names for each modality (e.g., 'rna,atac,protein')",
        "n_factors": "Number of latent factors to learn (default 10)",
    },
    usage_guide=(
        "Integrate multiple omics datasets (RNA + ATAC, RNA + protein, etc.) into a shared "
        "latent space using MOFA+. Requires muon: pip install muon. Each modality should be "
        "an h5ad file with overlapping cell barcodes."
    ),
)
def multiomics_integrate(
    paths: str = "",
    modality_names: str = "",
    n_factors: int = 10,
    **kwargs,
) -> dict:
    """Integrate multiple omics modalities using MOFA+."""
    mu = _omics._check_muon()
    if mu is None:
        return {
            "error": "muon required. Install with: pip install muon mudata",
            "summary": "Install muon for multi-omics integration: pip install muon mudata",
        }

    sc = _omics._check_scanpy()
    if sc is None:
        return {"error": "scanpy required. Install with: pip install scanpy", "summary": "Install scanpy: pip install scanpy"}

    path_list = [p.strip() for p in paths.split(",") if p.strip()]
    name_list = [n.strip() for n in modality_names.split(",") if n.strip()]

    if len(path_list) < 2:
        return {"error": "Need at least 2 modality paths", "summary": "Provide ≥2 h5ad paths for integration"}

    if not name_list:
        name_list = [f"modality_{i}" for i in range(len(path_list))]
    if len(name_list) != len(path_list):
        return {"error": "Number of names must match number of paths", "summary": "Mismatched path/name count"}

    # Load modalities
    modalities = {}
    for name, fpath in zip(name_list, path_list):
        fp = Path(fpath).expanduser()
        if not fp.exists():
            return {"error": f"File not found: {fpath}", "summary": f"Missing file: {fpath}"}
        try:
            adata = sc.read_h5ad(fp)
            modalities[name] = adata
        except Exception as exc:
            return {"error": f"Failed to load {fpath}: {str(exc)[:200]}", "summary": f"Load error: {str(exc)[:100]}"}

    # Create MuData
    try:
        from mudata import MuData
    except Exception:
        return {
            "error": "mudata required. Install with: pip install mudata",
            "summary": "Install mudata to build MuData containers: pip install mudata",
        }
    try:
        mdata = MuData(modalities)
    except Exception as exc:
        return {"error": f"MuData creation failed: {str(exc)[:200]}", "summary": f"Integration setup error: {str(exc)[:100]}"}

    n_shared = mdata.n_obs
    mod_shapes = {name: (ad.n_obs, ad.n_vars) for name, ad in modalities.items()}

    # Preprocess each modality
    for name in name_list:
        ad = mdata.mod[name]
        if ad.X.max() > 50:  # likely raw counts
            sc.pp.normalize_total(ad, target_sum=1e4)
            sc.pp.log1p(ad)
        sc.pp.highly_variable_genes(ad, min_mean=0.0125, max_mean=3, min_disp=0.5)

    # Run MOFA+
    try:
        mu.tl.mofa(mdata, n_factors=n_factors, quiet=True)
    except Exception as exc:
        return {
            "error": f"MOFA+ failed: {str(exc)[:200]}",
            "summary": f"MOFA+ integration failed: {str(exc)[:100]}",
            "n_shared_cells": n_shared,
            "modality_shapes": mod_shapes,
        }

    # Extract results
    has_mofa = "X_mofa" in mdata.obsm
    if not has_mofa:
        return {
            "error": "MOFA+ did not produce embeddings",
            "summary": "Integration ran but produced no factors",
        }

    # Downstream: neighbors + leiden on MOFA space
    sc.pp.neighbors(mdata, use_rep="X_mofa")
    sc.tl.leiden(mdata, resolution=1.0, key_added="joint_cluster")

    clusters = mdata.obs["joint_cluster"].value_counts().to_dict()
    n_clusters = len(clusters)

    return {
        "n_shared_cells": n_shared,
        "n_factors": n_factors,
        "modalities": name_list,
        "modality_shapes": mod_shapes,
        "n_joint_clusters": n_clusters,
        "joint_cluster_sizes": clusters,
        "summary": (
            f"MOFA+ integration of {len(name_list)} modalities "
            f"({', '.join(f'{n}: {s[0]}cells x {s[1]}features' for n, s in mod_shapes.items())}). "
            f"{n_shared:,} shared cells → {n_factors} factors → {n_clusters} joint clusters."
        ),
    }
