"""
target.disease_association: Open Targets Platform disease association query.

Split from tools/target.py.
"""

from tools import registry
from tools.http_client import request


@registry.register(
    name="target.disease_association",
    description="Query Open Targets Platform for disease associations of a gene target",
    category="target",
    parameters={"gene": "Gene symbol (e.g. BRAF, TP53)", "min_score": "Minimum association score (default 0.1)"},
    requires_data=[],
    usage_guide="You want to know which diseases a target is associated with — genetic evidence, drug evidence, literature support. Essential for indication selection and target validation.",
)
def disease_association(gene: str, min_score: float = 0.1, **kwargs) -> dict:
    """Query Open Targets for disease associations of a gene."""
    # Step 1: Resolve gene symbol to Ensembl ID
    ensembl_id = None
    ens_resp, ens_error = request(
        "GET",
        f"https://rest.ensembl.org/lookup/symbol/homo_sapiens/{gene}",
        params={"content-type": "application/json"},
        timeout=10,
        headers={"Content-Type": "application/json"},
        raise_for_status=False,
    )
    if ens_error:
        return {
            "error": f"Failed to resolve {gene} to Ensembl ID: {ens_error}",
            "summary": f"Could not resolve gene symbol {gene} via Ensembl REST API",
        }
    if ens_resp.status_code == 200:
        try:
            ens_data = ens_resp.json()
            ensembl_id = ens_data.get("id", "")
        except Exception:
            ensembl_id = None

    if not ensembl_id:
        return {
            "error": f"Gene {gene} not found in Ensembl (human)",
            "summary": f"Gene symbol {gene} could not be resolved to an Ensembl ID",
        }

    # Step 2: Query Open Targets GraphQL
    query = """
    query targetDiseases($ensemblId: String!, $size: Int!) {
      target(ensemblId: $ensemblId) {
        approvedSymbol
        approvedName
        associatedDiseases(page: {index: 0, size: $size}) {
          count
          rows {
            disease {
              id
              name
            }
            score
            datasourceScores {
              id
              score
            }
          }
        }
      }
    }
    """

    ot_resp, ot_error = request(
        "POST",
        "https://api.platform.opentargets.org/api/v4/graphql",
        json={
            "query": query,
            "variables": {
                "ensemblId": ensembl_id,
                "size": 50,
            },
        },
        timeout=10,
        headers={"Content-Type": "application/json"},
        raise_for_status=False,
    )
    if ot_error:
        return {
            "error": f"Open Targets API error: {ot_error}",
            "summary": f"Failed to query Open Targets for {gene}",
        }
    if ot_resp.status_code != 200:
        return {
            "error": f"Open Targets API returned HTTP {ot_resp.status_code}",
            "summary": f"Open Targets query failed for {gene} ({ensembl_id})",
        }
    try:
        ot_data = ot_resp.json()
    except Exception:
        return {
            "error": "Open Targets returned invalid JSON",
            "summary": f"Failed to parse Open Targets response for {gene}",
        }

    target_data = ot_data.get("data", {}).get("target")
    if not target_data:
        return {
            "error": f"No target data returned from Open Targets for {ensembl_id}",
            "summary": f"Open Targets has no entry for {gene} ({ensembl_id})",
        }

    approved_symbol = target_data.get("approvedSymbol", gene)
    approved_name = target_data.get("approvedName", "")
    assoc_data = target_data.get("associatedDiseases", {})
    total_count = assoc_data.get("count", 0)
    rows = assoc_data.get("rows", [])

    # Parse associations
    associations = []
    for row in rows:
        overall_score = row.get("score", 0)
        if overall_score < min_score:
            continue

        disease = row.get("disease", {})
        disease_id = disease.get("id", "")
        disease_name = disease.get("name", "")

        # Parse datasource scores into readable categories
        ds_scores = {}
        for ds in row.get("datasourceScores", []):
            comp_id = ds.get("id") or ds.get("componentId", "")
            ds_score = ds.get("score", 0)
            ds_scores[comp_id] = round(ds_score, 4)

        # Extract key evidence categories
        genetic_score = max(
            ds_scores.get("ot_genetics_portal", 0),
            ds_scores.get("gene_burden", 0),
            ds_scores.get("genomics_england", 0),
            ds_scores.get("eva", 0),
            ds_scores.get("uniprot_variants", 0),
        )
        drug_score = max(
            ds_scores.get("chembl", 0),
            ds_scores.get("europepmc", 0),
        )
        literature_score = ds_scores.get("europepmc", 0)

        associations.append({
            "disease_id": disease_id,
            "disease_name": disease_name,
            "overall_score": round(overall_score, 4),
            "genetic_association": round(genetic_score, 4),
            "known_drug": round(drug_score, 4),
            "literature": round(literature_score, 4),
            "all_datasource_scores": ds_scores,
        })

    associations.sort(key=lambda x: x["overall_score"], reverse=True)

    # Build summary
    n_filtered = len(associations)
    top_diseases = ", ".join(a["disease_name"] for a in associations[:5])
    if not top_diseases:
        top_diseases = "none"

    summary = (
        f"Disease associations for {approved_symbol} ({approved_name}): "
        f"{n_filtered} diseases above score {min_score} (out of {total_count} total). "
        f"Top: {top_diseases}."
    )

    return {
        "summary": summary,
        "gene": approved_symbol,
        "ensembl_id": ensembl_id,
        "approved_name": approved_name,
        "total_associations": total_count,
        "filtered_associations": n_filtered,
        "min_score": min_score,
        "associations": associations,
    }
