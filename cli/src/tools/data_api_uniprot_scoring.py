"""data_api.uniprot_lookup: search-hit relevance scoring. Split from tools/data_api.py."""
import re


def _entry_text_blob(entry: dict) -> str:
    parts: list[str] = []
    pd = entry.get("proteinDescription", {}) or {}
    rec = (pd.get("recommendedName", {}) or {}).get("fullName", {}) or {}
    if rec.get("value"):
        parts.append(str(rec.get("value")))
    for alt in (pd.get("alternativeNames", []) or []):
        full = (alt.get("fullName", {}) or {}).get("value")
        if full:
            parts.append(str(full))
    for kw in (entry.get("keywords", []) or []):
        name = kw.get("name")
        if name:
            parts.append(str(name))
    org = entry.get("organism", {}) or {}
    sci = org.get("scientificName")
    if sci:
        parts.append(str(sci))
    return " ".join(parts).lower()


def _entry_relevance_score(
    entry: dict,
    *,
    original_query: str,
    species_phrases: list[str],
    non_human_hints: bool,
) -> float:
    q_lc = (original_query or "").lower()
    blob = _entry_text_blob(entry)
    score = 0.0

    wants_secreted = any(x in q_lc for x in ("secreted", "excretory", "extracellular", "vesicle", "ev "))
    wants_uncharacterized = any(x in q_lc for x in ("uncharacterized", "understudied", "novel", "hypothetical"))
    wants_scp_taps = any(x in q_lc for x in ("venom allergen", "scp", "taps", "val", "cap superfamily"))

    # Species alignment dominates ranking.
    for sp in species_phrases:
        if sp.lower() in blob:
            score += 8.0
    if non_human_hints and "homo sapiens" in blob:
        score -= 10.0

    if wants_secreted and any(x in blob for x in ("secreted", "excretory", "extracellular", "signal peptide")):
        score += 3.0
    if wants_uncharacterized and any(x in blob for x in ("uncharacterized", "hypothetical", "putative")):
        score += 3.0
    if wants_scp_taps and any(x in blob for x in ("venom allergen", "scp", "taps", "val", "cap")):
        score += 4.0

    # Penalize clearly off-target "query not represented in entry text".
    query_tokens = [t for t in re.findall(r"[a-z0-9_-]+", q_lc) if len(t) >= 4]
    overlap = sum(1 for t in query_tokens[:8] if t in blob)
    score += min(overlap * 0.5, 2.0)

    entry_type = str(entry.get("entryType", "")).lower()
    if wants_uncharacterized and "unreviewed" in entry_type:
        score += 1.0

    return score
