"""data_api.uniprot_lookup: query normalization helpers. Split from tools/data_api.py."""
import re


_UNIPROT_NON_HUMAN_HINTS = (
    "helminth",
    "parasite",
    "schistosoma",
    "fasciola",
    "heligmosomoides",
    "nematode",
    "trematode",
    "cestode",
    "worm",
    "brugia",
    "filaria",
)

_UNIPROT_QUERY_STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "from", "with", "without",
    "in", "on", "of", "to", "by", "via", "as", "that", "this", "these",
    "those", "are", "is", "was", "were", "be", "been", "being", "it",
    "its", "their", "minimal", "annotation", "annotations", "key", "keys",
    "look", "lookup", "search", "find", "protein", "proteins", "immunomodulatory",
}


def _query_has_non_human_hints(query: str) -> bool:
    q = (query or "").lower()
    return any(hint in q for hint in _UNIPROT_NON_HUMAN_HINTS)


def _keyword_fallback_query(query: str, max_terms: int = 7) -> str:
    tokens = re.findall(r"[A-Za-z0-9_-]+", (query or "").lower())
    selected = []
    for tok in tokens:
        if len(tok) < 3:
            continue
        if tok in _UNIPROT_QUERY_STOPWORDS:
            continue
        if tok not in selected:
            selected.append(tok)
        if len(selected) >= max_terms:
            break
    return " ".join(selected)


def _extract_species_phrases(query: str, max_species: int = 3) -> list[str]:
    """Extract likely binomial species names from free-text query."""
    tokens = re.findall(r"[A-Za-z][A-Za-z-]*", query or "")
    species: list[str] = []
    for i in range(len(tokens) - 1):
        genus_raw = tokens[i]
        species_raw = tokens[i + 1]
        genus = genus_raw.lower()
        epithet = species_raw.lower()

        if len(genus) < 3 or len(epithet) < 3:
            continue
        if genus in _UNIPROT_QUERY_STOPWORDS or epithet in _UNIPROT_QUERY_STOPWORDS:
            continue
        if not epithet.isalpha():
            continue
        if not (genus in _UNIPROT_NON_HUMAN_HINTS or genus_raw[0].isupper()):
            continue

        phrase = f"{genus.capitalize()} {epithet}"
        if phrase not in species:
            species.append(phrase)
        if len(species) >= max_species:
            break
    return species


def _build_uniprot_search_candidates(
    *,
    query: str,
    compact_query: str,
    org_clause: str | None,
) -> list[str]:
    """Generate ranked UniProt search candidates for robust retrieval."""
    q = (query or "").strip()
    q_lc = q.lower()
    species = _extract_species_phrases(q)
    candidates: list[str] = []

    def add(candidate: str):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    if q:
        if org_clause:
            add(f"({q}) AND {org_clause}")
        add(q)

    if compact_query and compact_query != q:
        if org_clause:
            add(f"({compact_query}) AND {org_clause}")
        add(compact_query)

    wants_secreted = any(x in q_lc for x in ("secreted", "excretory", "extracellular", "vesicle", "ev "))
    wants_uncharacterized = any(x in q_lc for x in ("uncharacterized", "understudied", "novel", "hypothetical"))
    wants_scp_taps = any(
        x in q_lc for x in ("venom allergen", "scp", "taps", "val", "cap superfamily", "allergen-like")
    )

    for sp in species:
        sp_clause = f'organism_name:"{sp}"'
        add(sp_clause)
        if wants_secreted:
            add(f'{sp_clause} AND (secreted OR excretory OR extracellular)')
        if wants_uncharacterized:
            add(f'{sp_clause} AND (uncharacterized OR hypothetical)')
        if wants_scp_taps:
            add(f'{sp_clause} AND ("venom allergen" OR SCP OR TAPS OR VAL)')

    if _query_has_non_human_hints(q):
        add("parasite")
        add("helminth")
        add("schistosoma")
        add("fasciola")
        add("heligmosomoides")
        if wants_secreted:
            add("(parasite OR helminth) AND (secreted OR excretory OR extracellular)")
        if wants_scp_taps:
            add('(parasite OR helminth) AND ("venom allergen" OR SCP OR TAPS OR VAL)')

    # Keep search bounded to avoid excessive API calls.
    return candidates[:12]
