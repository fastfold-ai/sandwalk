"""
expression.l1000_similarity: transcriptomic signature similarity search.

Split from tools/expression.py.
"""

import pandas as pd

from tools import registry


@registry.register(
    name="expression.l1000_similarity",
    description="Find compounds with similar or opposite L1000 transcriptomic signatures",
    category="expression",
    parameters={"compound_id": "Query compound", "mode": "'similar' or 'opposite'", "top_n": "Number of hits"},
    requires_data=["l1000"],
    usage_guide="You want to find compounds with similar mechanisms (mode='similar') or complementary/opposing effects (mode='opposite'). Use for drug repurposing or finding synergy partners.",
)
def l1000_similarity(compound_id: str, mode: str = "similar", top_n: int = 20, **kwargs) -> dict:
    """Find transcriptionally similar or anti-correlated compounds."""
    from sklearn.metrics.pairwise import cosine_similarity

    from data.loaders import load_l1000
    from tools._compound_resolver import resolve_compound

    compound_id = resolve_compound(compound_id, dataset="l1000")

    l1000 = load_l1000()

    if compound_id not in l1000.index:
        return {"error": f"Compound {compound_id} not found in L1000 data", "summary": f"Compound {compound_id} not found in L1000 data"}
    query = l1000.loc[compound_id].values.reshape(1, -1)
    sims = cosine_similarity(query, l1000.values)[0]
    sim_df = pd.DataFrame({"compound": l1000.index, "cosine_similarity": sims})
    sim_df = sim_df[sim_df["compound"] != compound_id]

    if mode == "similar":
        hits = sim_df.nlargest(top_n, "cosine_similarity")
    elif mode == "opposite":
        hits = sim_df.nsmallest(top_n, "cosine_similarity")
    else:
        return {"error": f"Unknown mode: {mode}. Use 'similar' or 'opposite'", "summary": f"Unknown mode: {mode}. Use 'similar' or 'opposite'"}
    return {
        "summary": f"Top {top_n} {mode} compounds to {compound_id}",
        "query": compound_id,
        "mode": mode,
        "hits": hits.to_dict("records"),
    }
