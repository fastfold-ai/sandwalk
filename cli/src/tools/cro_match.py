"""CRO tool: rank built-in CRO directory entries by fit for an experiment."""

from tools import registry


@registry.register(
    name="cro.match_experiment",
    description="Rank CROs from built-in directory by fit for a specific experiment type, target, and compound",
    category="cro",
    parameters={
        "assay_type": "Experiment/assay type (e.g. cell_based_assay, structural_biology, in_vivo_efficacy)",
        "target": "Target protein or gene (optional)",
        "compound": "Compound name or class (optional)",
        "species": "Species for the experiment (default: human)",
        "scale": "Scale: small, medium, large (default: small)",
    },
    usage_guide="You have a specific experiment in mind and need to find the best-fit CRO. Run after experiment.design_assay to match the assay to capable vendors.",
)
def match_experiment(assay_type: str, target: str = None,
                     compound: str = None, species: str = "human",
                     scale: str = "small", **kwargs) -> dict:
    """Score and rank all CROs for a specific experiment."""
    from tools.cro import _load_cro_db, _score_cro  # indirect import for test patchability

    db = _load_cro_db()
    scored = []

    for cro in db:
        score = _score_cro(cro, assay_type, target, compound, species, scale)
        if score > 0:
            # Find matching service for pricing/turnaround
            matching_service = None
            for svc in cro.get("services", []):
                if svc["category"] == assay_type:
                    matching_service = svc
                    break

            entry = {
                "id": cro["id"],
                "name": cro["name"],
                "score": score,
                "headquarters": cro["headquarters"],
                "size": cro["size"],
                "relevant_capabilities": [
                    c for c in cro.get("capabilities", [])
                    if any(kw in c.lower() for kw in [
                        assay_type.lower().replace("_", " "),
                        "degradation", "protac", "tpd", "glue",
                    ] + ([target.lower()] if target else []))
                ],
            }
            if matching_service:
                entry["turnaround_days"] = matching_service["turnaround_days"]
                entry["price_range"] = matching_service["price_range"]

            scored.append(entry)

    scored.sort(key=lambda x: x["score"], reverse=True)

    top_names = ", ".join(s["name"] for s in scored[:3]) if scored else "none"
    return {
        "summary": (
            f"[PLACEHOLDER] CRO matching for {assay_type}"
            + (f" (target={target})" if target else "")
            + (f" (compound={compound})" if compound else "")
            + f": {len(scored)} CROs scored from static directory (not live data), top matches: {top_names}"
        ),
        "placeholder": True,
        "assay_type": assay_type,
        "target": target,
        "compound": compound,
        "species": species,
        "scale": scale,
        "ranked_cros": scored,
    }
