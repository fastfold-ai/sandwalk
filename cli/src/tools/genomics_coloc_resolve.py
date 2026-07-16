"""genomics.coloc: gene symbol alias handling + Ensembl ID resolution. Split from tools/genomics.py."""
from tools import genomics as _genomics

_ALIAS_MAP = {"GBA1": "GBA", "PARK2": "PRKN"}


def gene_symbol_candidates(input_gene: str) -> list[str]:
    token = (input_gene or "").strip()
    if not token:
        return []
    candidates = [token]
    mapped = _ALIAS_MAP.get(token.upper())
    if mapped:
        candidates.append(mapped)

    # Stable de-dup preserving order (case-insensitive).
    deduped = []
    seen = set()
    for c in candidates:
        k = c.upper()
        if k in seen:
            continue
        seen.add(k)
        deduped.append(c)
    return deduped


def resolve_ensembl_id(symbol: str) -> tuple[str | None, str | None]:
    ens_resp, resolve_error = _genomics.request(
        "GET",
        f"https://rest.ensembl.org/lookup/symbol/homo_sapiens/{symbol}",
        params={"content-type": "application/json"},
        timeout=10,
        retries=2,
        headers={"Content-Type": "application/json"},
        raise_for_status=False,
    )
    if resolve_error:
        return None, f"Failed to resolve {symbol} to Ensembl ID: {resolve_error}"
    if ens_resp.status_code != 200:
        return None, f"Gene {symbol} not found in Ensembl (human)"
    try:
        ens_data = ens_resp.json()
    except Exception:
        return None, f"Failed to parse Ensembl response for {symbol}"
    ensembl = ens_data.get("id", "")
    if not ensembl:
        return None, f"Gene {symbol} not found in Ensembl (human)"
    return ensembl, None
