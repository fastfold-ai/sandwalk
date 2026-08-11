"""data_api.chembl_advanced: dispatch to per-search-type ChEMBL helpers. Split from tools/data_api.py."""
from tools import registry
from tools.data_api_chembl_activities import _chembl_target_activities
from tools.data_api_chembl_compound import _chembl_compound_search
from tools.data_api_chembl_mechanism import _chembl_drug_indication, _chembl_mechanism


@registry.register(
    name="data_api.chembl_advanced",
    description="Advanced ChEMBL queries: compound details, target activity statistics, mechanisms, drug indications",
    category="data_api",
    parameters={
        "query": "Compound name/ChEMBL ID, target gene, or drug name",
        "search_type": "Query type: 'compound', 'target_activities', 'mechanism', or 'drug_indication' (default 'compound')",
    },
    requires_data=[],
    usage_guide="You want detailed ChEMBL data: full compound properties, aggregated bioactivity statistics for a target (min/max/median IC50), drug mechanisms of action, or approved indications. More detailed than literature.chembl_query.",
)
def chembl_advanced(query: str, search_type: str = "compound", **kwargs) -> dict:
    """Advanced ChEMBL REST API queries with aggregated statistics."""
    valid_types = ("compound", "target_activities", "mechanism", "drug_indication")
    if search_type not in valid_types:
        return {"error": f"Invalid search_type '{search_type}'. Choose from: {', '.join(valid_types)}", "summary": f"Invalid ChEMBL search type '{search_type}'"}

    chembl_base = "https://www.ebi.ac.uk/chembl/api/data"
    headers = {"Accept": "application/json"}

    if search_type == "compound":
        return _chembl_compound_search(query, chembl_base, headers)
    elif search_type == "target_activities":
        return _chembl_target_activities(query, chembl_base, headers)
    elif search_type == "mechanism":
        return _chembl_mechanism(query, chembl_base, headers)
    else:  # drug_indication
        return _chembl_drug_indication(query, chembl_base, headers)
