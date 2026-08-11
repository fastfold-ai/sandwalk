"""genomics.variant_annotate: Ensembl VEP variant annotation. Split from tools/genomics.py."""
from tools import genomics as _genomics
from tools import registry


@registry.register(
    name="genomics.variant_annotate",
    description="Annotate a genetic variant using Ensembl VEP (Variant Effect Predictor)",
    category="genomics",
    parameters={
        "variant": "Variant identifier: rsID (e.g. 'rs1234') or HGVS notation (e.g. '17:g.41245466G>A')",
    },
    requires_data=[],
    usage_guide="You want to understand the functional consequence of a specific genetic variant. Use to get consequence type (missense, synonymous, etc.), impact prediction, amino acid changes, allele frequencies, and clinical significance.",
)
def variant_annotate(variant: str, **kwargs) -> dict:
    """Annotate a variant using the Ensembl VEP REST API."""
    try:
        import httpx  # noqa: F401
    except ImportError:
        return {"error": "httpx required (pip install httpx)", "summary": "httpx required (pip install httpx)"}
    ensembl_base = "https://rest.ensembl.org"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    # Determine if this is an rsID or HGVS notation
    variant_clean = variant.strip()
    if variant_clean.lower().startswith("rs"):
        url = f"{ensembl_base}/vep/human/id/{variant_clean}"
    else:
        url = f"{ensembl_base}/vep/human/hgvs/{variant_clean}"

    resp, error = _genomics.request(
        "GET",
        url,
        headers=headers,
        timeout=30,
        retries=2,
        raise_for_status=False,
    )
    if error:
        return {"error": f"Ensembl VEP query failed: {error}", "summary": f"Ensembl VEP query failed: {error}"}
    if resp.status_code == 400:
        return {"error": f"Invalid variant format: '{variant}'. Use rsID (e.g. rs1234) or HGVS (e.g. 17:g.41245466G>A)", "summary": f"Invalid variant format: '{variant}'. Use rsID (e.g. rs1234) or HGVS (e.g. 17:g.41245466G>A)"}
    if resp.status_code >= 400:
        return {"error": f"Ensembl VEP query failed: HTTP {resp.status_code}", "summary": f"Ensembl VEP query failed: HTTP {resp.status_code}"}
    try:
        data = resp.json()
    except Exception:
        return {"error": "Ensembl VEP query failed: invalid JSON response", "summary": "Ensembl VEP query failed: invalid JSON response"}
    if not data or not isinstance(data, list):
        return {"error": f"No VEP results for variant {variant}", "summary": f"No VEP results for variant {variant}"}
    vep_result = data[0]

    # Extract variant identifiers
    variant_id = vep_result.get("id", variant)
    input_str = vep_result.get("input", variant)
    most_severe = vep_result.get("most_severe_consequence", "")
    allele_string = vep_result.get("allele_string", "")
    _strand = vep_result.get("strand")
    assembly = vep_result.get("assembly_name", "")
    seq_region = vep_result.get("seq_region_name", "")
    start = vep_result.get("start")
    end = vep_result.get("end")

    # Extract colocated variants (for allele frequencies, clinical significance)
    colocated = vep_result.get("colocated_variants", [])
    allele_frequencies = {}
    clinical_significance = []
    existing_ids = []

    for cv in colocated:
        cv_id = cv.get("id", "")
        if cv_id:
            existing_ids.append(cv_id)

        # Allele frequencies from different populations
        freqs = cv.get("frequencies", {})
        for allele, pop_freqs in freqs.items():
            for pop, freq in pop_freqs.items():
                key = f"{allele}_{pop}"
                allele_frequencies[key] = freq

        # Minor allele frequency
        maf = cv.get("minor_allele_freq")
        minor_allele = cv.get("minor_allele", "")
        if maf is not None:
            allele_frequencies["minor_allele"] = minor_allele
            allele_frequencies["minor_allele_freq"] = maf

        # Clinical significance
        clin_sig = cv.get("clin_sig", [])
        if clin_sig:
            clinical_significance.extend(clin_sig)

    # Extract transcript consequences
    transcript_consequences = []
    for tc in vep_result.get("transcript_consequences", []):
        consequence_terms = tc.get("consequence_terms", [])
        transcript_consequences.append({
            "gene_id": tc.get("gene_id", ""),
            "gene_symbol": tc.get("gene_symbol", ""),
            "transcript_id": tc.get("transcript_id", ""),
            "biotype": tc.get("biotype", ""),
            "consequence_terms": consequence_terms,
            "impact": tc.get("impact", ""),
            "amino_acids": tc.get("amino_acids", ""),
            "codons": tc.get("codons", ""),
            "protein_position": tc.get("protein_position", ""),
            "sift_prediction": tc.get("sift_prediction", ""),
            "sift_score": tc.get("sift_score"),
            "polyphen_prediction": tc.get("polyphen_prediction", ""),
            "polyphen_score": tc.get("polyphen_score"),
            "canonical": tc.get("canonical", 0) == 1,
        })

    # Sort: canonical transcripts first, then by impact severity
    impact_order = {"HIGH": 0, "MODERATE": 1, "LOW": 2, "MODIFIER": 3}
    transcript_consequences.sort(
        key=lambda x: (
            0 if x["canonical"] else 1,
            impact_order.get(x["impact"], 4),
        )
    )

    # Find the most impactful consequence for the summary
    top_consequence = transcript_consequences[0] if transcript_consequences else {}
    gene_symbol = top_consequence.get("gene_symbol", "")
    impact = top_consequence.get("impact", "")
    aa_change = top_consequence.get("amino_acids", "")
    protein_pos = top_consequence.get("protein_position", "")

    aa_str = ""
    if aa_change and protein_pos:
        aa_str = f", p.{aa_change.replace('/', str(protein_pos))}"

    clin_str = ""
    if clinical_significance:
        unique_clin = list(set(clinical_significance))
        clin_str = f" Clinical: {', '.join(unique_clin)}."

    maf_str = ""
    maf_val = allele_frequencies.get("minor_allele_freq")
    if maf_val is not None:
        maf_str = f" MAF={maf_val:.4f} ({allele_frequencies.get('minor_allele', '')})."

    return {
        "summary": (
            f"VEP annotation for {variant_id}: {most_severe} ({impact}) "
            f"in {gene_symbol}{aa_str}.{clin_str}{maf_str}"
        ),
        "variant_id": variant_id,
        "input": input_str,
        "location": f"{seq_region}:{start}-{end}" if seq_region and start else "",
        "assembly": assembly,
        "allele_string": allele_string,
        "most_severe_consequence": most_severe,
        "existing_ids": existing_ids,
        "allele_frequencies": allele_frequencies,
        "clinical_significance": list(set(clinical_significance)),
        "transcript_consequences": transcript_consequences[:10],  # Top 10
        "n_transcript_consequences": len(transcript_consequences),
    }
