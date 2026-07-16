"""genomics.coloc: per-GWAS-row QTL colocalization parsing (current + legacy schema). Split from tools/genomics.py."""
import math


def is_gwas(row: dict) -> bool:
    st = row.get("studyType") or (row.get("study") or {}).get("studyType") or ""
    return str(st).lower() == "gwas"


def parse_row(row: dict, ensembl_id: str, study_id: str | None, tissues_seen: set, studies_seen: set) -> list[dict]:
    """Parse colocalization results (current + legacy schema) for one GWAS credible-set row.

    Mutates tissues_seen/studies_seen in place. Returns a list of coloc result dicts
    (empty if filtered out by study_id or no QTL colocalizations present).
    """
    study = row.get("study") or {}
    gwas_study_id = row.get("studyId") or study.get("id", "")
    if study_id and gwas_study_id != study_id:
        return []

    variant = row.get("variant") or {}
    rs_ids = variant.get("rsIds", [])
    lead_rsid = rs_ids[0] if rs_ids else ""

    p_mantissa = row.get("pValueMantissa")
    p_exponent = row.get("pValueExponent")
    p_value = None
    if p_mantissa is not None and p_exponent is not None:
        try:
            p_value = float(p_mantissa) * (10 ** int(p_exponent))
        except (ValueError, TypeError):
            pass

    l2g_score = None
    l2g_preds_raw = row.get("l2GPredictions") or []
    l2g_preds = l2g_preds_raw.get("rows") or [] if isinstance(l2g_preds_raw, dict) else l2g_preds_raw
    for pred in l2g_preds:
        pred_target = pred.get("target") or {}
        if pred_target.get("id") == ensembl_id:
            l2g_score = pred.get("score")
            if l2g_score is None:
                l2g_score = pred.get("yProbaModel")
            break

    trait = study.get("traitFromSource", "")
    diseases = study.get("diseases") or []
    disease_names = [d.get("name", "") for d in diseases if d.get("name")]

    base = {
        "gwas_study_id": gwas_study_id,
        "trait": trait,
        "diseases": disease_names,
        "lead_variant": variant.get("id", ""),
        "lead_rsid": lead_rsid,
        "p_value": p_value,
        "l2g_score": round(l2g_score, 4) if l2g_score is not None else None,
    }

    results = []

    # Current schema: colocalisation.rows
    coloc_obj = row.get("colocalisation") or {}
    qtl_colocs = coloc_obj.get("rows", []) if isinstance(coloc_obj, dict) else []
    for qtl in qtl_colocs:
        h4, h3 = qtl.get("h4"), qtl.get("h3")
        right_study_type = str(qtl.get("rightStudyType") or "").lower()
        if right_study_type and "qtl" not in right_study_type:
            continue

        other = qtl.get("otherStudyLocus") or {}
        other_study = other.get("study") or {}
        biosample = other_study.get("biosample") or {}
        tissue_name = biosample.get("biosampleName") or other_study.get("condition") or other_study.get("traitFromSource") or ""
        tissue_id = biosample.get("biosampleId", "")
        qtl_study = other.get("studyId") or other_study.get("id", "")
        phenotype = other.get("qtlGeneId", "")

        log2_h4_h3 = None
        if h4 is not None and h3 not in (None, 0):
            try:
                if float(h4) > 0 and float(h3) > 0:
                    log2_h4_h3 = math.log2(float(h4) / float(h3))
            except (TypeError, ValueError, ZeroDivisionError):
                log2_h4_h3 = None

        if tissue_name:
            tissues_seen.add(tissue_name)
        studies_seen.add(gwas_study_id)

        results.append({
            **base,
            "qtl_study_id": qtl_study,
            "phenotype_id": phenotype,
            "tissue": tissue_name,
            "tissue_id": tissue_id,
            "h4": round(h4, 4) if h4 is not None else None,
            "h3": round(h3, 4) if h3 is not None else None,
            "log2_h4_h3": round(log2_h4_h3, 4) if log2_h4_h3 is not None else None,
            "colocalisation_method": qtl.get("colocalisationMethod"),
            "right_study_type": qtl.get("rightStudyType"),
            "clpp": round(qtl.get("clpp"), 4) if qtl.get("clpp") is not None else None,
        })

    # Backward compatibility with legacy schema field name used in old fixtures.
    for qtl in row.get("colocalisationsQtl") or []:
        h4 = qtl.get("h4")
        tissue_info = qtl.get("tissue") or {}
        tissue_name = tissue_info.get("name", "")
        if tissue_name:
            tissues_seen.add(tissue_name)
        studies_seen.add(gwas_study_id)

        results.append({
            **base,
            "qtl_study_id": qtl.get("qtlStudyId", ""),
            "phenotype_id": qtl.get("phenotypeId", ""),
            "tissue": tissue_name,
            "tissue_id": tissue_info.get("id", ""),
            "h4": round(h4, 4) if h4 is not None else None,
            "h3": round(qtl.get("h3", 0), 4) if qtl.get("h3") is not None else None,
            "log2_h4_h3": round(qtl.get("log2h4h3", 0), 4) if qtl.get("log2h4h3") is not None else None,
            "colocalisation_method": None,
            "right_study_type": None,
            "clpp": None,
        })

    return results
