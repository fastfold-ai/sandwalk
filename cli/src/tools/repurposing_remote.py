"""Remote-fallback response formatting for repurposing.cmap_query."""

from tools.repurposing_l1000fwd import _query_l1000fwd


def _remote_fallback(gene_signature: dict, source: str, mode: str, top_n: int, allow_remote: bool) -> dict:
    """Handle the no-local-L1000 path: try L1000FWD, else return external-tool guidance."""
    up_genes = sorted([g for g, v in gene_signature.items() if v > 0])
    down_genes = sorted([g for g, v in gene_signature.items() if v < 0])
    remote_error = None

    if allow_remote:
        remote_hits, remote_error = _query_l1000fwd(up_genes, down_genes, mode, top_n)
        if remote_hits:
            top3_str = ", ".join(
                f"{h['compound']}(score={h['connectivity_score']:.3f})"
                if isinstance(h.get("connectivity_score"), float)
                else h["compound"]
                for h in remote_hits[:3]
            )
            return {
                "summary": (
                    f"Remote CMap query via L1000FWD ({source}, mode={mode}): "
                    f"{len(remote_hits)} hit(s) returned. Top hits: {top3_str}"
                ),
                "source": source,
                "mode": mode,
                "remote_source": "L1000FWD",
                "local_data_unavailable": True,
                "remote_used": True,
                "hits": remote_hits,
                "up_genes": up_genes[:100],
                "down_genes": down_genes[:100],
            }

    remote_note = f"Remote fallback attempt failed: {remote_error}\n" if (allow_remote and remote_error) else ""
    summary = (
        f"L1000 data not loaded -- cannot compute correlations locally.\n"
        f"Query signature: {len(up_genes)} up, {len(down_genes)} down genes.\n"
        f"{remote_note}"
        f"For external CMap query, use these gene lists at:\n"
        f"  - CLUE (https://clue.io/query)\n"
        f"  - SigCom LINCS (https://maayanlab.cloud/sigcom-lincs/)\n"
        f"  - L1000FWD (https://maayanlab.cloud/L1000FWD/)\n"
        f"Upload up-genes and down-genes separately."
    )
    return {
        "summary": summary,
        "source": source,
        "mode": mode,
        "up_genes": up_genes[:100],
        "down_genes": down_genes[:100],
        "data_unavailable": True,
        "remote_used": False,
        "remote_error": remote_error if allow_remote else None,
        "external_resources": [
            {"name": "CLUE", "url": "https://clue.io/query"},
            {"name": "SigCom LINCS", "url": "https://maayanlab.cloud/sigcom-lincs/"},
            {"name": "L1000FWD", "url": "https://maayanlab.cloud/L1000FWD/"},
        ],
        "hits": [],
    }
