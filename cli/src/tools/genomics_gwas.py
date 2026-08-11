"""genomics.gwas_lookup: GWAS Catalog association search. Split from tools/genomics.py."""
from tools import genomics as _genomics
from tools import registry


@registry.register(
    name="genomics.gwas_lookup",
    description="Query the GWAS Catalog for genetic associations for a gene, optionally filtered by trait",
    category="genomics",
    parameters={
        "gene": "Gene symbol (e.g. 'BRCA1', 'TP53')",
        "trait": "Trait or disease name to filter (optional)",
        "p_threshold": "P-value threshold for significance (default 5e-8)",
    },
    requires_data=[],
    usage_guide="You want to find genome-wide significant genetic associations for a specific gene. Optionally add a trait filter to focus disease context.",
)
def gwas_lookup(gene: str = None, trait: str = None, p_threshold: float = 5e-8, **kwargs) -> dict:
    """Query the NHGRI-EBI GWAS Catalog REST API for genetic associations."""
    try:
        import httpx  # noqa: F401
    except ImportError:
        return {"error": "httpx required (pip install httpx)", "summary": "httpx required (pip install httpx)"}
    gene = str(gene or "").strip()
    trait = str(trait or "").strip() or None
    if not gene:
        detail = f" (trait='{trait}')" if trait else ""
        return {
            "error": f"Missing required parameter: gene{detail}",
            "summary": "GWAS lookup requires a non-empty gene symbol (e.g., SNCA, APOE).",
            "gene": gene,
            "trait_filter": trait,
            "suggestion": (
                "First identify candidate genes (e.g., with data_api.opentargets_search), "
                "then run genomics.gwas_lookup with one gene at a time."
            ),
        }

    base = "https://www.ebi.ac.uk/gwas/rest/api"

    # Step 1: Find SNPs associated with the gene
    snp_url = f"{base}/singleNucleotidePolymorphisms/search/findByGene"
    params = {"geneName": gene, "size": 100}

    data, error = _genomics.request_json(
        "GET",
        snp_url,
        params=params,
        timeout=30,
        retries=2,
    )
    if error:
        return {"error": f"GWAS Catalog query failed: {error}", "summary": f"GWAS Catalog query failed: {error}"}
    embedded = data.get("_embedded", {})
    snps = embedded.get("singleNucleotidePolymorphisms", [])

    if not snps:
        return {
            "summary": f"No GWAS associations found for gene {gene}",
            "gene": gene,
            "associations": [],
            "n_associations": 0,
        }

    # Step 2: For each SNP, fetch associations using the summary projection
    # which embeds EFO traits inline (avoids extra per-trait API calls)
    associations = []
    seen = set()

    for snp_entry in snps[:30]:  # Cap at 30 SNPs to limit API calls
        rsid = snp_entry.get("rsId", "")
        if not rsid:
            continue

        # Use the associationBySnp projection which embeds traits inline
        assoc_url = f"{base}/singleNucleotidePolymorphisms/{rsid}/associations"
        assoc_data, assoc_error = _genomics.request_json(
            "GET",
            assoc_url,
            params={"projection": "associationBySnp"},
            timeout=10,
            retries=2,
        )
        if assoc_error:
            continue

        assoc_list = assoc_data.get("_embedded", {}).get("associations", [])

        for assoc in assoc_list:
            pval_mantissa = assoc.get("pvalueMantissa")
            pval_exponent = assoc.get("pvalueExponent")
            if pval_mantissa is not None and pval_exponent is not None:
                try:
                    pval = float(pval_mantissa) * (10 ** int(pval_exponent))
                except (ValueError, TypeError):
                    pval = None
            else:
                pval = None

            # Filter by p-value threshold
            if pval is not None and pval > p_threshold:
                continue

            # Extract risk allele info from loci
            loci = assoc.get("loci", [])
            risk_allele_name = ""
            if loci:
                risk_alleles = loci[0].get("strongestRiskAlleles", [])
                if risk_alleles:
                    risk_allele_name = risk_alleles[0].get("riskAlleleName", "")

            # Extract traits from embedded efoTraits (no extra API call needed)
            efo_traits = assoc.get("efoTraits", [])
            trait_names = [t.get("trait", "") for t in efo_traits if t.get("trait")]
            trait_name = "; ".join(trait_names)

            # Filter by trait if specified
            if trait and trait_name:
                if trait.lower() not in trait_name.lower():
                    continue

            or_value = assoc.get("orPerCopyNum")
            beta = assoc.get("betaNum")
            beta_unit = assoc.get("betaUnit", "")
            beta_direction = assoc.get("betaDirection", "")

            assoc_id = f"{rsid}_{pval}_{trait_name}"
            if assoc_id in seen:
                continue
            seen.add(assoc_id)

            associations.append({
                "rsid": rsid,
                "risk_allele": risk_allele_name,
                "p_value": pval,
                "p_value_str": f"{pval_mantissa}e{pval_exponent}" if pval_mantissa else None,
                "trait": trait_name,
                "or_per_copy": or_value,
                "beta": beta,
                "beta_unit": beta_unit,
                "beta_direction": beta_direction,
                "mapped_gene": gene,
            })

        # Stop early if we have enough
        if len(associations) >= 50:
            break

    # Sort by p-value (most significant first)
    associations.sort(key=lambda x: x["p_value"] if x["p_value"] is not None else 1.0)

    trait_str = f" for trait '{trait}'" if trait else ""
    return {
        "summary": (
            f"GWAS associations for {gene}{trait_str}: "
            f"{len(associations)} genome-wide significant hits (p < {p_threshold})"
        ),
        "gene": gene,
        "trait_filter": trait,
        "p_threshold": p_threshold,
        "n_associations": len(associations),
        "associations": associations[:30],  # Return top 30
    }
