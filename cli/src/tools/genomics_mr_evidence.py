"""genomics.mendelian_randomization_lookup: genetic evidence fetch + formatting. Split from tools/genomics.py."""
from tools import genomics as _genomics
from tools.genomics_mr_resolve import OT_HEADERS, OT_URL


def fetch_evidence(ensembl_id: str, efo_id: str) -> tuple[dict, dict | None]:
    """Query target-disease genetic evidence. Returns (data, error)."""
    # Genetic datasources: gwas_credible_sets (L2G scores), eva, gene_burden,
    # gene2phenotype, genomics_england, uniprot_literature
    evidence_query = """
    query targetDiseaseEvidence($ensemblId: String!, $efoId: String!) {
        target(ensemblId: $ensemblId) {
            id
            approvedSymbol
            approvedName
            associatedDiseases(BFilter: $efoId, page: {size: 1, index: 0}) {
                rows {
                    score
                    disease { id name }
                    datasourceScores {
                        id
                        score
                    }
                }
            }
            evidences(
                efoIds: [$efoId]
                datasourceIds: [
                    "gwas_credible_sets", "gene_burden", "eva",
                    "gene2phenotype", "genomics_england", "uniprot_literature"
                ]
                size: 50
            ) {
                count
                rows {
                    datasourceId
                    datatypeId
                    score
                    resourceScore
                    studyId
                    beta
                    oddsRatio
                    confidence
                    studySampleSize
                    publicationYear
                    variantRsId
                    credibleSet {
                        studyLocusId
                        study { id projectId studyType }
                        variant { id rsIds }
                        pValueMantissa
                        pValueExponent
                        beta
                        finemappingMethod
                    }
                }
            }
        }
        disease(efoId: $efoId) {
            id
            name
            description
        }
    }
    """

    result_data, error = _genomics.request_json(
        "POST", OT_URL, json={"query": evidence_query, "variables": {"ensemblId": ensembl_id, "efoId": efo_id}}, headers=OT_HEADERS, timeout=15, retries=2,
    )
    if error:
        return {}, {"error": f"Open Targets evidence query failed: {error}", "summary": f"Open Targets evidence query failed: {error}"}
    if result_data.get("errors"):
        error_msgs = [e.get("message", "") for e in result_data["errors"]]
        return {}, {"error": f"Open Targets GraphQL errors: {'; '.join(error_msgs)}", "summary": f"Open Targets GraphQL errors: {'; '.join(error_msgs)}"}
    return result_data.get("data", {}), None
