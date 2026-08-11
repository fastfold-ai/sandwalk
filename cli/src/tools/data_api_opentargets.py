"""data_api.opentargets_search: Open Targets Platform GraphQL profile lookup. Split from tools/data_api.py."""
from tools import data_api as _data_api
from tools import registry
from tools.data_api_opentargets_format import format_disease, format_drug, format_target
from tools.data_api_opentargets_gql import ot_fetch_detail, ot_search_entity


@registry.register(
    name="data_api.opentargets_search",
    description="Search Open Targets Platform for comprehensive target, disease, or drug profiles",
    category="data_api",
    parameters={
        "query": "Gene name, disease name, or drug name",
        "entity_type": "Entity type: 'target', 'disease', or 'drug' (default 'target')",
    },
    requires_data=[],
    usage_guide="You want a comprehensive profile from Open Targets: disease associations for a target, associated targets for a disease, or indications/mechanisms for a drug. General-purpose Open Targets access.",
)
def opentargets_search(query: str, entity_type: str = "target", **kwargs) -> dict:
    """Query Open Targets Platform GraphQL API for target/disease/drug profiles."""
    valid_types = ("target", "disease", "drug")
    if entity_type not in valid_types:
        return {"error": f"Invalid entity_type '{entity_type}'. Choose from: {', '.join(valid_types)}", "summary": f"Invalid entity type '{entity_type}'"}

    # Normalize query based on entity type
    if entity_type == "target":
        query = _data_api._normalize_gene_name(query)
    elif entity_type == "drug":
        query = _data_api._normalize_drug_query(query)

    entity_id, error = ot_search_entity(query, entity_type)
    if error:
        return error

    data_root, error = ot_fetch_detail(entity_id, entity_type)
    if error:
        return error

    if entity_type == "target":
        return format_target(data_root.get("target") or {}, query, entity_id)
    elif entity_type == "disease":
        return format_disease(data_root.get("disease") or {}, query, entity_id)
    else:
        return format_drug(data_root.get("drug") or {}, query, entity_id)
