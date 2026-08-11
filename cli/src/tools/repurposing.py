"""Drug repurposing tools: connectivity map queries, signature matching.

Split across repurposing_local.py (local L1000 correlation) and
repurposing_l1000fwd.py (remote API fallback); re-exported here for
backward compatibility.
"""

import numpy as np

from tools import registry
from tools.http_client import request_json
from tools.repurposing_l1000fwd import (
    _extract_l1000fwd_hits,
    _normalize_l1000fwd_hit,
    _query_l1000fwd,
    _to_float,
)
from tools.repurposing_local import _correlate_against_l1000, _rank_and_classify_hits
from tools.repurposing_remote import _remote_fallback

__all__ = [
    "cmap_query",
    "_to_float",
    "_extract_l1000fwd_hits",
    "_normalize_l1000fwd_hit",
    "_query_l1000fwd",
    "request_json",
]


@registry.register(
    name="repurposing.cmap_query",
    description="Query for drug repurposing opportunities using L1000 connectivity map signature matching",
    category="repurposing",
    parameters={
        "gene_signature": "Dict of gene:value (expression changes), used as query signature",
        "compound_id": "Compound ID to use as query (pulls L1000 signature; alternative to gene_signature)",
        "mode": "'similar' (same mechanism) or 'reverse' (opposing signature, e.g. disease reversal)",
        "top_n": "Number of top hits to return (default 20)",
        "allow_remote": "If true and local L1000 is unavailable, try free L1000FWD API fallback",
    },
    requires_data=[],
    usage_guide="You want to find drug repurposing opportunities — compounds with similar signatures "
                "(shared mechanism) or reverse signatures (disease-reversing). Provide a gene signature "
                "dict or compound_id. Use mode='reverse' to find compounds that reverse a disease signature. "
                "Works best with local L1000 data; if unavailable, can query the free L1000FWD API.",
)
def cmap_query(gene_signature: dict = None, compound_id: str = None,
               mode: str = "similar", top_n: int = 20,
               allow_remote: bool = True, **kwargs) -> dict:
    """Query for drug repurposing via connectivity map signature matching.

    Strategy:
    1. If compound_id provided + L1000 loaded: correlate that compound's signature
       with all other compounds in the L1000 matrix.
    2. If gene_signature provided + L1000 loaded: correlate the query signature
       against all compounds in L1000.
    3. If L1000 not available: return guidance for external CMap queries.
    """
    if gene_signature is None and compound_id is None:
        return {"error": "Provide either gene_signature (dict) or compound_id", "summary": "Provide either gene_signature (dict) or compound_id"}
    if mode not in ("similar", "reverse"):
        return {"error": f"Unknown mode '{mode}'. Use 'similar' or 'reverse'", "summary": f"Unknown mode '{mode}'. Use 'similar' or 'reverse'"}

    l1000 = None
    try:
        from data.loaders import load_l1000
        l1000 = load_l1000()
    except (FileNotFoundError, ImportError):
        pass

    if compound_id is not None and l1000 is not None:
        if compound_id not in l1000.index:
            return {"error": f"Compound {compound_id} not found in L1000 data", "summary": f"Compound {compound_id} not found in L1000 data"}
        query_series = l1000.loc[compound_id]
        query_genes = set(query_series.index)
        source = f"compound {compound_id} (L1000)"
    elif gene_signature is not None:
        query_genes = set(gene_signature.keys())
        source = f"provided signature ({len(query_genes)} genes)"
        query_series = None
    else:
        return {"error": "compound_id not found in L1000 and no gene_signature provided", "summary": "compound_id not found in L1000 and no gene_signature provided"}

    results = None
    if l1000 is not None:
        if query_series is not None:
            results = _correlate_against_l1000(l1000, query_series.values, l1000.index.tolist(), exclude=compound_id)
        else:
            common_genes = sorted(query_genes & set(l1000.columns))
            if len(common_genes) >= 10:
                query_vec = np.array([gene_signature[g] for g in common_genes])
                results = _correlate_against_l1000(l1000, query_vec, l1000.index.tolist(), common_genes=common_genes)

    if results is not None:
        if not results:
            return {"summary": "No correlations computed -- insufficient overlapping data", "source": source, "mode": mode, "hits": []}

        top_hits = _rank_and_classify_hits(results, mode, top_n)
        desc = "similar mechanism (positively correlated)" if mode == "similar" else "signature-reversing (negatively correlated)"
        best_r = top_hits[0]["correlation"] if top_hits else 0
        strong = sum(1 for h in top_hits if h["strength"] == "strong")
        moderate = sum(1 for h in top_hits if h["strength"] == "moderate")
        top3_str = ", ".join(f"{h['compound']}(r={h['correlation']:.3f})" for h in top_hits[:3])

        summary = (
            f"CMap query ({source}, mode={mode}):\n"
            f"Searching for: {desc}\n"
            f"Top {len(top_hits)} hits: {strong} strong, {moderate} moderate\n"
            f"Best matches: {top3_str}\n"
            f"Best correlation: {best_r:.4f}"
        )
        return {"summary": summary, "source": source, "mode": mode, "n_compounds_screened": len(results), "hits": top_hits}

    if gene_signature is not None:
        return _remote_fallback(gene_signature, source, mode, top_n, allow_remote)

    return {
        "summary": "L1000 data not available and no gene_signature provided for external query",
        "error": "Load L1000 data (sandwalk data pull l1000) or provide a gene_signature dict",
        "hits": [],
    }
