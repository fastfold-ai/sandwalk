"""
target.neosubstrate_score / target.coessentiality: DepMap-driven target scoring.

Split from tools/target.py.
"""

import numpy as np
import pandas as pd

from tools import registry


@registry.register(
    name="target.neosubstrate_score",
    description="Score proteins as potential neosubstrate targets based on degradation selectivity and magnitude",
    category="target",
    parameters={"proteomics_path": "Path to proteomics LFC matrix", "top_n": "Number of top targets to return"},
    requires_data=["proteomics"],
    usage_guide="You want to discover new degradation targets from proteomics data — ranks proteins by selective, potent degradation across compounds. Use early in target discovery campaigns.",
)
def neosubstrate_score(proteomics_path: str = None, top_n: int = 50, **kwargs) -> dict:
    """Score proteins for neosubstrate potential."""
    # Load proteomics data
    if proteomics_path is None:
        try:
            from data.loaders import load_proteomics
            prot = load_proteomics()
        except FileNotFoundError:
            return {
                "error": "Proteomics data not available.",
                "summary": "Proteomics data not available — skipping. Provide proteomics data for full analysis.",
            }
    else:
        prot = pd.read_csv(proteomics_path, index_col=0)

    # Score: selectivity × |mean_degradation| × log2(n_degraders + 1)
    results = []
    for protein in prot.index:
        values = prot.loc[protein].dropna()
        degraded = values[values < -0.5]
        if len(degraded) == 0:
            continue

        n_degraders = len(degraded)
        mean_deg = degraded.mean()
        # Selectivity: fraction of compounds that degrade it (lower = more selective)
        selectivity = 1.0 - (n_degraders / len(values))

        score = selectivity * abs(mean_deg) * np.log2(n_degraders + 1)

        results.append({
            "protein": protein,
            "score": score,
            "n_degraders": n_degraders,
            "mean_degradation": mean_deg,
            "selectivity": selectivity,
        })

    if not results:
        return {
            "summary": f"No neosubstrate candidates found in {len(prot)} proteins (none degraded below -0.5 LFC)",
            "top_targets": [],
            "n_proteins_scored": 0,
        }

    df = pd.DataFrame(results).sort_values("score", ascending=False).head(top_n)

    # Map UniProt IDs to gene symbols if protein IDs look like UniProt accessions
    top_proteins = df["protein"].tolist()
    if top_proteins and all(len(p) >= 6 and p[0].isalpha() and any(c.isdigit() for c in p) and " " not in p for p in top_proteins[:3]):
        try:
            import httpx
            # Batch lookup via UniProt ID mapping
            ids_str = ",".join(top_proteins)
            resp = httpx.get(
                "https://rest.uniprot.org/uniprotkb/accessions",
                params={"accessions": ids_str, "fields": "accession,gene_primary"},
                headers={"Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code == 200:
                entries = resp.json().get("results", [])
                id_to_gene = {}
                for entry in entries:
                    acc = entry.get("primaryAccession", "")
                    genes = entry.get("genes", [])
                    if genes:
                        gene_name = genes[0].get("geneName", {}).get("value", "")
                        if gene_name:
                            id_to_gene[acc] = gene_name
                if id_to_gene:
                    df["gene_symbol"] = df["protein"].map(id_to_gene)
        except Exception:
            pass

    return {
        "summary": f"Top {min(top_n, len(results))} neosubstrate candidates scored from {len(prot)} proteins",
        "top_targets": df.to_dict("records"),
        "n_proteins_scored": len(results),
    }


@registry.register(
    name="target.coessentiality",
    description="Find co-essential and synthetic lethal partners for a target gene using DepMap CRISPR data",
    category="target",
    parameters={"gene": "Gene symbol", "top_n": "Number of partners to return"},
    requires_data=["depmap_crispr"],
    usage_guide="You need to validate a drug target by finding functionally related genes, or identify synthetic lethal partners for combination therapy. Also useful for understanding pathway context of a gene.",
)
def coessentiality(gene: str, top_n: int = 20, **kwargs) -> dict:
    """Compute co-essentiality network for a gene."""
    from data.loaders import load_crispr

    crispr = load_crispr()

    if gene not in crispr.columns:
        return {"error": f"Gene {gene} not found in DepMap CRISPR data", "summary": f"Gene {gene} not found in DepMap CRISPR data"}
    target_vals = crispr[gene].dropna()

    correlations = []
    for other_gene in crispr.columns:
        if other_gene == gene:
            continue
        other_vals = crispr[other_gene].dropna()
        common = target_vals.index.intersection(other_vals.index)
        if len(common) < 50:
            continue

        from scipy import stats
        r, p = stats.pearsonr(target_vals[common], other_vals[common])
        correlations.append({"gene": other_gene, "r": r, "p": p})

    if not correlations:
        return {
            "summary": f"Co-essentiality network for {gene}: no genes with sufficient shared cell lines (>=50)",
            "gene": gene,
            "co_essential": [],
            "synthetic_lethal": [],
        }

    df = pd.DataFrame(correlations).sort_values("r", ascending=False)

    co_essential = df.head(top_n).to_dict("records")
    synthetic_lethal = df.tail(top_n).sort_values("r").to_dict("records")

    return {
        "summary": f"Co-essentiality network for {gene}: {len(correlations)} genes tested",
        "gene": gene,
        "co_essential": co_essential,
        "synthetic_lethal": synthetic_lethal,
    }
