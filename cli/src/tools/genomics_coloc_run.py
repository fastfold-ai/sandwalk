"""genomics.coloc: query execution with complexity-aware retry/fallback. Split from tools/genomics.py."""
from tools import genomics as _genomics
from tools.genomics_coloc_queries import OT_HEADERS, OT_URL, QUERY_FULL, QUERY_LEAN


def _run_query(ensembl: str, query_text: str, page_attempts: tuple[tuple[int, int], ...]) -> tuple[dict | None, str | None]:
    last_err = None
    for size, coloc_size in page_attempts:
        resp, query_error = _genomics.request(
            "POST",
            OT_URL,
            json={"query": query_text, "variables": {"ensemblId": ensembl, "size": size, "colocSize": coloc_size}},
            headers=OT_HEADERS,
            timeout=15,
            retries=2,
            raise_for_status=False,
        )
        if query_error:
            last_err = f"Open Targets API error: {query_error}"
            continue
        if resp.status_code != 200:
            last_err = f"Open Targets API returned HTTP {resp.status_code}"
            # Retry with smaller page sizes for likely complexity-related rejections.
            if resp.status_code in {400, 413, 422, 429, 500, 502, 503, 504}:
                continue
            break

        try:
            payload = resp.json()
        except Exception:
            last_err = "Open Targets API returned invalid JSON"
            continue

        gql_errors = payload.get("errors") or []
        if gql_errors:
            msgs = "; ".join(e.get("message", "") for e in gql_errors)
            last_err = f"Open Targets GraphQL errors: {msgs}"
            lower = msgs.lower()
            if any(tok in lower for tok in ("complex", "depth", "cost", "too many", "timeout")):
                continue
            break
        return payload, None
    return None, (last_err or "Open Targets colocalization query failed")


def query_target_coloc(ensembl: str) -> tuple[dict | None, str | None]:
    # Try richer query first, then lower-complexity fallback.
    attempts = (
        ("full", QUERY_FULL, ((60, 40), (30, 20), (15, 10))),
        ("lean", QUERY_LEAN, ((40, 20), (20, 10), (10, 5))),
    )
    errors = []
    for label, query_text, page_attempts in attempts:
        payload, err = _run_query(ensembl, query_text, page_attempts)
        if payload is not None:
            return payload, None
        if err:
            errors.append(f"{label} query: {err}")
    if errors:
        return None, "; ".join(errors)
    return None, "Open Targets colocalization query failed"
