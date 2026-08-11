"""data_api.opentargets_search: response formatting per entity type. Split from tools/data_api.py."""


def format_target(target: dict, query: str, entity_id: str) -> dict:
    assoc = target.get("associatedDiseases", {})
    n_diseases = assoc.get("count", 0)
    top_diseases = [
        {"disease": r["disease"]["name"], "score": round(r["score"], 3)} for r in assoc.get("rows", [])
    ]
    known_drugs = target.get("knownDrugs", {})
    n_drugs = known_drugs.get("uniqueDrugs", 0)
    drug_rows = known_drugs.get("rows", [])
    tractability = target.get("tractability", [])

    top_disease_str = ", ".join(f"{d['disease']} ({d['score']:.2f})" for d in top_diseases[:3])
    return {
        "summary": (
            f"Open Targets: {target.get('approvedSymbol', query)} — "
            f"{n_diseases} disease associations, "
            f"top: {top_disease_str or 'none'}. "
            f"{n_drugs} known drug(s)."
        ),
        "entity_type": "target",
        "entity_id": entity_id,
        "approved_symbol": target.get("approvedSymbol", ""),
        "approved_name": target.get("approvedName", ""),
        "biotype": target.get("biotype", ""),
        "function": target.get("functionDescriptions", []),
        "tractability": tractability,
        "n_disease_associations": n_diseases,
        "top_diseases": top_diseases,
        "n_known_drugs": n_drugs,
        "known_drugs": [
            {
                "name": d.get("prefName", ""),
                "type": d.get("drugType", ""),
                "mechanism": d.get("mechanismOfAction", ""),
                "phase": d.get("phase", 0),
            }
            for d in drug_rows[:10]
        ],
    }


def format_disease(disease: dict, query: str, entity_id: str) -> dict:
    assoc = disease.get("associatedTargets", {})
    n_targets = assoc.get("count", 0)
    top_targets = [
        {"gene": r["target"]["approvedSymbol"], "score": round(r["score"], 3)} for r in assoc.get("rows", [])
    ]
    therapeutic_areas = [ta["name"] for ta in disease.get("therapeuticAreas", [])]
    known_drugs = disease.get("knownDrugs", {})
    n_drugs = known_drugs.get("uniqueDrugs", 0)

    top_target_str = ", ".join(f"{t['gene']} ({t['score']:.2f})" for t in top_targets[:3])
    return {
        "summary": (
            f"Open Targets: {disease.get('name', query)} — "
            f"{n_targets} associated targets, "
            f"top: {top_target_str or 'none'}. "
            f"Areas: {', '.join(therapeutic_areas[:3]) or 'N/A'}."
        ),
        "entity_type": "disease",
        "entity_id": entity_id,
        "name": disease.get("name", ""),
        "description": disease.get("description", ""),
        "therapeutic_areas": therapeutic_areas,
        "n_associated_targets": n_targets,
        "top_targets": top_targets,
        "n_known_drugs": n_drugs,
    }


def format_drug(drug: dict, query: str, entity_id: str) -> dict:
    moa_rows = drug.get("mechanismsOfAction", {}).get("rows", [])
    indications = drug.get("indications", {})
    n_indications = indications.get("count", 0)
    ind_rows = indications.get("rows", [])

    mechanisms = [m.get("mechanismOfAction", "") for m in moa_rows]
    return {
        "summary": (
            f"Open Targets: {drug.get('name', query)} — "
            f"{drug.get('drugType', 'unknown')} drug, "
            f"max phase {drug.get('maximumClinicalTrialPhase', 'N/A')}, "
            f"{n_indications} indications."
        ),
        "entity_type": "drug",
        "entity_id": entity_id,
        "name": drug.get("name", ""),
        "drug_type": drug.get("drugType", ""),
        "max_clinical_phase": drug.get("maximumClinicalTrialPhase"),
        "withdrawn": drug.get("hasBeenWithdrawn", False),
        "description": drug.get("description", ""),
        "mechanisms": mechanisms,
        "n_indications": n_indications,
        "indications": [
            {"disease": r["disease"]["name"], "max_phase": r.get("maxPhaseForIndication")} for r in ind_rows[:15]
        ],
    }
