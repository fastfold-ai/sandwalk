"""omics.deseq2 helpers: level-name resolution and target-gene lookup. Split from tools/omics.py."""
from pathlib import Path

from tools import omics as _omics


def _resolve_level_name(requested: str, available_levels: list[str]) -> str:
    """Best-effort map of user/planner shorthand labels to metadata factor levels."""
    import re

    req = str(requested or "").strip()
    if not req:
        return req
    if req in available_levels:
        return req

    def _norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", s.lower())

    req_norm = _norm(req)
    if not req_norm:
        return req

    # 1) Exact normalized match.
    exact = [lvl for lvl in available_levels if _norm(str(lvl)) == req_norm]
    if len(exact) == 1:
        return exact[0]

    # 2) Prefix/token containment match (e.g., "CBD" -> "CBD_IC50").
    token_like = [
        lvl
        for lvl in available_levels
        if _norm(str(lvl)).startswith(req_norm) or req_norm in _norm(str(lvl))
    ]
    if len(token_like) == 1:
        return token_like[0]

    # 3) Prefer non-combined condition when shorthand maps to several levels.
    if len(token_like) > 1:
        non_combo = [
            lvl
            for lvl in token_like
            if "serum_starvation" not in str(lvl).lower()
            and "cisplatin" not in str(lvl).lower()
            and "comb" not in str(lvl).lower()
            and "plus" not in str(lvl).lower()
        ]
        if len(non_combo) == 1:
            return non_combo[0]
    return req


def _build_gene_symbol_mapper(gm_df, gene_id_col: str, gene_symbol_col: str) -> "dict[str, str]":
    id_col = gene_id_col or ("ENSG_ID" if "ENSG_ID" in gm_df.columns else gm_df.columns[0])
    sym_col = gene_symbol_col or (
        "gene_name"
        if "gene_name" in gm_df.columns
        else ("symbol" if "symbol" in gm_df.columns else gm_df.columns[-1])
    )
    gm2 = gm_df[[id_col, sym_col]].dropna().copy()
    gm2[id_col] = gm2[id_col].astype(str).str.split(".").str[0]
    gm2[sym_col] = gm2[sym_col].astype(str)
    return {symbol.lower(): gid for gid, symbol in zip(gm2[id_col], gm2[sym_col]) if symbol}


def _resolve_target_gene(
    results_df,
    target_gene: str,
    counts_path: str,
    gene_map_path: str,
    gene_id_col: str,
    gene_symbol_col: str,
) -> "dict | None":
    """Resolve a user-requested target gene against DE results."""
    import pandas as pd

    target_gene = str(target_gene or "").strip()
    if not target_gene:
        return None

    idx_series = pd.Series(results_df.index.astype(str), index=results_df.index)
    idx_no_ver = idx_series.str.split(".").str[0]
    tgt_no_ver = target_gene.split(".")[0]
    tgt_lower = target_gene.lower()
    tgt_no_ver_lower = tgt_no_ver.lower()

    mask = (idx_series.str.lower() == tgt_lower) | (idx_no_ver.str.lower() == tgt_no_ver_lower)

    # If the target appears to be a symbol and IDs are in results, use mapping if provided/discoverable.
    if not mask.any():
        mapper = None
        if gene_map_path:
            gm, gm_err = _omics._load_tabular(gene_map_path, index_col=None)
            if not gm_err and gm is not None and not gm.empty:
                mapper = _build_gene_symbol_mapper(gm, gene_id_col, gene_symbol_col)
        else:
            # Best-effort auto-discovery for common capsule naming patterns.
            try:
                base_dir = Path(counts_path).expanduser().resolve().parent
                candidates = sorted(
                    p
                    for p in base_dir.iterdir()
                    if p.is_file()
                    and p.suffix.lower() in {".csv", ".tsv", ".txt", ".xlsx", ".xls"}
                    and ("gene" in p.name.lower() and ("meta" in p.name.lower() or "annot" in p.name.lower()))
                )
                for cand in candidates:
                    gm, gm_err = _omics._load_tabular(str(cand), index_col=None)
                    if gm_err or gm is None or gm.empty:
                        continue
                    mapper = _build_gene_symbol_mapper(gm, gene_id_col, gene_symbol_col)
                    if mapper:
                        break
            except Exception:
                mapper = None

        if mapper:
            mapped_id = mapper.get(tgt_lower)
            if mapped_id:
                mask = idx_no_ver.str.lower() == mapped_id.lower()

    if not mask.any():
        return {"target_gene": target_gene, "found": False}

    row = results_df.loc[mask].iloc[0]
    return {
        "target_gene": target_gene,
        "found": True,
        "matched_gene_id": str(results_df.loc[mask].index[0]),
        "log2FoldChange": float(row.get("log2FoldChange")) if pd.notna(row.get("log2FoldChange")) else None,
        "baseMean": float(row.get("baseMean")) if pd.notna(row.get("baseMean")) else None,
        "padj": float(row.get("padj")) if pd.notna(row.get("padj")) else None,
        "pvalue": float(row.get("pvalue")) if "pvalue" in row and pd.notna(row.get("pvalue")) else None,
    }


def _target_gene_summary_text(target_gene_result: "dict | None", target_gene: str) -> str:
    if not target_gene_result:
        return ""
    if target_gene_result.get("found"):
        lfc_val = target_gene_result.get("log2FoldChange")
        lfc_txt = f"{lfc_val:.6g}" if lfc_val is not None else "NA"
        return f" {target_gene} log2FoldChange={lfc_txt}."
    return f" {target_gene} was not found in result gene IDs."
