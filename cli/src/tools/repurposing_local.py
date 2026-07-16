"""Local L1000-matrix correlation helpers for repurposing.cmap_query."""

import numpy as np


def _correlate_against_l1000(l1000, query_vec, compounds, exclude=None, common_genes=None):
    """Pearson-correlate a query vector against every compound row in L1000."""
    from scipy import stats as sp_stats

    results = []
    for cpd in compounds:
        if exclude is not None and cpd == exclude:
            continue
        other_vec = (
            l1000.loc[cpd, common_genes].values.astype(float)
            if common_genes is not None
            else l1000.loc[cpd].values
        )
        valid = ~(np.isnan(query_vec) | np.isnan(other_vec))
        if valid.sum() < 10:
            continue
        r, p = sp_stats.pearsonr(query_vec[valid], other_vec[valid])
        results.append({
            "compound": cpd,
            "correlation": round(float(r), 4),
            "p_value": float(p),
            "n_genes": int(valid.sum()),
        })
    return results


def _rank_and_classify_hits(results: list[dict], mode: str, top_n: int) -> list[dict]:
    """Sort correlation results by mode and tag each hit's correlation strength."""
    if mode == "similar":
        results.sort(key=lambda x: x["correlation"], reverse=True)
    else:  # reverse
        results.sort(key=lambda x: x["correlation"])

    top_hits = results[:top_n]
    for hit in top_hits:
        r = hit["correlation"]
        if abs(r) > 0.5:
            hit["strength"] = "strong"
        elif abs(r) > 0.3:
            hit["strength"] = "moderate"
        else:
            hit["strength"] = "weak"
    return top_hits
