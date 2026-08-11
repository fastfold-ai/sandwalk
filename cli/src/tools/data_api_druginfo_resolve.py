"""data_api.drug_info: PubChem name-to-CID resolution. Split from tools/data_api.py."""
import re

from tools import data_api as _data_api

PUG_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUGVIEW_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view"


def query_candidates(text: str) -> list[str]:
    candidates = []
    seen = set()

    def _add(candidate: str):
        c = " ".join((candidate or "").split()).strip()
        if not c or c.lower() in seen:
            return
        seen.add(c.lower())
        candidates.append(c)

    _add(text)
    for part in re.split(r"[;,/|()]|\bor\b|\band\b", text, flags=re.IGNORECASE):
        _add(part)
    for token in text.split():
        cleaned = token.strip(" ,;:/|()[]{}")
        if len(cleaned) >= 3 and re.search(r"[A-Za-z]", cleaned):
            _add(cleaned)
    return candidates


def resolve_cid(raw_query: str) -> tuple[int | None, str, dict | None]:
    """Resolve a drug name to a PubChem CID, trying alias/fallback candidates.

    Returns (cid, resolved_query, error).
    """
    import urllib.parse

    cid = None
    resolved_query = raw_query
    lookup_errors = []
    for candidate in query_candidates(raw_query):
        encoded_query = urllib.parse.quote(candidate, safe="")
        try:
            resp = _data_api._http_get(f"{PUG_BASE}/compound/name/{encoded_query}/cids/JSON", timeout=10, retries=2)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            cid_data = resp.json()
        except Exception as e:
            lookup_errors.append(f"{candidate}: {e}")
            continue

        cids = cid_data.get("IdentifierList", {}).get("CID", [])
        if cids:
            cid = cids[0]
            resolved_query = candidate
            break

    if cid is None:
        if lookup_errors:
            return None, resolved_query, {
                "error": f"PubChem CID lookup failed: {lookup_errors[0]}",
                "summary": f"PubChem CID lookup failed for '{raw_query}'",
                "tried_queries": query_candidates(raw_query)[:5],
            }
        return None, resolved_query, {
            "error": f"Drug '{raw_query}' not found in PubChem",
            "summary": f"PubChem: no compound found for '{raw_query}'",
            "tried_queries": query_candidates(raw_query)[:5],
        }

    return cid, resolved_query, None
