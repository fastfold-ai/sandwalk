"""Combination therapy tool: synergy prediction from anti-correlated L1000 signatures."""

import pandas as pd

from tools import registry


@registry.register(
    name="combination.synergy_predict",
    description="Predict synergistic compound pairs from anti-correlated L1000 transcriptomic signatures",
    category="combination",
    parameters={
        "compound_id": "Query compound (or 'all' for full pairwise)",
        "top_n": "Number of top synergy candidates to return",
    },
    requires_data=["l1000", "prism", "depmap_model"],
    usage_guide="You want to find compounds that work well together — anti-correlated transcriptomic profiles suggest complementary mechanisms. Use for rational combination therapy design.",
)
def synergy_predict(compound_id: str = "all", top_n: int = 20, **kwargs) -> dict:
    """Find synergistic compound pairs based on anti-correlated L1000 signatures.

    Synergy score = |anti-correlation| x tissue_complementarity x potency_bonus
    """
    from sklearn.metrics.pairwise import cosine_similarity

    from data.loaders import load_l1000, load_model_metadata, load_prism
    from tools._compound_resolver import resolve_compound

    if compound_id != "all":
        compound_id = resolve_compound(compound_id, dataset="l1000")

    l1000 = load_l1000()

    # Compute pairwise cosine similarity
    sim_matrix = cosine_similarity(l1000.values)
    compounds = l1000.index.tolist()

    # Build PRISM tissue profiles for complementarity
    prism = load_prism()
    model = load_model_metadata()
    ccle_to_lineage = {}
    for _, row in model.iterrows():
        ccle = row.get("CCLEName", "")
        lin = row.get("OncotreeLineage", "Unknown")
        if pd.notna(ccle) and pd.notna(lin):
            ccle_to_lineage[ccle] = lin

    # Compute per-compound tissue profiles (mean LFC per lineage at max dose)
    tissue_profiles = {}
    for cpd in prism["pert_name"].unique():
        cpd_data = prism[prism["pert_name"] == cpd]
        max_dose = cpd_data["pert_dose"].max()
        cpd_hd = cpd_data[cpd_data["pert_dose"] == max_dose].copy()
        cpd_hd["lineage"] = cpd_hd["ccle_name"].map(ccle_to_lineage)
        tissue_mean = cpd_hd.groupby("lineage")["LFC"].mean()
        tissue_profiles[cpd] = tissue_mean

    # Find anti-correlated pairs
    if compound_id != "all" and compound_id in compounds:
        query_idx = compounds.index(compound_id)
        query_compounds = [compound_id]
    else:
        query_compounds = compounds
        query_idx = None

    ANTICORR_THRESHOLD = -0.3
    results = []

    for _i, cpd1 in enumerate(query_compounds):
        idx1 = compounds.index(cpd1) if query_idx is None else query_idx
        for j in range(len(compounds)):
            if j <= idx1 and query_idx is None:
                continue
            cpd2 = compounds[j]
            if cpd1 == cpd2:
                continue

            cosine = sim_matrix[idx1, j]
            if cosine >= ANTICORR_THRESHOLD:
                continue

            # Tissue complementarity
            tissue_comp = 0.5  # default
            if cpd1 in tissue_profiles and cpd2 in tissue_profiles:
                t1 = tissue_profiles[cpd1]
                t2 = tissue_profiles[cpd2]
                common = t1.index.intersection(t2.index)
                if len(common) >= 3:
                    kills_1 = t1[common] < -0.3
                    kills_2 = t2[common] < -0.3
                    comp_tissues = (kills_1 & ~kills_2).sum() + (kills_2 & ~kills_1).sum()
                    overlap_tissues = (kills_1 & kills_2).sum()
                    tissue_comp = comp_tissues / (comp_tissues + overlap_tissues + 0.001)

            # Synergy score
            anticorr_strength = abs(cosine)
            score = anticorr_strength * (0.4 + 0.6 * tissue_comp)

            # Potency bonus
            if cpd1 in tissue_profiles and cpd2 in tissue_profiles:
                pot1 = abs(tissue_profiles[cpd1].mean()) if len(tissue_profiles[cpd1]) > 0 else 0
                pot2 = abs(tissue_profiles[cpd2].mean()) if len(tissue_profiles[cpd2]) > 0 else 0
                avg_potency = (pot1 + pot2) / 2.0
                score *= (1.0 + min(avg_potency, 2.0) / 4.0)

            results.append({
                "compound_1": cpd1,
                "compound_2": cpd2,
                "cosine_similarity": round(float(cosine), 4),
                "anticorrelation_strength": round(float(anticorr_strength), 4),
                "tissue_complementarity": round(float(tissue_comp), 4),
                "synergy_score": round(float(score), 4),
            })

    if not results:
        return {
            "summary": f"Synergy prediction: 0 anti-correlated pairs (cosine < {ANTICORR_THRESHOLD}). No synergistic candidates found.",
            "n_pairs": 0,
            "top_candidates": [],
        }

    df = pd.DataFrame(results).sort_values("synergy_score", ascending=False)
    top_hits = df.head(top_n)

    return {
        "summary": (
            f"Synergy prediction: {len(df)} anti-correlated pairs (cosine < {ANTICORR_THRESHOLD})\n"
            f"Top synergy score: {top_hits.iloc[0]['synergy_score']:.4f}" if len(top_hits) > 0 else "No pairs found"
        ),
        "n_pairs": len(df),
        "top_candidates": top_hits.to_dict("records"),
    }
