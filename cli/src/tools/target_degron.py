"""
target.degron_predict: structural degron feature prediction via UniProt.

Split from tools/target.py.
"""

from tools import registry
from tools.http_client import request


@registry.register(
    name="target.degron_predict",
    description="Predict structural degron motifs in a protein (zinc fingers, disordered regions, surface accessibility) using UniProt features",
    category="target",
    parameters={"uniprot_id": "UniProt ID of target protein (e.g. P04637 for TP53)"},
    requires_data=[],
    usage_guide="You want to assess whether a protein has structural features (zinc fingers, disordered loops) that make it amenable to E3-mediated degradation. Use after identifying a target of interest.",
)
def degron_predict(uniprot_id: str, **kwargs) -> dict:
    """Predict degron features for a target protein using UniProt feature analysis."""
    # Fetch protein features from UniProt API
    resp, error = request(
        "GET",
        f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json",
        timeout=30,
        headers={"Accept": "application/json"},
        raise_for_status=False,
    )
    if error:
        return {"error": f"Failed to fetch UniProt data: {error}", "summary": f"Failed to fetch UniProt data: {error}"}
    if resp.status_code != 200:
        return {"error": f"UniProt entry not found for {uniprot_id} (HTTP {resp.status_code})", "summary": f"UniProt entry not found for {uniprot_id} (HTTP {resp.status_code})"}
    try:
        data = resp.json()
    except Exception:
        return {"error": f"Invalid UniProt JSON response for {uniprot_id}", "summary": f"Invalid UniProt JSON response for {uniprot_id}"}
    protein_name = data.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", uniprot_id)
    gene_name = ""
    genes = data.get("genes", [])
    if genes:
        gene_name = genes[0].get("geneName", {}).get("value", "")
    sequence = data.get("sequence", {})
    seq_length = sequence.get("length", 0)

    # Extract structural features relevant to degradation
    features = data.get("features", [])
    zinc_fingers = [f for f in features if f.get("type") == "Zinc finger"]
    domains = [f for f in features if f.get("type") == "Domain"]
    disordered = [f for f in features if f.get("type") == "Region" and "Disordered" in f.get("description", "")]
    motifs = [f for f in features if f.get("type") == "Motif"]
    modifications = [f for f in features if f.get("type") in ("Modified residue", "Cross-link")]

    # Compute degron-relevant scores
    def _region_length(feat):
        loc = feat.get("location", {})
        start = loc.get("start", {}).get("value", 0)
        end = loc.get("end", {}).get("value", 0)
        return max(0, end - start + 1) if start and end else 0

    disordered_residues = sum(_region_length(f) for f in disordered)
    disorder_fraction = disordered_residues / seq_length if seq_length > 0 else 0

    # Known degron-associated domain types
    degron_domains = []
    for d in domains:
        desc = d.get("description", "").lower()
        if any(k in desc for k in ["zinc finger", "ring", "btb", "wd40", "kelch", "socs box", "f-box"]):
            degron_domains.append(d.get("description", "unknown"))

    # Lysine count from sequence (ubiquitination sites)
    raw_seq = sequence.get("value", "")
    lysine_count = raw_seq.count("K") if raw_seq else 0
    lysine_density = lysine_count / seq_length if seq_length > 0 else 0

    # Known ubiquitination sites from modifications
    ub_sites = [m for m in modifications if "ubiquit" in m.get("description", "").lower()]

    # Compute overall degradability score (0-1 heuristic)
    score = 0.0
    score_breakdown = {}

    # Zinc fingers are strong degron features (CRBN/IKZF-type)
    zf_score = min(len(zinc_fingers) * 0.15, 0.3)
    score += zf_score
    score_breakdown["zinc_fingers"] = zf_score

    # Disordered regions expose protein to E3 engagement
    disorder_score = min(disorder_fraction * 0.5, 0.25)
    score += disorder_score
    score_breakdown["disorder"] = disorder_score

    # Lysine density enables ubiquitination
    lys_score = min(lysine_density * 3.0, 0.2)
    score += lys_score
    score_breakdown["lysine_accessibility"] = lys_score

    # Known ubiquitination sites
    ub_score = min(len(ub_sites) * 0.05, 0.15)
    score += ub_score
    score_breakdown["known_ub_sites"] = ub_score

    # Small-medium proteins degrade more easily
    size_score = 0.1 if seq_length < 800 else 0.05 if seq_length < 1500 else 0.0
    score += size_score
    score_breakdown["protein_size"] = size_score

    score = min(score, 1.0)

    # Classify
    if score >= 0.5:
        classification = "high"
        rationale = "Strong structural features for E3-mediated degradation"
    elif score >= 0.25:
        classification = "moderate"
        rationale = "Some favorable features; may require linker/scaffold optimization"
    else:
        classification = "low"
        rationale = "Few structural degron features identified"

    return {
        "summary": (
            f"Degron prediction for {gene_name or uniprot_id} ({protein_name}): "
            f"{classification} degradability (score={score:.2f}). "
            f"{len(zinc_fingers)} zinc finger(s), {disordered_residues} disordered residues "
            f"({disorder_fraction:.0%}), {lysine_count} lysines, {len(ub_sites)} known Ub site(s)."
        ),
        "uniprot_id": uniprot_id,
        "gene": gene_name,
        "protein_name": protein_name,
        "seq_length": seq_length,
        "degradability_score": round(score, 3),
        "classification": classification,
        "rationale": rationale,
        "score_breakdown": {k: round(v, 3) for k, v in score_breakdown.items()},
        "features": {
            "zinc_fingers": len(zinc_fingers),
            "zinc_finger_details": [
                {"description": f.get("description", ""), "start": f.get("location", {}).get("start", {}).get("value"), "end": f.get("location", {}).get("end", {}).get("value")}
                for f in zinc_fingers
            ],
            "disordered_residues": disordered_residues,
            "disorder_fraction": round(disorder_fraction, 3),
            "domains": [d.get("description", "") for d in domains],
            "degron_associated_domains": degron_domains,
            "lysine_count": lysine_count,
            "lysine_density": round(lysine_density, 3),
            "known_ub_sites": len(ub_sites),
            "motifs": [m.get("description", "") for m in motifs],
        },
    }
