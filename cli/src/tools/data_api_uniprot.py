"""data_api.uniprot_lookup: comprehensive protein information from UniProt. Split from tools/data_api.py."""
from tools import registry
from tools.data_api_uniprot_extract import extract_fields
from tools.data_api_uniprot_resolve import resolve_entries, resolve_organism_clause


@registry.register(
    name="data_api.uniprot_lookup",
    description="Look up comprehensive protein information from UniProt by gene symbol, UniProt ID, or protein name",
    category="data_api",
    parameters={
        "query": "Gene symbol, UniProt accession (e.g. P04637), or protein name",
        "organism": "Organism filter: common name (human/mouse/...), taxonomy ID, or 'any' (default 'human')",
    },
    requires_data=[],
    usage_guide="You need detailed protein information: function, domains, subcellular location, GO terms, PDB structures, disease involvement, tissue specificity. Comprehensive UniProt protein profile.",
)
def uniprot_lookup(query: str, organism: str = "human", **kwargs) -> dict:
    """Look up comprehensive protein data from UniProt REST API."""
    organism_clean, org_clause = resolve_organism_clause(organism, query)

    resolved = resolve_entries(query, org_clause)
    if resolved["error"]:
        return resolved["error"]

    entries = resolved["entries"]
    if not entries:
        return {
            "error": f"No UniProt entry found for '{query}' (organism: {organism_clean or 'any'})",
            "summary": f"UniProt: no results for '{query}'",
            "search_attempts": resolved["attempted_queries"],
        }

    return extract_fields(entries[0], query, org_clause, resolved["matched_query"])
