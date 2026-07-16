"""Network biology tool: protein-protein interaction analysis via STRING."""

from tools import registry
from tools.http_client import request_json
from tools.network_common import _coerce_gene_list
from tools.network_ppi_stats import _compute_network_stats, _expand_depth2, _functional_enrichment


@registry.register(
    name="network.ppi_analysis",
    description="Analyze protein-protein interaction network for a gene using STRING database",
    category="network",
    parameters={
        "gene": "Gene symbol or comma-separated list (e.g. 'CRBN' or 'CRBN,DDB1,CUL4A')",
        "min_score": "Minimum interaction confidence score 0-1 (default 0.4 = medium)",
        "network_depth": "1=direct partners only, 2=partners of partners (default 1)",
    },
    usage_guide="You want to understand what proteins interact with a target — maps the interaction neighborhood using STRING. Use for target validation, mechanism exploration, and finding co-complex members.",
)
def ppi_analysis(gene: str, min_score: float = 0.4, network_depth: int = 1, **kwargs) -> dict:
    """Analyze protein-protein interaction network via STRING API.

    Retrieves direct interaction partners and optionally second-shell neighbors.
    Computes network statistics and runs functional enrichment on the interactor set.
    """
    genes = _coerce_gene_list(gene)
    if not genes:
        return {"error": "No gene symbols provided", "summary": "No gene symbols provided"}
    string_score = int(min_score * 1000)  # STRING uses 0-1000 scale
    base = "https://string-db.org/api/json"

    interactions, error = request_json(
        "GET",
        f"{base}/network",
        params={
            "identifiers": "\r".join(genes),
            "species": 9606,
            "required_score": string_score,
            "caller_identity": "ct-celltype",
        },
        timeout=15,
        retries=2,
    )
    if error:
        return {"error": f"STRING network query failed: {error}", "summary": f"STRING network query failed: {error}"}
    if not interactions:
        return {
            "summary": f"No interactions found for {', '.join(genes)} at score >= {min_score}",
            "query_genes": genes,
            "interactions": [],
            "network_stats": {"node_count": len(genes), "edge_count": 0},
        }

    edges = []
    all_nodes = set(genes)
    for ix in interactions:
        a = ix.get("preferredName_A", ix.get("stringId_A", ""))
        b = ix.get("preferredName_B", ix.get("stringId_B", ""))
        edges.append({
            "gene_a": a,
            "gene_b": b,
            "score": round(ix.get("score", 0), 3),
            "nscore": round(ix.get("nscore", 0), 3),
            "fscore": round(ix.get("fscore", 0), 3),
            "pscore": round(ix.get("pscore", 0), 3),
            "ascore": round(ix.get("ascore", 0), 3),
            "escore": round(ix.get("escore", 0), 3),
            "dscore": round(ix.get("dscore", 0), 3),
            "tscore": round(ix.get("tscore", 0), 3),
        })
        all_nodes.add(a)
        all_nodes.add(b)
    edges.sort(key=lambda x: x["score"], reverse=True)

    depth2_edges = _expand_depth2(base, string_score, all_nodes, genes, edges) if network_depth >= 2 else []
    network_stats, avg_clustering = _compute_network_stats(all_nodes, edges, depth2_edges)
    enrichment = _functional_enrichment(base, list(all_nodes))

    query_set = set(genes)
    seen_partners = set()
    top_partners = []
    for e in edges:
        partner = e["gene_b"] if e["gene_a"] in query_set else e["gene_a"]
        if partner not in seen_partners and partner not in query_set:
            seen_partners.add(partner)
            top_partners.append(partner)
        if len(top_partners) >= 5:
            break
    top_str = ", ".join(top_partners) if top_partners else "none"
    top_pathway = enrichment[0]["description"] if enrichment else "N/A"

    summary = (
        f"PPI network for {', '.join(genes)}: "
        f"{network_stats['node_count']} nodes, {network_stats['edge_count']} edges (score >= {min_score})\n"
        f"Top interactors: {top_str}\n"
        f"Avg clustering coefficient: {avg_clustering:.3f}\n"
        f"Top enriched pathway: {top_pathway}"
    )

    result = {
        "summary": summary,
        "query_genes": genes,
        "interactions": edges[:50],  # Cap to keep response manageable
        "network_stats": network_stats,
        "enrichment": enrichment,
    }
    if depth2_edges:
        result["depth2_interactions"] = depth2_edges[:30]

    return result
