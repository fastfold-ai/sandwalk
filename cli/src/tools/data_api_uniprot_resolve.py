"""data_api.uniprot_lookup: entry resolution (direct accession or ranked search). Split from tools/data_api.py."""
from tools import data_api as _data_api
from tools.data_api_uniprot_helpers import (
    _build_uniprot_search_candidates,
    _extract_species_phrases,
    _keyword_fallback_query,
    _query_has_non_human_hints,
)
from tools.data_api_uniprot_scoring import _entry_relevance_score


def resolve_organism_clause(organism: str, query: str) -> tuple[str, str | None]:
    """Returns (organism_clean, org_clause)."""
    organism_ids = {"human": 9606, "mouse": 10090, "rat": 10116, "zebrafish": 7955, "drosophila": 7227, "yeast": 559292}
    organism_clean = (organism or "human").strip()
    organism_lc = organism_clean.lower()

    org_clause = None
    if organism_lc not in ("", "any", "all", "none"):
        if organism_lc.isdigit():
            org_clause = f"organism_id:{organism_lc}"
        elif organism_lc in organism_ids:
            org_clause = f"organism_id:{organism_ids[organism_lc]}"
        else:
            escaped = organism_clean.replace('"', "")
            if escaped:
                org_clause = f'organism_name:"{escaped}"'

    # If caller left default "human" but query clearly targets non-human organisms
    # (e.g., helminth parasite proteins), do not force a human-only filter.
    if organism_lc == "human" and _query_has_non_human_hints(query):
        org_clause = None

    return organism_clean, org_clause


def resolve_entries(query: str, org_clause: str | None) -> dict:
    """Fetch candidate UniProt entries via direct accession lookup or ranked search.

    Returns a dict with keys: entries, matched_query, attempted_queries, error (optional).
    """
    is_accession = len(query) >= 6 and query[0].isalpha() and any(c.isdigit() for c in query)
    species_phrases = _extract_species_phrases(query)
    non_human_hints = _query_has_non_human_hints(query)
    matched_query = None
    attempted_queries: list[str] = []

    try:
        entries = []
        if is_accession and " " not in query:
            resp = _data_api._http_get(
                f"https://rest.uniprot.org/uniprotkb/{query}", headers={"Accept": "application/json"}, timeout=15, retries=2,
            )
            if resp.status_code == 200:
                entries = [resp.json()]

        if not entries:
            base_query = " ".join((query or "").split())
            compact_query = _keyword_fallback_query(base_query)
            search_candidates = _build_uniprot_search_candidates(query=base_query, compact_query=compact_query, org_clause=org_clause)

            last_status = None
            best_entry = None
            best_score = float("-inf")
            for search_query in search_candidates:
                attempted_queries.append(search_query)
                resp = _data_api._http_get(
                    "https://rest.uniprot.org/uniprotkb/search",
                    params={"query": search_query, "format": "json", "size": 10},
                    headers={"Accept": "application/json"},
                    timeout=15,
                    retries=2,
                )
                last_status = resp.status_code
                if resp.status_code != 200:
                    continue
                hits = resp.json().get("results", [])
                if not hits:
                    continue

                for hit in hits:
                    s = _entry_relevance_score(hit, original_query=query, species_phrases=species_phrases, non_human_hints=non_human_hints)
                    if s > best_score:
                        best_score, best_entry, matched_query = s, hit, search_query

                if best_score >= 4.0:
                    break

            if best_entry is not None:
                entries = [best_entry]

            if not entries and last_status not in (None, 200):
                return {
                    "entries": [], "matched_query": matched_query, "attempted_queries": attempted_queries,
                    "error": {
                        "error": f"UniProt search failed (HTTP {last_status})",
                        "summary": f"UniProt search failed for '{query}'",
                        "search_attempts": attempted_queries,
                    },
                }
    except Exception as e:
        return {
            "entries": [], "matched_query": matched_query, "attempted_queries": attempted_queries,
            "error": {"error": f"UniProt API error: {e}", "summary": f"UniProt query failed for '{query}'"},
        }

    if entries and non_human_hints:
        org_name = str((entries[0].get("organism", {}) or {}).get("scientificName", "")).lower()
        if "homo sapiens" in org_name and matched_query is not None:
            return {
                "entries": [], "matched_query": matched_query, "attempted_queries": attempted_queries,
                "error": {
                    "error": (
                        "Only human hits were returned for a non-human/parasite query. "
                        "Please specify organism='any' or a concrete parasite species (taxid/scientific name)."
                    ),
                    "summary": f"UniProt: no reliable non-human match for '{query}'",
                    "search_attempts": attempted_queries,
                },
            }

    return {"entries": entries, "matched_query": matched_query, "attempted_queries": attempted_queries, "error": None}
