"""CRO tool: full-text search across the built-in CRO directory."""

from tools import registry


@registry.register(
    name="cro.search",
    description="Search built-in CRO directory by keyword, service type, or therapeutic area",
    category="cro",
    parameters={
        "query": "Free-text search across CRO names, capabilities, and specialties",
        "service_type": "Filter by service category (e.g. cell_based_assay, structural_biology)",
        "therapeutic_area": "Filter by therapeutic area (e.g. oncology, neuroscience)",
    },
    usage_guide="You need to find CROs that offer a specific service or work in a therapeutic area. Use for initial CRO discovery before match_experiment.",
)
def search(query: str, service_type: str = None,
           therapeutic_area: str = None, **kwargs) -> dict:
    """Full-text search across CRO database with optional filtering."""
    from tools.cro import _load_cro_db  # indirect import so tests can patch tools.cro._load_cro_db

    db = _load_cro_db()
    query_lower = query.lower()
    results = []

    for cro in db:
        # Build searchable text
        searchable = " ".join([
            cro["name"],
            " ".join(cro.get("capabilities", [])),
            " ".join(cro.get("specialties", [])),
            " ".join(cro.get("therapeutic_areas", [])),
        ]).lower()

        if query_lower not in searchable:
            continue

        # Filter by service_type
        if service_type:
            service_cats = [s["category"] for s in cro.get("services", [])]
            if service_type not in service_cats:
                continue

        # Filter by therapeutic_area
        if therapeutic_area:
            areas = [t.lower() for t in cro.get("therapeutic_areas", [])]
            if therapeutic_area.lower() not in areas:
                continue

        results.append({
            "id": cro["id"],
            "name": cro["name"],
            "headquarters": cro["headquarters"],
            "size": cro["size"],
            "capabilities": cro.get("capabilities", []),
            "specialties": cro.get("specialties", []),
            "services": [s["category"] for s in cro.get("services", [])],
        })

    return {
        "summary": f"[PLACEHOLDER] CRO search for '{query}': {len(results)} matches from static directory (not live data)",
        "placeholder": True,
        "query": query,
        "filters": {"service_type": service_type, "therapeutic_area": therapeutic_area},
        "results": results,
    }
