"""
target.druggability: druggability assessment via UniProt annotations.

Split from tools/target.py.
"""

from tools import registry
from tools.http_client import request


@registry.register(
    name="target.druggability",
    description="Assess the druggability of a protein target using UniProt annotations (protein family, domains, ligands, structural coverage)",
    category="target",
    parameters={"gene": "Gene symbol (e.g. BRAF, EGFR)"},
    requires_data=[],
    usage_guide="You want to evaluate whether a target protein is druggable — checks protein class, known ligands, structural data, and surface accessibility. Use early in target prioritization.",
)
def druggability(gene: str, **kwargs) -> dict:
    """Assess druggability of a protein target via UniProt annotations."""
    # Query UniProt for the gene
    resp, error = request(
        "GET",
        "https://rest.uniprot.org/uniprotkb/search",
        params={
            "query": f"gene_exact:{gene} AND organism_id:9606",
            "format": "json",
            "size": "1",
        },
        timeout=10,
        headers={"Accept": "application/json"},
        raise_for_status=False,
    )
    if error:
        return {"error": f"Failed to fetch UniProt data: {error}", "summary": f"UniProt API error for {gene}"}
    if resp.status_code != 200:
        return {"error": f"UniProt search failed for {gene} (HTTP {resp.status_code})", "summary": f"Failed to query UniProt for {gene}"}
    try:
        data = resp.json()
    except Exception:
        return {"error": f"Invalid UniProt response for {gene}", "summary": f"Failed to parse UniProt data for {gene}"}

    results = data.get("results", [])
    if not results:
        return {"error": f"No UniProt entry found for {gene} in human", "summary": f"Gene {gene} not found in UniProt (human)"}

    entry = results[0]

    # Extract protein info
    protein_name = (
        entry.get("proteinDescription", {})
        .get("recommendedName", {})
        .get("fullName", {})
        .get("value", gene)
    )
    uniprot_id = entry.get("primaryAccession", "")

    # Extract features
    features = entry.get("features", [])
    domains = [f.get("description", "") for f in features if f.get("type") == "Domain"]
    keywords = [kw.get("name", "") for kw in entry.get("keywords", [])]

    # Subcellular location
    comments = entry.get("comments", [])
    subcellular_locs = []
    for c in comments:
        if c.get("commentType") == "SUBCELLULAR LOCATION":
            for sl in c.get("subcellularLocations", []):
                loc_val = sl.get("location", {}).get("value", "")
                if loc_val:
                    subcellular_locs.append(loc_val)

    # Transmembrane regions
    transmembrane = [f for f in features if f.get("type") == "Transmembrane"]

    # Cross-references
    xrefs = entry.get("uniProtKBCrossReferences", [])

    # Check for ChEMBL cross-refs (known small molecule ligands)
    chembl_refs = [x for x in xrefs if x.get("database") == "ChEMBL"]
    known_drugs = [x.get("id", "") for x in chembl_refs]

    # Check for PDB cross-refs (structural coverage)
    pdb_refs = [x for x in xrefs if x.get("database") == "PDB"]
    pdb_ids = [x.get("id", "") for x in pdb_refs]

    # Determine protein class from keywords and domains
    protein_class = "other"
    class_score = 0.0
    keywords_lower = [k.lower() for k in keywords]
    domains_lower = [d.lower() for d in domains]
    all_annotations = " ".join(keywords_lower + domains_lower)

    if any(k in all_annotations for k in ["kinase", "protein kinase"]):
        protein_class = "kinase"
        class_score = 0.35
    elif any(k in all_annotations for k in ["g-protein coupled receptor", "gpcr"]):
        protein_class = "GPCR"
        class_score = 0.35
    elif any(k in all_annotations for k in ["ion channel", "voltage-gated"]):
        protein_class = "ion_channel"
        class_score = 0.30
    elif any(k in all_annotations for k in ["nuclear hormone receptor", "nuclear receptor"]):
        protein_class = "nuclear_receptor"
        class_score = 0.30
    elif any(k in all_annotations for k in ["protease", "peptidase"]):
        protein_class = "protease"
        class_score = 0.25
    elif any(k in all_annotations for k in ["phosphatase"]):
        protein_class = "phosphatase"
        class_score = 0.25
    elif any(k in all_annotations for k in ["transferase"]):
        protein_class = "transferase"
        class_score = 0.20
    elif any(k in all_annotations for k in ["transcription factor", "transcription"]):
        protein_class = "transcription_factor"
        class_score = 0.10
    elif any(k in all_annotations for k in ["scaffold", "adaptor"]):
        protein_class = "scaffold_adaptor"
        class_score = 0.05

    # Score: known ligands
    ligand_score = min(len(chembl_refs) * 0.10, 0.25)

    # Score: surface accessibility (extracellular / secreted / membrane)
    surface_keywords = ["secreted", "cell membrane", "extracellular"]
    is_surface = any(
        any(sk in loc.lower() for sk in surface_keywords)
        for loc in subcellular_locs
    )
    surface_score = 0.15 if is_surface else 0.0

    # Score: structural coverage (PDB entries)
    structure_score = min(len(pdb_refs) * 0.02, 0.15)

    # Score: has transmembrane (often druggable for membrane targets)
    tm_score = 0.10 if transmembrane else 0.0

    total_score = min(class_score + ligand_score + surface_score + structure_score + tm_score, 1.0)

    # Reasoning
    reasoning_parts = []
    if class_score > 0:
        reasoning_parts.append(f"Protein class '{protein_class}' is a {'highly ' if class_score >= 0.30 else ''}tractable target class")
    else:
        reasoning_parts.append(f"Protein class '{protein_class}' has limited druggability precedent")
    if chembl_refs:
        reasoning_parts.append(f"{len(chembl_refs)} ChEMBL entry/entries indicate known small-molecule interactions")
    else:
        reasoning_parts.append("No ChEMBL cross-references found (no known small-molecule ligands)")
    if pdb_refs:
        reasoning_parts.append(f"{len(pdb_refs)} PDB structure(s) available for structure-based drug design")
    else:
        reasoning_parts.append("No PDB structures available")
    if is_surface:
        reasoning_parts.append("Surface-accessible / extracellular localization supports biologic targeting")
    reasoning = ". ".join(reasoning_parts) + "."

    # Classify
    if total_score >= 0.6:
        classification = "highly druggable"
    elif total_score >= 0.35:
        classification = "druggable"
    elif total_score >= 0.15:
        classification = "challenging"
    else:
        classification = "undruggable (with current modalities)"

    return {
        "summary": (
            f"Druggability assessment for {gene} ({protein_name}): "
            f"{classification} (score={total_score:.2f}). "
            f"Class: {protein_class}. {len(pdb_ids)} PDB structures, "
            f"{len(known_drugs)} ChEMBL entries."
        ),
        "gene": gene,
        "uniprot_id": uniprot_id,
        "protein_name": protein_name,
        "druggability_score": round(total_score, 3),
        "classification": classification,
        "protein_class": protein_class,
        "known_drugs": known_drugs,
        "structural_coverage": {
            "pdb_count": len(pdb_ids),
            "pdb_ids": pdb_ids[:20],  # Cap at 20 for readability
        },
        "surface_accessible": is_surface,
        "subcellular_locations": subcellular_locs,
        "transmembrane_regions": len(transmembrane),
        "domains": domains,
        "reasoning": reasoning,
        "score_breakdown": {
            "protein_class": round(class_score, 3),
            "known_ligands": round(ligand_score, 3),
            "surface_accessibility": round(surface_score, 3),
            "structural_data": round(structure_score, 3),
            "transmembrane": round(tm_score, 3),
        },
    }
