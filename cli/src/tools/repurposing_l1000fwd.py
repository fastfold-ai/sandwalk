"""L1000FWD remote API helpers for repurposing.cmap_query."""


def _to_float(value):
    """Best-effort float conversion for heterogeneous API payloads."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_l1000fwd_hits(payload: dict | list, mode: str) -> list:
    """Extract mode-specific hits from L1000FWD response payload."""
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    if mode == "reverse":
        primary_keys = ("opposite", "reverse", "discordant", "anti")
    else:
        primary_keys = ("similar", "mimic", "concordant")

    secondary_keys = ("results", "topn", "data")

    for key in primary_keys:
        hits = payload.get(key)
        if isinstance(hits, list):
            return hits

    for section in secondary_keys:
        nested = payload.get(section)
        if not isinstance(nested, dict):
            continue
        for key in primary_keys:
            hits = nested.get(key)
            if isinstance(hits, list):
                return hits

    return []


def _normalize_l1000fwd_hit(hit, rank: int) -> dict:
    """Normalize one L1000FWD hit into a stable ct-friendly shape."""
    if not isinstance(hit, dict):
        return {
            "rank": rank,
            "compound": str(hit),
            "connectivity_score": None,
            "raw": hit,
        }

    compound = (
        hit.get("pert_iname")
        or hit.get("name")
        or hit.get("drug")
        or hit.get("sig_id")
        or hit.get("id")
        or f"hit_{rank}"
    )
    score = (
        _to_float(hit.get("score"))
        or _to_float(hit.get("combined_score"))
        or _to_float(hit.get("combined_scores"))
        or _to_float(hit.get("tau"))
        or _to_float(hit.get("zscore"))
        or _to_float(hit.get("zscores"))
    )
    p_value = _to_float(hit.get("p_value")) or _to_float(hit.get("pval")) or _to_float(hit.get("pvals"))
    q_value = _to_float(hit.get("q_value")) or _to_float(hit.get("qval")) or _to_float(hit.get("qvals"))

    normalized = {
        "rank": rank,
        "compound": compound,
        "connectivity_score": score,
    }
    if p_value is not None:
        normalized["p_value"] = p_value
    if q_value is not None:
        normalized["q_value"] = q_value
    normalized["raw"] = hit
    return normalized


def _query_l1000fwd(up_genes: list[str], down_genes: list[str], mode: str, top_n: int) -> tuple[list, str | None]:
    """Query free L1000FWD API and return normalized hits."""
    # Lazy + indirect import so tests can patch tools.repurposing.request_json.
    from tools.repurposing import request_json

    if not up_genes and not down_genes:
        return [], "Signature is empty after separating up/down genes"

    search_payload = {
        "up_genes": up_genes,
        "down_genes": down_genes,
    }
    search_data, search_error = request_json(
        "POST",
        "https://maayanlab.cloud/L1000FWD/sig_search",
        json=search_payload,
        timeout=45,
        retries=1,
    )
    if search_error:
        return [], f"L1000FWD sig_search failed: {search_error}"
    if not isinstance(search_data, dict):
        return [], "L1000FWD sig_search returned unexpected payload"

    result_id = search_data.get("result_id") or search_data.get("id")
    if not result_id:
        return [], "L1000FWD did not return a result_id"

    result_data, result_error = request_json(
        "GET",
        f"https://maayanlab.cloud/L1000FWD/result/topn/{result_id}",
        timeout=45,
        retries=1,
    )
    if result_error:
        return [], f"L1000FWD topn lookup failed for {result_id}: {result_error}"

    raw_hits = _extract_l1000fwd_hits(result_data, mode=mode)
    if not raw_hits:
        return [], f"L1000FWD returned no {mode} hits"

    hits = [_normalize_l1000fwd_hit(hit, rank=i + 1) for i, hit in enumerate(raw_hits[:top_n])]
    return hits, None
