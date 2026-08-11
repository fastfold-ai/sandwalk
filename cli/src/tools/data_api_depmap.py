"""data_api.depmap_search: DepMap gene dependency lookup. Split from tools/data_api.py."""
from tools import registry

from tools import data_api as _data_api
from tools.data_api_common import _logger


@registry.register(
    name="data_api.depmap_search",
    description="Search DepMap for gene dependency scores across cancer cell lines",
    category="data_api",
    parameters={
        "gene": "Gene symbol (e.g. BRCA1, TP53)",
        "dataset": "Dataset to query: 'crispr', 'expression', 'mutations', or 'cn' (default 'crispr')",
    },
    requires_data=[],
    usage_guide="You want DepMap gene dependency data across cell lines. Returns dependency scores, most/least dependent lineages. Uses local DepMap data when available, or the Cell Model Passports API as fallback.",
)
def depmap_search(gene: str, dataset: str = "crispr", **kwargs) -> dict:
    """Search DepMap for gene dependency / expression / mutation data.

    Tries local DepMap data first (via ct data loaders), then falls back to
    the Cell Model Passports API (public, no key required).
    """

    valid_datasets = ("crispr", "expression", "mutations", "cn")
    if dataset not in valid_datasets:
        return {"error": f"Invalid dataset '{dataset}'. Choose from: {', '.join(valid_datasets)}", "summary": f"Invalid dataset '{dataset}'"}

    # Normalize gene name
    gene = _data_api._normalize_gene_name(gene)

    # --- Attempt local DepMap data ---
    if dataset == "crispr":
        try:
            from data.loaders import load_crispr
            crispr = load_crispr()
            # Try exact match first, then common variations
            if gene not in crispr.columns:
                # Try with/without hyphens, dots, etc.
                found = False
                for variant in [gene.replace("-", ""), gene.replace(".", ""), gene + "A"]:
                    if variant in crispr.columns:
                        _logger.warning("Gene '%s' not found, using variant '%s'", gene, variant)
                        gene = variant
                        found = True
                        break
                if not found:
                    # Try partial match (e.g., "CD274" matches "CD274 (PD-L1)")
                    matches = [c for c in crispr.columns if c.startswith(gene + " ") or c == gene]
                    if matches:
                        gene = matches[0]
                        _logger.warning("Gene exact match not found, using '%s'", gene)
                    else:
                        return {"error": f"Gene {gene} not found in local DepMap CRISPR data", "summary": f"Gene {gene} not in DepMap CRISPR"}

            scores = crispr[gene].dropna()
            n_lines = len(scores)
            essential = (scores < -0.5).sum()
            mean_score = float(scores.mean())
            min_score = float(scores.min())

            # Lineage info if model metadata available
            lineage_stats = []
            try:
                from data.loaders import load_model_metadata
                model = load_model_metadata()
                merged = scores.to_frame(name="score").join(
                    model.set_index("ModelID")["OncotreeLineage"], how="left"
                )
                if "OncotreeLineage" in merged.columns:
                    for lin, grp in merged.groupby("OncotreeLineage"):
                        lineage_stats.append({
                            "lineage": lin,
                            "mean_score": round(float(grp["score"].mean()), 4),
                            "n_lines": len(grp),
                            "n_essential": int((grp["score"] < -0.5).sum()),
                        })
                    lineage_stats.sort(key=lambda x: x["mean_score"])
            except Exception:
                pass

            most_dependent = [ls["lineage"] for ls in lineage_stats[:3]] if lineage_stats else []
            least_dependent = [ls["lineage"] for ls in lineage_stats[-3:]] if lineage_stats else []

            return {
                "summary": (
                    f"{gene} dependency (DepMap CRISPR): essential in {essential}/{n_lines} lines, "
                    f"mean score {mean_score:.3f}"
                    + (f", most dependent: {', '.join(most_dependent)}" if most_dependent else "")
                ),
                "gene": gene,
                "dataset": "crispr",
                "n_cell_lines": n_lines,
                "n_essential": int(essential),
                "mean_score": round(mean_score, 4),
                "min_score": round(min_score, 4),
                "lineage_stats": lineage_stats[:20],
                "most_dependent_lineages": most_dependent,
                "least_dependent_lineages": least_dependent,
            }
        except (ImportError, FileNotFoundError):
            pass  # Fall through to API

    if dataset == "mutations":
        try:
            from data.loaders import load_mutations
            mutations = load_mutations()
            if gene not in mutations.columns:
                return {"error": f"Gene {gene} not found in local DepMap mutation data"}

            mutated = mutations[gene].dropna()
            n_lines = len(mutated)
            n_mutated = int((mutated > 0).sum())
            mutation_rate = n_mutated / n_lines if n_lines > 0 else 0

            return {
                "summary": (
                    f"{gene} mutations (DepMap): mutated in {n_mutated}/{n_lines} lines "
                    f"({mutation_rate:.1%})"
                ),
                "gene": gene,
                "dataset": "mutations",
                "n_cell_lines": n_lines,
                "n_mutated": n_mutated,
                "mutation_rate": round(mutation_rate, 4),
            }
        except (ImportError, FileNotFoundError):
            pass  # Fall through to API

    # --- Fallback: Cell Model Passports API ---
    try:
        resp = _data_api._http_get(
            "https://www.cellmodelpassports.sanger.ac.uk/api/v1/genes",
            params={"search": gene, "page_size": 5},
            timeout=15,
        )
        if resp.status_code != 200:
            return {
                "error": f"Cell Model Passports API returned HTTP {resp.status_code}",
                "summary": f"Could not query DepMap/CMP for {gene}",
            }
        data = resp.json()
    except Exception as e:
        import httpx
        if isinstance(e, httpx.TimeoutException):
            return {"error": "Cell Model Passports API timed out", "summary": f"CMP timeout for {gene}"}
        if isinstance(e, httpx.HTTPError):
            return {"error": f"CMP API error: {e}", "summary": f"CMP query failed for {gene}"}
        return {"error": f"CMP API error: {e}", "summary": f"CMP query failed for {gene}"}

    results = data.get("data", data.get("results", []))
    if not results:
        return {
            "error": f"Gene {gene} not found in Cell Model Passports",
            "summary": f"No results for {gene} in CMP",
        }

    gene_info = results[0] if isinstance(results, list) else results
    return {
        "summary": f"DepMap/CMP: {gene} — found in Cell Model Passports database",
        "gene": gene,
        "dataset": dataset,
        "source": "cell_model_passports",
        "gene_info": gene_info,
    }


# ---------------------------------------------------------------------------
# 2. Open Targets search
# ---------------------------------------------------------------------------
