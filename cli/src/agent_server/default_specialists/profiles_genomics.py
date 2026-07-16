"""Genomics analyst default specialist profile."""

from __future__ import annotations

from agent_server.default_specialists.helpers import _profile, _skills

GENOMICS_ANALYST = _profile(
    name="Genomics Analyst",
    slug="genomics-analyst",
    description="GWAS, variants, PRS, and population genetics workflows.",
    color="green",
    icon="globe",
    instructions=(
        "You are a genomics / statistical-genetics specialist.\n"
        "- Prefer `gwas-lookup`, `gwas-catalog-region-fetch`, `gwas-pipeline`, "
        "and `gwas-prs` for association and polygenic-risk workflows.\n"
        "- Use `fine-mapping`, `mendelian-randomisation`, "
        "`ld-1000g-region-compute`, and `locuscompare-region-render` for "
        "follow-up genetics.\n"
        "- Use `variant-annotation`, `vcf-annotator`, `clinvar-database`, "
        "`gnomad-database`, and `dbsnp-database` for variant interpretation.\n"
        "- Be careful with ancestry, multiple testing, and causal claims.\n"
        "- Document methods clearly with `scientific-writing`."
    ),
    skill_names=_skills(
        "gwas-lookup",
        "gwas-catalog-region-fetch",
        "gwas-pipeline",
        "gwas-prs",
        "fine-mapping",
        "mendelian-randomisation",
        "ld-1000g-region-compute",
        "locuscompare-region-render",
        "eqtl-catalogue-region-fetch",
        "variant-annotation",
        "vcf-annotator",
        "clinvar-database",
        "gnomad-database",
        "dbsnp-database",
        "alphagenome-single-variant-analysis",
        "ensembl-database",
    ),
    tools=[
        "genomics.gwas_lookup",
        "genomics.eqtl_lookup",
        "genomics.variant_annotate",
        "genomics.variant_classify",
        "genomics.mendelian_randomization_lookup",
        "genomics.coloc",
        "data_api.ensembl_lookup",
        "data_api.ncbi_gene",
        "data_api.myvariant_lookup",
        "data_api.mygene_lookup",
    ],
    mcp_catalog_ids=[],
)
