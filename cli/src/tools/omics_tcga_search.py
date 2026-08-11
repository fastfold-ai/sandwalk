"""omics.tcga_search: search TCGA/GDC for datasets. Split from tools/omics.py."""
from tools import registry

from tools import omics as _omics

_GDC_API = "https://api.gdc.cancer.gov"


@registry.register(
    name="omics.tcga_search",
    description="Search TCGA/GDC for cancer genomics projects and data files",
    category="omics",
    parameters={
        "query": "Search terms (cancer type, gene, etc.)",
        "data_type": "Filter: 'gene_expression', 'methylation', 'mutation', 'clinical' (default 'gene_expression')",
        "max_results": "Maximum results to return (default 10)",
    },
    usage_guide=(
        "Search the NCI Genomic Data Commons (GDC) for TCGA and other cancer "
        "genomics projects. Use before omics.tcga_fetch to find file UUIDs."
    ),
)
def tcga_search(
    query: str,
    data_type: str = "gene_expression",
    max_results: int = 10,
    **kwargs,
) -> dict:
    """Search TCGA/GDC for projects and data files."""
    if not query or not query.strip():
        return {"error": "Query is required", "summary": "No query provided"}

    valid_types = {"gene_expression", "methylation", "mutation", "clinical"}
    if data_type not in valid_types:
        return {
            "error": f"Invalid data_type '{data_type}'. Choose from: {', '.join(valid_types)}",
            "summary": f"Invalid data_type: {data_type}",
        }

    # Map requested analysis type to GDC project summary data categories.
    # Project summaries expose category-level counts, not file-level data_type counts.
    gdc_data_category_map = {
        "gene_expression": "Transcriptome Profiling",
        "methylation": "DNA Methylation",
        "mutation": "Simple Nucleotide Variation",
        "clinical": "Clinical",
    }

    # Search projects first
    projects_url = f"{_GDC_API}/projects"
    filters = {
        "op": "or",
        "content": [
            {"op": "in", "content": {"field": "project_id", "value": [query.upper()]}},
            {"op": "like", "content": {"field": "name", "value": f"*{query}*"}},
            {"op": "like", "content": {"field": "disease_type", "value": f"*{query}*"}},
            {"op": "like", "content": {"field": "primary_site", "value": f"*{query}*"}},
        ],
    }

    import json

    params = {
        "filters": json.dumps(filters),
        "fields": "project_id,name,disease_type,primary_site,summary.case_count,summary.file_count,summary.data_categories.data_category,summary.data_categories.file_count",
        "size": str(min(max_results, 50)),
        "format": "json",
    }

    data, error = _omics.request_json("GET", projects_url, params=params, timeout=15)
    if error:
        return {"error": f"GDC search failed: {error}", "summary": f"GDC error: {error}"}

    hits = data.get("data", {}).get("hits", [])
    projects = []
    for hit in hits:
        summary = hit.get("summary", {})
        # Count files in the category most relevant to requested data_type.
        data_cats = summary.get("data_categories", [])
        requested_category = gdc_data_category_map.get(data_type, "")
        category_file_count = 0
        available_categories = []
        for cat in data_cats:
            cat_name = cat.get("data_category", "")
            if cat_name:
                available_categories.append(cat_name)
            if cat_name.lower() == requested_category.lower():
                category_file_count = int(cat.get("file_count", 0) or 0)

        projects.append({
            "project_id": hit.get("project_id", ""),
            "name": hit.get("name", ""),
            "disease_type": hit.get("disease_type", ""),
            "primary_site": hit.get("primary_site", ""),
            "case_count": summary.get("case_count", 0),
            "file_count": summary.get("file_count", 0),
            "data_type": data_type,
            "matching_data_category": requested_category,
            "data_type_file_count": category_file_count,
            "available_data_categories": available_categories[:20],
            "count_method": "project_summary_data_category",
        })

    if not projects:
        return {
            "projects": [],
            "query": query,
            "count": 0,
            "summary": f"No TCGA/GDC projects found for '{query}'",
        }

    return {
        "projects": projects,
        "query": query,
        "data_type": data_type,
        "count": len(projects),
        "summary": (
            f"Found {len(projects)} GDC project(s) for '{query}'. "
            + "; ".join(f"{p['project_id']}: {p['name'][:40]} ({p['case_count']} cases)" for p in projects[:3])
        ),
    }
