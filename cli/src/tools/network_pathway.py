"""Network biology tool: pathway membership and crosstalk via Reactome."""

from tools import registry
from tools.http_client import request_json
from tools.network_common import _coerce_gene_list
from tools.network_pathway_stats import (
    _crosstalk_nodes,
    _fetch_pathway_participants,
    _pathway_overlaps,
)


@registry.register(
    name="network.pathway_crosstalk",
    description="Analyze pathway membership and crosstalk for a gene set using Reactome",
    category="network",
    parameters={
        "genes": "Comma-separated gene symbols (e.g. 'CRBN,DDB1,CUL4A,RBX1')",
    },
    usage_guide="You want to understand which biological pathways a set of genes participate in and how those pathways overlap. Use for mechanism-of-action analysis and understanding pathway-level effects of perturbations.",
)
def pathway_crosstalk(genes: str, **kwargs) -> dict:
    """Analyze pathway membership and crosstalk via Reactome Content Service.

    Submits gene list for pathway over-representation analysis, then analyzes
    which genes appear in multiple pathways to identify crosstalk nodes.
    """
    gene_list = _coerce_gene_list(genes)
    if not gene_list:
        return {"error": "No gene symbols provided", "summary": "No gene symbols provided"}
    reactome_url = "https://reactome.org/AnalysisService/identifiers/projection"
    body = "\n".join(gene_list)

    data, error = request_json(
        "POST",
        reactome_url,
        data=body,
        headers={"Content-Type": "text/plain"},
        params={"pageSize": 20, "page": 1},
        timeout=15,
        retries=2,
    )
    if error:
        return {"error": f"Reactome analysis failed: {error}", "summary": f"Reactome analysis failed: {error}"}

    pathways_raw = data.get("pathways", [])
    pathways = []
    gene_pathway_map: dict = {}  # gene -> list of pathways

    for pw in pathways_raw:
        entities = pw.get("entities", {})
        ratio = entities.get("ratio", 0)
        pathways.append({
            "pathway_id": pw.get("stId", ""),
            "name": pw.get("name", ""),
            "p_value": entities.get("pValue", 1.0),
            "fdr": entities.get("fdr", 1.0),
            "genes_found": entities.get("found", 0),
            "genes_total": entities.get("total", 0),
            "ratio": round(ratio, 4) if ratio else 0,
        })

    not_found = data.get("identifiersNotFound", 0)

    # For each significant pathway, fetch the participant genes for crosstalk analysis
    significant_pathways = [p for p in pathways if p["fdr"] < 0.05][:10]
    _fetch_pathway_participants(significant_pathways, gene_list, gene_pathway_map)

    crosstalk_nodes = _crosstalk_nodes(gene_pathway_map)
    pathway_overlaps = _pathway_overlaps(significant_pathways)

    sig_count = len(significant_pathways)
    top_pathway = pathways[0]["name"] if pathways else "N/A"
    top_fdr = pathways[0]["fdr"] if pathways else "N/A"

    summary = (
        f"Reactome pathway analysis for {len(gene_list)} genes: "
        f"{len(pathways)} pathways enriched, {sig_count} significant (FDR < 0.05)\n"
        f"Top pathway: {top_pathway} (FDR={top_fdr})\n"
        f"Crosstalk nodes (multi-pathway genes): {len(crosstalk_nodes)}\n"
        f"Pathway pairs with shared genes: {len(pathway_overlaps)}"
    )

    return {
        "summary": summary,
        "query_genes": gene_list,
        "genes_not_found": not_found,
        "pathways": pathways,
        "crosstalk_nodes": crosstalk_nodes,
        "pathway_overlaps": pathway_overlaps,
    }
