"""CRO tool: side-by-side comparison of selected CROs."""

from tools import registry


@registry.register(
    name="cro.compare",
    description="Side-by-side comparison of selected CROs from built-in directory on services, pricing, and capabilities",
    category="cro",
    parameters={
        "cro_ids": "List of CRO IDs to compare (e.g. ['reaction-biology', 'promega'])",
    },
    usage_guide="You have shortlisted CROs and need to compare them on services, pricing, and capabilities before making a decision.",
)
def compare(cro_ids: list[str], **kwargs) -> dict:
    """Compare selected CROs side-by-side."""
    from tools.cro import _load_cro_db  # indirect import so tests can patch tools.cro._load_cro_db

    db = _load_cro_db()
    id_to_cro = {cro["id"]: cro for cro in db}

    comparisons = []
    not_found = []

    for cro_id in cro_ids:
        cro = id_to_cro.get(cro_id)
        if not cro:
            not_found.append(cro_id)
            continue

        services_summary = {
            s["category"]: {
                "turnaround_days": s["turnaround_days"],
                "price_range": s["price_range"],
            }
            for s in cro.get("services", [])
        }

        comparisons.append({
            "id": cro["id"],
            "name": cro["name"],
            "headquarters": cro["headquarters"],
            "size": cro["size"],
            "website": cro["website"],
            "services": services_summary,
            "capabilities": cro.get("capabilities", []),
            "specialties": cro.get("specialties", []),
            "therapeutic_areas": cro.get("therapeutic_areas", []),
        })

    # Build comparison matrix for common service categories
    all_categories = set()
    for comp in comparisons:
        all_categories.update(comp["services"].keys())

    names = [c["name"] for c in comparisons]
    summary = f"[PLACEHOLDER] Comparison of {len(comparisons)} CROs from static directory (not live data): {', '.join(names)}"
    if not_found:
        summary += f" (not found: {', '.join(not_found)})"

    return {
        "summary": summary,
        "placeholder": True,
        "comparisons": comparisons,
        "service_categories": sorted(all_categories),
        "not_found": not_found,
    }
