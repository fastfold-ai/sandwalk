"""data_api.opentargets_search: GraphQL search + detail fetch. Split from tools/data_api.py."""
from tools import data_api as _data_api

_OT_URL = "https://api.platform.opentargets.org/api/v4/graphql"
_OT_HEADERS = {"Content-Type": "application/json"}


def ot_search_entity(query: str, entity_type: str) -> tuple[str, dict | None]:
    """Resolve a query string to an Open Targets entity ID via the search endpoint."""
    search_gql = """
    query search($q: String!, $entities: [String!]!) {
        search(queryString: $q, entityNames: $entities, page: {size: 5, index: 0}) {
            total
            hits { id entity name description }
        }
    }
    """
    entity_names = {"target": ["target"], "disease": ["disease"], "drug": ["drug"]}

    try:
        search_resp = _data_api._http_post(
            _OT_URL,
            json={"query": search_gql, "variables": {"q": query, "entities": entity_names[entity_type]}},
            headers=_OT_HEADERS,
            timeout=15,
        )
        search_resp.raise_for_status()
        search_data = search_resp.json()
    except Exception as e:
        import httpx
        if isinstance(e, httpx.TimeoutException):
            return "", {"error": f"Open Targets search timed out for '{query}'", "summary": f"Open Targets timed out for '{query}'"}
        if isinstance(e, httpx.HTTPError):
            return "", {"error": f"Open Targets search failed: {e}", "summary": "Open Targets search failed"}
        return "", {"error": f"Open Targets search failed: {e}", "summary": "Open Targets search failed"}

    hits = search_data.get("data", {}).get("search", {}).get("hits", [])
    if not hits:
        return "", {
            "error": f"No {entity_type} found for '{query}' in Open Targets",
            "summary": f"Open Targets: no {entity_type} matches for '{query}'",
        }

    return hits[0]["id"], None


def ot_fetch_detail(entity_id: str, entity_type: str) -> tuple[dict, dict | None]:
    """Fetch the detailed entity profile for a resolved Open Targets entity ID."""
    if entity_type == "target":
        detail_gql = """
        query targetProfile($id: String!) {
            target(ensemblId: $id) {
                id
                approvedSymbol
                approvedName
                biotype
                functionDescriptions
                subcellularLocations { location }
                tractability {
                    label
                    modality
                    value
                }
                associatedDiseases(page: {size: 10, index: 0}) {
                    count
                    rows {
                        disease { id name }
                        score
                    }
                }
                knownDrugs(size: 10) {
                    uniqueDrugs
                    rows {
                        prefName
                        drugType
                        mechanismOfAction
                        phase
                    }
                }
            }
        }
        """
    elif entity_type == "disease":
        detail_gql = """
        query diseaseProfile($id: String!) {
            disease(efoId: $id) {
                id
                name
                description
                therapeuticAreas { id name }
                associatedTargets(page: {size: 10, index: 0}) {
                    count
                    rows {
                        target { id approvedSymbol }
                        score
                    }
                }
                knownDrugs(size: 10) {
                    uniqueDrugs
                    rows {
                        prefName
                        drugType
                        phase
                        mechanismOfAction
                    }
                }
            }
        }
        """
    else:  # drug
        detail_gql = """
        query drugProfile($id: String!) {
            drug(chemblId: $id) {
                id
                name
                drugType
                maximumClinicalTrialPhase
                hasBeenWithdrawn
                description
                mechanismsOfAction {
                    rows {
                        mechanismOfAction
                        targets { id approvedSymbol }
                    }
                }
                indications {
                    count
                    rows {
                        disease { id name }
                        maxPhaseForIndication
                    }
                }
            }
        }
        """

    try:
        detail_resp = _data_api._http_post(
            _OT_URL, json={"query": detail_gql, "variables": {"id": entity_id}}, headers=_OT_HEADERS, timeout=15,
        )
        detail_resp.raise_for_status()
        detail_data = detail_resp.json()
    except Exception as e:
        import httpx
        if isinstance(e, httpx.TimeoutException):
            return {}, {"error": f"Open Targets detail query timed out for {entity_id}", "summary": "Open Targets detail timed out"}
        if isinstance(e, httpx.HTTPError):
            return {}, {"error": f"Open Targets detail query failed: {e}", "summary": "Open Targets detail query failed"}
        return {}, {"error": f"Open Targets detail query failed: {e}", "summary": "Open Targets detail query failed"}

    return detail_data.get("data", {}), None
