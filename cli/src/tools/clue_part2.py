"""clue — part 2 of split module. See tools/clue.py."""
from tools.clue_base import np, pd, registry
from tools.clue_part1 import _load_profiles

@registry.register(
    name="clue.connectivity_query",
    description="Find compounds with similar or opposing transcriptomic signatures to a gene set",
    category="clue",
    parameters={
        "gene_list": "Dict with 'up' and 'down' keys, each a list of gene symbols",
        "n_results": "Number of top results to return (default 20)",
    },
    usage_guide=(
        "You have a gene signature (up/down-regulated genes) and want to find compounds "
        "with similar or opposing transcriptomic effects. Core CMap analysis. "
        "Use to find drug repurposing candidates or understand mechanism of action."
    ),
)
def connectivity_query(gene_list: dict = None, n_results: int = 20, **kwargs) -> dict:
    """Query local L1000 profiles with a gene signature using weighted connectivity scoring."""
    if not gene_list or not isinstance(gene_list, dict):
        return {
            "error": "gene_list must be a dict with 'up' and 'down' keys",
            "summary": "Invalid input: provide gene_list={'up': [...], 'down': [...]}",
        }

    up_genes = gene_list.get("up", [])
    down_genes = gene_list.get("down", [])

    if not up_genes and not down_genes:
        return {
            "error": "gene_list must have at least one gene in 'up' or 'down'",
            "summary": "Provide at least one up- or down-regulated gene.",
        }

    try:
        profiles = _load_profiles()
    except FileNotFoundError as e:
        return {"error": str(e), "summary": str(e)}

    # Find which query genes are in the profile columns
    available_up = [g for g in up_genes if g in profiles.columns]
    available_down = [g for g in down_genes if g in profiles.columns]

    if not available_up and not available_down:
        return {
            "error": "None of the query genes found in L1000 landmark genes.",
            "summary": (
                f"0/{len(up_genes)} up genes and 0/{len(down_genes)} down genes "
                "matched L1000 landmark genes (978 genes)."
            ),
        }

    # Compute connectivity score for each compound:
    # score = mean(z-scores of up genes) - mean(z-scores of down genes)
    # Positive score = compound mimics the signature
    # Negative score = compound opposes the signature
    score = np.zeros(len(profiles))

    if available_up:
        up_matrix = profiles[available_up].values
        score += np.nanmean(up_matrix, axis=1)
    if available_down:
        down_matrix = profiles[available_down].values
        score -= np.nanmean(down_matrix, axis=1)

    # Rank compounds
    results_df = pd.DataFrame({
        "compound": profiles.index,
        "connectivity_score": score,
    }).sort_values("connectivity_score", ascending=False)

    # Top similar (positive scores) and top opposing (negative scores)
    top_similar = results_df.head(n_results).to_dict("records")
    top_opposing = results_df.tail(n_results).iloc[::-1].to_dict("records")

    for row in top_similar + top_opposing:
        row["connectivity_score"] = round(row["connectivity_score"], 4)

    top = top_similar[0] if top_similar else {}
    summary = (
        f"Connectivity query: {len(available_up)}/{len(up_genes)} up, "
        f"{len(available_down)}/{len(down_genes)} down genes matched. "
        f"Scored {len(profiles)} compounds. "
        f"Top mimicker: {top.get('compound', 'N/A')} (score={top.get('connectivity_score', 0)}). "
        f"Top opposer: {top_opposing[0]['compound']} (score={top_opposing[0]['connectivity_score']})"
    )

    return {
        "summary": summary,
        "n_up_matched": len(available_up),
        "n_down_matched": len(available_down),
        "n_compounds_scored": len(profiles),
        "top_similar": top_similar,
        "top_opposing": top_opposing,
    }
