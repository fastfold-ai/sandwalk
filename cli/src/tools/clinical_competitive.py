"""clinical.competitive_landscape: aggregate competitive intel from trials, ChEMBL, Open Targets.

Split from tools/clinical.py. Calls ``request_json``/``trial_search`` indirectly via the
``tools.clinical`` hub module so that ``patch("tools.clinical.trial_search")`` in tests
continues to work regardless of which submodule performs the call.
"""

from tools import clinical as _clinical
from tools import registry


@registry.register(
    name="clinical.competitive_landscape",
    description="Aggregate competitive intelligence for a target or indication from trials, ChEMBL, and Open Targets",
    category="clinical",
    parameters={
        "gene": "Target gene symbol (e.g. CRBN, BRAF, EGFR)",
        "indication": "Optional indication to focus the search (e.g. 'melanoma', 'lung cancer')",
    },
    usage_guide="You want a comprehensive view of the competitive landscape around a drug target — combines ClinicalTrials.gov, ChEMBL, and Open Targets to show active programs, phase distribution, and mechanism diversity. Use for strategic positioning and differentiation.",
)
def competitive_landscape(gene: str, indication: str = "", **kwargs) -> dict:
    """Aggregate competitive intelligence from multiple sources.

    Combines:
    1. ClinicalTrials.gov: active clinical programs
    2. ChEMBL: known compounds and bioactivities against the target
    3. Open Targets: known drugs and mechanisms via GraphQL
    """
    try:
        import httpx
    except ImportError:
        return {"error": "httpx required (pip install httpx)", "summary": "httpx required (pip install httpx)"}
    results = {
        "gene": gene,
        "indication": indication or "all",
    }

    # --- Source 1: ClinicalTrials.gov ---
    ct_query = f"{gene} {indication}".strip() if indication else gene
    trial_data = _clinical.trial_search(query=ct_query)

    if "error" not in trial_data:
        results["trials"] = {
            "total_count": trial_data.get("total_count", 0),
            "phase_distribution": trial_data.get("phase_distribution", {}),
            "status_distribution": trial_data.get("status_distribution", {}),
            "top_trials": trial_data.get("trials", [])[:10],
        }
    else:
        results["trials"] = {"error": trial_data["error"], "total_count": 0}

    # --- Source 2: ChEMBL target search + activities ---
    chembl_compounds = []
    chembl_base = "https://www.ebi.ac.uk/chembl/api/data"
    headers = {"Accept": "application/json"}

    try:
        # Find target in ChEMBL
        tgt_data, error = _clinical.request_json(
            "GET",
            f"{chembl_base}/target/search.json",
            params={"q": gene, "limit": 5},
            headers=headers,
            timeout=10,
            retries=2,
        )
        if error:
            raise RuntimeError(error)

        targets = tgt_data.get("targets", [])
        chembl_target_id = None
        for tgt in targets:
            # Prefer human SINGLE PROTEIN targets
            if (tgt.get("organism", "") == "Homo sapiens" and
                    tgt.get("target_type", "") == "SINGLE PROTEIN"):
                chembl_target_id = tgt.get("target_chembl_id")
                break

        if not chembl_target_id and targets:
            chembl_target_id = targets[0].get("target_chembl_id")

        if chembl_target_id:
            # Get activities for the target
            act_data, error = _clinical.request_json(
                "GET",
                f"{chembl_base}/activity.json",
                params={
                    "target_chembl_id": chembl_target_id,
                    "limit": 50,
                    "standard_type__in": "IC50,Ki,Kd,EC50",
                },
                headers=headers,
                timeout=10,
                retries=2,
            )
            if error:
                raise RuntimeError(error)

            # Deduplicate by molecule
            seen_mols = set()
            moa_types = set()
            for act in act_data.get("activities", []):
                mol_id = act.get("molecule_chembl_id", "")
                if mol_id and mol_id not in seen_mols:
                    seen_mols.add(mol_id)
                    chembl_compounds.append({
                        "chembl_id": mol_id,
                        "name": act.get("molecule_pref_name", "") or mol_id,
                        "activity_type": act.get("standard_type", ""),
                        "activity_value": act.get("standard_value"),
                        "activity_units": act.get("standard_units", ""),
                        "pchembl": act.get("pchembl_value"),
                    })
                    assay_desc = act.get("assay_description", "")
                    if assay_desc:
                        # Extract broad MoA categories from assay descriptions
                        desc_lower = assay_desc.lower()
                        if "inhibit" in desc_lower:
                            moa_types.add("Inhibitor")
                        if "degrad" in desc_lower:
                            moa_types.add("Degrader")
                        if "agonist" in desc_lower:
                            moa_types.add("Agonist")
                        if "antagonist" in desc_lower:
                            moa_types.add("Antagonist")
                        if "allosteric" in desc_lower:
                            moa_types.add("Allosteric modulator")
                        if "antibod" in desc_lower:
                            moa_types.add("Antibody")
                        if "covalent" in desc_lower:
                            moa_types.add("Covalent binder")

            results["chembl"] = {
                "target_chembl_id": chembl_target_id,
                "unique_compounds": len(chembl_compounds),
                "moa_types": sorted(moa_types),
                "top_compounds": chembl_compounds[:15],
            }
        else:
            results["chembl"] = {"error": f"No ChEMBL target found for {gene}", "unique_compounds": 0}

    except Exception as e:
        results["chembl"] = {"error": f"ChEMBL query failed: {e}", "unique_compounds": 0}

    # --- Source 3: Open Targets known drugs (GraphQL) ---
    ot_drugs = []
    ot_url = "https://api.platform.opentargets.org/api/v4/graphql"
    graphql_query = """
    query knownDrugs($ensemblId: String!) {
      target(ensemblId: $ensemblId) {
        id
        approvedSymbol
        knownDrugs(size: 30) {
          uniqueDrugs
          uniqueTargets
          rows {
            drugId
            prefName
            drugType
            mechanismOfAction
            phase
            status
            disease {
              id
              name
            }
          }
        }
      }
    }
    """

    # Map gene symbol to Ensembl ID via Open Targets search
    try:
        search_data, error = _clinical.request_json(
            "POST",
            ot_url,
            json={
                "query": """
                query searchTarget($q: String!) {
                  search(queryString: $q, entityNames: ["target"], page: {size: 5, index: 0}) {
                    hits {
                      id
                      name
                      entity
                    }
                  }
                }
                """,
                "variables": {"q": gene},
            },
            timeout=10,
            retries=2,
        )
        if error:
            raise RuntimeError(error)

        hits = search_data.get("data", {}).get("search", {}).get("hits", [])
        ensembl_id = None
        for hit in hits:
            if hit.get("entity") == "target":
                ensembl_id = hit.get("id")
                break

        if ensembl_id:
            drugs_data, error = _clinical.request_json(
                "POST",
                ot_url,
                json={
                    "query": graphql_query,
                    "variables": {"ensemblId": ensembl_id},
                },
                timeout=10,
                retries=2,
            )
            if error:
                raise RuntimeError(error)

            known_drugs = drugs_data.get("data", {}).get("target", {}).get("knownDrugs", {})
            if known_drugs:
                unique_drugs = known_drugs.get("uniqueDrugs", 0)
                phase_dist_ot = {}
                moa_set = set()

                for row in known_drugs.get("rows", []):
                    drug_name = row.get("prefName", "") or row.get("drugId", "")
                    phase = row.get("phase", 0)
                    moa = row.get("mechanismOfAction", "")
                    disease = row.get("disease", {})
                    disease_name = disease.get("name", "") if disease else ""

                    # Filter by indication if specified
                    if indication and disease_name:
                        if indication.lower() not in disease_name.lower():
                            continue

                    ot_drugs.append({
                        "drug": drug_name,
                        "drug_type": row.get("drugType", ""),
                        "mechanism": moa,
                        "phase": phase,
                        "status": row.get("status", ""),
                        "disease": disease_name,
                    })

                    phase_key = f"Phase {phase}" if phase else "Unknown"
                    phase_dist_ot[phase_key] = phase_dist_ot.get(phase_key, 0) + 1
                    if moa:
                        moa_set.add(moa)

                results["open_targets"] = {
                    "ensembl_id": ensembl_id,
                    "unique_drugs": unique_drugs,
                    "phase_distribution": phase_dist_ot,
                    "mechanisms": sorted(moa_set),
                    "drugs": ot_drugs[:20],
                }
            else:
                results["open_targets"] = {"error": "No known drugs found", "unique_drugs": 0}
        else:
            results["open_targets"] = {"error": f"Could not resolve Ensembl ID for {gene}", "unique_drugs": 0}

    except Exception as e:
        results["open_targets"] = {"error": f"Open Targets query failed: {e}", "unique_drugs": 0}

    # --- Aggregate summary ---
    total_trials = results.get("trials", {}).get("total_count", 0)
    chembl_count = results.get("chembl", {}).get("unique_compounds", 0)
    ot_count = results.get("open_targets", {}).get("unique_drugs", 0)

    trial_phases = results.get("trials", {}).get("phase_distribution", {})
    chembl_moas = results.get("chembl", {}).get("moa_types", [])
    ot_moas = results.get("open_targets", {}).get("mechanisms", [])
    all_moas = sorted(set(chembl_moas + ot_moas))

    phase_str = ", ".join(f"{k}: {v}" for k, v in sorted(trial_phases.items())) if trial_phases else "none"
    moa_str = ", ".join(all_moas[:5]) if all_moas else "not characterized"

    ind_label = f" in {indication}" if indication else ""
    summary = (
        f"Competitive landscape for {gene}{ind_label}:\n"
        f"Clinical trials: {total_trials} ({phase_str})\n"
        f"ChEMBL compounds: {chembl_count}\n"
        f"Open Targets known drugs: {ot_count}\n"
        f"Mechanism diversity: {moa_str}"
    )

    results["summary"] = summary
    return results
