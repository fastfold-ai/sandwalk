"""genomics.coloc: assemble the final colocalization result from a target payload. Split from tools/genomics.py."""
from tools.genomics_coloc_parse import is_gwas, parse_row


def build_result(target_data: dict, gene: str, study_id: str | None, ensembl_id: str) -> dict:
    approved_symbol = target_data.get("approvedSymbol", gene)
    # Backward-compatibility: some mocked test fixtures still use legacy field names.
    credible_sets = target_data.get("credibleSets") or target_data.get("gwasCredibleSets") or {}
    rows = credible_sets.get("rows", []) if isinstance(credible_sets, dict) else []

    if target_data.get("gwasCredibleSets") is not None:
        gwas_rows = rows
        total_loci = credible_sets.get("count", len(rows))
    else:
        gwas_rows = [row for row in rows if is_gwas(row)]
        total_loci = len(gwas_rows)

    coloc_results = []
    tissues_seen: set = set()
    studies_seen: set = set()
    for row in gwas_rows:
        coloc_results.extend(parse_row(row, ensembl_id, study_id, tissues_seen, studies_seen))

    # Sort by H4 (strongest colocalization first)
    coloc_results.sort(key=lambda x: x["h4"] if x["h4"] is not None else 0, reverse=True)

    n_strong = sum(1 for c in coloc_results if c["h4"] is not None and c["h4"] > 0.8)
    n_moderate = sum(1 for c in coloc_results if c["h4"] is not None and 0.5 < c["h4"] <= 0.8)

    study_filter_str = f" (study {study_id})" if study_id else ""
    if coloc_results:
        top_coloc = coloc_results[0]
        top_str = (
            f"Strongest: {top_coloc['trait']} / {top_coloc['tissue']} (H4={top_coloc['h4']:.3f})"
            if top_coloc["h4"] is not None
            else f"Strongest: {top_coloc['trait']} / {top_coloc['tissue']}"
        )
        summary = (
            f"Colocalization for {approved_symbol}{study_filter_str}: "
            f"{len(coloc_results)} GWAS-QTL pairs across {len(tissues_seen)} tissues, "
            f"{len(studies_seen)} GWAS studies. "
            f"{n_strong} strong (H4>0.8), {n_moderate} moderate (0.5<H4<=0.8). "
            f"{top_str}"
        )
    else:
        summary = (
            f"Colocalization for {approved_symbol}{study_filter_str}: "
            f"no QTL colocalization data found ({total_loci} GWAS loci scanned)"
        )

    return {
        "summary": summary,
        "gene": approved_symbol,
        "ensembl_id": ensembl_id,
        "total_gwas_loci": total_loci,
        "n_colocalizations": len(coloc_results),
        "n_strong_coloc": n_strong,
        "n_moderate_coloc": n_moderate,
        "n_tissues": len(tissues_seen),
        "n_studies": len(studies_seen),
        "tissues": sorted(tissues_seen),
        "colocalizations": coloc_results[:50],  # Cap at 50
    }
