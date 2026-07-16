"""STRING PPI network statistics: depth-2 expansion, clustering, enrichment."""

from tools.http_client import request_json


def _expand_depth2(base: str, string_score: int, all_nodes: set, genes: list[str], edges: list[dict]) -> list[dict]:
    """Fetch second-shell partners for the top 10 first-shell interactors."""
    first_shell = all_nodes - set(genes)
    if not first_shell:
        return []

    expand_genes = sorted(first_shell, key=lambda g: max(
        (e["score"] for e in edges if g in (e["gene_a"], e["gene_b"])),
        default=0,
    ), reverse=True)[:10]

    depth2_data, depth2_error = request_json(
        "GET",
        f"{base}/network",
        params={
            "identifiers": "\r".join(expand_genes),
            "species": 9606,
            "required_score": string_score,
            "caller_identity": "ct-celltype",
        },
        timeout=15,
        retries=2,
    )
    if depth2_error:
        return []

    depth2_edges = []
    existing_keys = {tuple(sorted([e["gene_a"], e["gene_b"]])) for e in edges}
    for ix in depth2_data:
        a = ix.get("preferredName_A", ix.get("stringId_A", ""))
        b = ix.get("preferredName_B", ix.get("stringId_B", ""))
        score = round(ix.get("score", 0), 3)
        edge_key = tuple(sorted([a, b]))
        if edge_key not in existing_keys:
            depth2_edges.append({"gene_a": a, "gene_b": b, "score": score})
            all_nodes.add(a)
            all_nodes.add(b)
    depth2_edges.sort(key=lambda x: x["score"], reverse=True)
    return depth2_edges


def _compute_network_stats(all_nodes: set, edges: list[dict], depth2_edges: list[dict]) -> dict:
    """Degree distribution, approximate clustering coefficient, and hub genes."""
    node_count = len(all_nodes)
    edge_count = len(edges) + len(depth2_edges)

    degree = {}
    for e in edges + depth2_edges:
        degree[e["gene_a"]] = degree.get(e["gene_a"], 0) + 1
        degree[e["gene_b"]] = degree.get(e["gene_b"], 0) + 1
    avg_degree = sum(degree.values()) / max(len(degree), 1)

    adjacency = {}
    for e in edges + depth2_edges:
        adjacency.setdefault(e["gene_a"], set()).add(e["gene_b"])
        adjacency.setdefault(e["gene_b"], set()).add(e["gene_a"])

    clustering_coefficients = []
    for _node, neighbors in adjacency.items():
        n = len(neighbors)
        if n < 2:
            clustering_coefficients.append(0.0)
            continue
        neighbor_list = list(neighbors)
        triangles = 0
        for i in range(len(neighbor_list)):
            for j in range(i + 1, len(neighbor_list)):
                if neighbor_list[j] in adjacency.get(neighbor_list[i], set()):
                    triangles += 1
        possible = n * (n - 1) / 2
        clustering_coefficients.append(triangles / possible if possible > 0 else 0)

    avg_clustering = sum(clustering_coefficients) / max(len(clustering_coefficients), 1)
    hub_genes = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "avg_degree": round(avg_degree, 2),
        "clustering_coefficient": round(avg_clustering, 3),
        "hub_genes": [{"gene": g, "degree": d} for g, d in hub_genes],
    }, avg_clustering


def _functional_enrichment(base: str, interactor_genes: list[str]) -> list[dict]:
    """Run STRING functional enrichment on the interactor set."""
    if len(interactor_genes) < 2:
        return []

    enrich_data, enrich_error = request_json(
        "GET",
        f"{base}/enrichment",
        params={
            "identifiers": "\r".join(interactor_genes),
            "species": 9606,
            "caller_identity": "ct-celltype",
        },
        timeout=15,
        retries=2,
    )
    if enrich_error:
        return []

    enrichment = [
        {
            "category": entry.get("category", ""),
            "term": entry.get("term", ""),
            "description": entry.get("description", ""),
            "p_value": entry.get("p_value", 1.0),
            "fdr": entry.get("fdr", 1.0),
            "gene_count": entry.get("number_of_genes", 0),
            "genes": entry.get("preferredNames", ""),
        }
        for entry in enrich_data
    ]
    enrichment.sort(key=lambda x: x["fdr"])
    return enrichment[:20]
