"""genomics.mendelian_randomization_lookup: evidence formatting/summary. Split from tools/genomics.py."""


def format_result(data: dict, gene: str, disease: str, ensembl_id: str, efo_id: str, disease_name: str) -> dict:
    target_info = data.get("target") or {}
    disease_info = data.get("disease") or {}
    approved_symbol = target_info.get("approvedSymbol", gene)
    approved_name = target_info.get("approvedName", "")
    resolved_disease = disease_info.get("name", disease_name if disease_name else disease)

    assoc_rows = target_info.get("associatedDiseases", {}).get("rows", [])
    overall_score = assoc_rows[0].get("score") if assoc_rows else None
    datasource_scores = {}
    if assoc_rows:
        for ds in assoc_rows[0].get("datasourceScores", []):
            datasource_scores[ds["id"]] = ds["score"]

    evidences_obj = target_info.get("evidences") or {}
    evidence_count = evidences_obj.get("count", 0)
    evidence_rows = evidences_obj.get("rows", [])

    gwas_evidence = []
    other_genetic_evidence = []

    for row in evidence_rows:
        datasource = row.get("datasourceId", "")
        credible_set = row.get("credibleSet") or {}
        variant_info = credible_set.get("variant") or {}
        study_info = credible_set.get("study") or {}
        rs_ids = variant_info.get("rsIds", [])
        variant_rsid = rs_ids[0] if rs_ids else (row.get("variantRsId") or "")

        p_mantissa = credible_set.get("pValueMantissa")
        p_exponent = credible_set.get("pValueExponent")
        p_value = None
        if p_mantissa is not None and p_exponent is not None:
            try:
                p_value = float(p_mantissa) * (10 ** int(p_exponent))
            except (ValueError, TypeError):
                pass

        evidence_item = {
            "datasource": datasource,
            "datatype": row.get("datatypeId", ""),
            "score": row.get("score"),
            "resource_score": row.get("resourceScore"),
            "variant_id": variant_info.get("id", ""),
            "variant_rsid": variant_rsid,
            "study_id": study_info.get("id") or row.get("studyId", ""),
            "study_type": study_info.get("studyType", ""),
            "p_value": p_value,
            "beta": credible_set.get("beta") or row.get("beta"),
            "odds_ratio": row.get("oddsRatio"),
            "finemapping_method": credible_set.get("finemappingMethod", ""),
            "publication_year": row.get("publicationYear"),
        }

        if datasource == "gwas_credible_sets":
            gwas_evidence.append(evidence_item)
        else:
            other_genetic_evidence.append(evidence_item)

    all_evidence = gwas_evidence + other_genetic_evidence
    max_score = max((e["score"] for e in all_evidence if e["score"] is not None), default=None)
    n_variants = len({e["variant_rsid"] for e in all_evidence if e["variant_rsid"]})
    n_studies = len({e["study_id"] for e in all_evidence if e["study_id"]})

    parts = []
    if gwas_evidence:
        parts.append(f"{len(gwas_evidence)} GWAS credible set(s)")
    if other_genetic_evidence:
        parts.append(f"{len(other_genetic_evidence)} other genetic evidence(s)")
    if not parts:
        parts.append("no genetic evidence found")

    score_str = f" Overall association: {overall_score:.3f}." if overall_score is not None else ""
    max_str = f" Max L2G score: {max_score:.3f}." if max_score is not None else ""
    variant_str = f" {n_variants} unique variant(s) across {n_studies} study(ies)." if n_variants > 0 else ""

    return {
        "summary": (
            f"Genetic evidence for {approved_symbol} -> {resolved_disease}: "
            f"{', '.join(parts)}.{score_str}{max_str}{variant_str}"
        ),
        "gene": approved_symbol,
        "gene_name": approved_name,
        "ensembl_id": ensembl_id,
        "disease": resolved_disease,
        "disease_id": efo_id,
        "overall_association_score": overall_score,
        "datasource_scores": datasource_scores,
        "total_evidence_count": evidence_count,
        "gwas_credible_sets": gwas_evidence,
        "other_genetic_evidence": other_genetic_evidence,
        "max_l2g_score": max_score,
        "n_unique_variants": n_variants,
        "n_studies": n_studies,
    }
