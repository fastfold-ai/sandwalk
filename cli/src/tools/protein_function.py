"""
protein.function_predict: UniProt-derived function/localization/PTM/disease data.

Split from tools/protein.py.
"""

from tools import registry
from tools.http_client import request


@registry.register(
    name="protein.function_predict",
    description="Predict protein function, localization, domains, PTMs, and disease associations from UniProt",
    category="protein",
    parameters={
        "gene": "Gene symbol (e.g. BRCA1) or UniProt ID (e.g. P38398)",
        "sequence": "Amino acid sequence (optional, used for basic analysis if API fails)",
    },
    usage_guide="You need comprehensive protein function information — GO terms, subcellular location, domains, PTMs, disease associations, and tissue specificity. Use for target characterization and understanding protein biology.",
)
def function_predict(gene: str, sequence: str = None, **kwargs) -> dict:
    """Query UniProt for comprehensive protein function data.

    Searches by gene symbol (human) or UniProt accession. Extracts function
    description, subcellular location, GO terms, domains, post-translational
    modifications, disease associations, and tissue specificity.
    """
    # Determine if input is UniProt ID or gene symbol
    is_uniprot_id = (
        len(gene) == 6
        and gene[0].isalpha()
        and all(c.isalnum() for c in gene)
    )

    if is_uniprot_id:
        resp, error = request(
            "GET",
            f"https://rest.uniprot.org/uniprotkb/{gene}.json",
            timeout=15,
            headers={"Accept": "application/json"},
            raise_for_status=False,
        )
        if error:
            return {"error": f"UniProt API error: {error}", "summary": f"Failed to query UniProt for {gene}"}
        if resp.status_code != 200:
            return {
                "error": f"UniProt entry not found for {gene} (HTTP {resp.status_code})",
                "summary": f"No UniProt entry for {gene}",
            }
        try:
            entry = resp.json()
        except Exception:
            return {"error": f"Invalid UniProt response for {gene}", "summary": f"Failed to parse UniProt response for {gene}"}
    else:
        resp, error = request(
            "GET",
            "https://rest.uniprot.org/uniprotkb/search",
            params={
                "query": f"{gene} AND organism_id:9606",
                "format": "json",
                "size": "1",
            },
            timeout=15,
            headers={"Accept": "application/json"},
            raise_for_status=False,
        )
        if error:
            return {"error": f"UniProt API error: {error}", "summary": f"Failed to query UniProt for {gene}"}
        if resp.status_code != 200:
            return {
                "error": f"UniProt search failed (HTTP {resp.status_code})",
                "summary": f"UniProt query failed for {gene}",
            }
        try:
            data = resp.json()
        except Exception:
            return {"error": f"Invalid UniProt response for {gene}", "summary": f"Failed to parse UniProt response for {gene}"}
        results = data.get("results", [])
        if not results:
            return {
                "error": f"No UniProt entry found for gene {gene} in human",
                "summary": f"Gene {gene} not found in UniProt (human)",
            }
        entry = results[0]

    # Extract basic info
    uniprot_id = entry.get("primaryAccession", "")
    protein_desc = entry.get("proteinDescription", {})
    rec_name = protein_desc.get("recommendedName", {})
    protein_name = rec_name.get("fullName", {}).get("value", gene)

    gene_names = entry.get("genes", [])
    gene_symbol = gene_names[0].get("geneName", {}).get("value", gene) if gene_names else gene

    seq_info = entry.get("sequence", {})
    seq_length = seq_info.get("length", 0)

    # Extract comments (function, location, tissue specificity, etc.)
    comments = entry.get("comments", [])

    function_text = ""
    subcellular_locations = []
    tissue_specificity = ""
    disease_associations = []
    catalytic_activity = []

    for comment in comments:
        ct = comment.get("commentType", "")

        if ct == "FUNCTION":
            texts = comment.get("texts", [])
            if texts:
                function_text = texts[0].get("value", "")

        elif ct == "SUBCELLULAR LOCATION":
            for sl in comment.get("subcellularLocations", []):
                loc = sl.get("location", {}).get("value", "")
                if loc:
                    subcellular_locations.append(loc)

        elif ct == "TISSUE SPECIFICITY":
            texts = comment.get("texts", [])
            if texts:
                tissue_specificity = texts[0].get("value", "")

        elif ct == "DISEASE":
            disease = comment.get("disease", {})
            if disease:
                disease_associations.append({
                    "name": disease.get("diseaseId", ""),
                    "description": disease.get("description", ""),
                    "acronym": disease.get("acronym", ""),
                })

        elif ct == "CATALYTIC ACTIVITY":
            reaction = comment.get("reaction", {})
            if reaction:
                catalytic_activity.append(reaction.get("name", ""))

    # Extract features
    features = entry.get("features", [])
    domains = []
    ptms = []
    active_sites = []
    binding_sites = []

    for feat in features:
        ftype = feat.get("type", "")
        desc = feat.get("description", "")
        loc = feat.get("location", {})
        start = loc.get("start", {}).get("value")
        end = loc.get("end", {}).get("value")

        if ftype == "Domain":
            domains.append({"name": desc, "start": start, "end": end})
        elif ftype in ("Modified residue", "Glycosylation", "Disulfide bond", "Cross-link", "Lipidation"):
            ptms.append({"type": ftype, "description": desc, "position": start})
        elif ftype == "Active site":
            active_sites.append({"description": desc, "position": start})
        elif ftype == "Binding site":
            binding_sites.append({"description": desc, "start": start, "end": end})

    # Extract GO terms from cross-references
    xrefs = entry.get("uniProtKBCrossReferences", [])
    go_terms = {"biological_process": [], "molecular_function": [], "cellular_component": []}
    for xref in xrefs:
        if xref.get("database") == "GO":
            props = xref.get("properties", [])
            go_id = xref.get("id", "")
            term_name = ""
            term_type = ""
            for p in props:
                if p.get("key") == "GoTerm":
                    val = p.get("value", "")
                    if val.startswith("P:"):
                        term_type = "biological_process"
                        term_name = val[2:]
                    elif val.startswith("F:"):
                        term_type = "molecular_function"
                        term_name = val[2:]
                    elif val.startswith("C:"):
                        term_type = "cellular_component"
                        term_name = val[2:]
            if term_type and term_name:
                go_terms[term_type].append({"id": go_id, "name": term_name})

    # Extract keywords
    keywords = [kw.get("name", "") for kw in entry.get("keywords", [])]

    # Build summary
    location_str = ", ".join(subcellular_locations[:3]) if subcellular_locations else "Unknown"
    domain_str = f"{len(domains)} {'domain' if len(domains) == 1 else 'domains'}"
    if domains:
        domain_names = ", ".join(d["name"] for d in domains[:4])
        domain_str += f" ({domain_names})"

    disease_str = ""
    if disease_associations:
        disease_names = ", ".join(d["name"] for d in disease_associations[:3])
        disease_str = f" Associated with {disease_names}."

    func_short = function_text[:150] + "..." if len(function_text) > 150 else function_text

    summary = (
        f"{gene_symbol} ({uniprot_id}): {func_short} "
        f"{location_str}. {domain_str}.{disease_str}"
    )

    return {
        "summary": summary,
        "uniprot_id": uniprot_id,
        "gene": gene_symbol,
        "protein_name": protein_name,
        "sequence_length": seq_length,
        "function": function_text,
        "subcellular_locations": subcellular_locations,
        "tissue_specificity": tissue_specificity,
        "go_terms": go_terms,
        "domains": domains,
        "ptms": ptms[:30],
        "active_sites": active_sites,
        "binding_sites": binding_sites,
        "disease_associations": disease_associations,
        "catalytic_activity": catalytic_activity,
        "keywords": keywords,
    }
