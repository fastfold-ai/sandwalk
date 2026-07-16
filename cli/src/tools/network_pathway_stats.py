"""Reactome pathway-participant and crosstalk helpers for network.pathway_crosstalk."""

from tools.http_client import request


def _fetch_pathway_participants(significant_pathways: list[dict], gene_list: list[str], gene_pathway_map: dict) -> None:
    """Mutate each pathway dict with its matched input genes; track gene->pathways map."""
    for pw in significant_pathways:
        part_resp, part_error = request(
            "GET",
            f"https://reactome.org/ContentService/data/participants/{pw['pathway_id']}",
            headers={"Accept": "application/json"},
            timeout=10,
            raise_for_status=False,
        )
        if part_error or part_resp.status_code != 200:
            pw["matched_input_genes"] = []
            continue
        try:
            participants = part_resp.json()
        except Exception:
            pw["matched_input_genes"] = []
            continue

        pw_genes = set()
        for participant in participants:
            ref_entities = participant.get("refEntities", [])
            for ref in ref_entities:
                gene_name = ref.get("displayName", "")
                # Reactome format: "UniProt:XXXXX GENE_NAME"
                if " " in gene_name:
                    gene_name = gene_name.split(" ")[-1]
                if gene_name in gene_list:
                    pw_genes.add(gene_name)
                    gene_pathway_map.setdefault(gene_name, []).append(pw["name"])

        pw["matched_input_genes"] = sorted(pw_genes)


def _crosstalk_nodes(gene_pathway_map: dict) -> list[dict]:
    """Genes that appear in more than one enriched pathway."""
    nodes = [
        {"gene": g, "pathway_count": len(pws), "pathways": pws}
        for g, pws in gene_pathway_map.items()
        if len(pws) > 1
    ]
    nodes.sort(key=lambda x: x["pathway_count"], reverse=True)
    return nodes


def _pathway_overlaps(significant_pathways: list[dict]) -> list[dict]:
    """Pairs of pathways sharing input genes, sorted by shared-gene count."""
    pathway_gene_sets = {
        pw["name"]: set(pw["matched_input_genes"])
        for pw in significant_pathways
        if pw.get("matched_input_genes")
    }

    overlaps = []
    pw_names = list(pathway_gene_sets.keys())
    for i in range(len(pw_names)):
        for j in range(i + 1, len(pw_names)):
            shared = pathway_gene_sets[pw_names[i]] & pathway_gene_sets[pw_names[j]]
            if shared:
                overlaps.append({
                    "pathway_a": pw_names[i],
                    "pathway_b": pw_names[j],
                    "shared_genes": sorted(shared),
                    "shared_count": len(shared),
                })
    overlaps.sort(key=lambda x: x["shared_count"], reverse=True)
    return overlaps
