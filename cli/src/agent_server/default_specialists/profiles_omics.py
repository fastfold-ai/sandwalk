"""Target discovery and single-cell analysis default specialist profiles."""

from __future__ import annotations

from agent_server.default_specialists.helpers import _profile, _skills

TARGET_DISCOVERY = _profile(
    name="Target Discovery",
    slug="target-discovery",
    description="Target evidence, pathways, DepMap, and drug–target mapping.",
    color="indigo",
    icon="microscope",
    instructions=(
        "You are a target-discovery specialist.\n"
        "- Prefer `opentargets-database`, `chembl-database`, `string-database`, "
        "`reactome-database`, and `uniprot-database` for target evidence.\n"
        "- Use `depmap` for dependency / essentiality context and "
        "`omics-target-evidence-mapper` / `target-validation-scorer` to score "
        "hypotheses.\n"
        "- Use `pathway-enricher` / `pathway-enrichment` and `primekg` for "
        "pathway and knowledge-graph views.\n"
        "- Use `drug-repurposing-screen` when mapping targets to known drugs.\n"
        "- Be explicit about evidence strength and conflicting sources.\n"
        "- Deliver concise target briefs with `scientific-writing` / `slack_report`."
    ),
    skill_names=_skills(
        "opentargets-database",
        "chembl-database",
        "string-database",
        "reactome-database",
        "uniprot-database",
        "depmap",
        "omics-target-evidence-mapper",
        "target-validation-scorer",
        "pathway-enricher",
        "pathway-enrichment",
        "primekg",
        "drug-repurposing-screen",
        "human-protein-atlas-database",
    ),
    tools=[
        "target.disease_association",
        "target.druggability",
        "target.coessentiality",
        "target.expression_profile",
        "target.neosubstrate_score",
        "target.degron_predict",
        "data_api.opentargets_search",
        "data_api.depmap_search",
        "data_api.chembl_advanced",
        "data_api.drug_info",
        "data_api.uniprot_lookup",
        "data_api.reactome_pathway_search",
        "network.ppi_analysis",
        "network.pathway_crosstalk",
        "expression.pathway_enrichment",
        "viability.tissue_selectivity",
    ],
    mcp_catalog_ids=[],
)

SINGLE_CELL_ANALYST = _profile(
    name="Single-cell Analyst",
    slug="single-cell-analyst",
    description="scRNA-seq QC, embedding, DE, and atlas queries.",
    color="pink",
    icon="sparkles",
    instructions=(
        "You are a single-cell / transcriptomics specialist.\n"
        "- Prefer `scanpy`, `single-cell-rna-qc`, `scrna-embedding`, "
        "`scrna-orchestrator`, `scvelo`, and `scvi-tools` for analysis loops.\n"
        "- Use `cellxgene-census` for atlas queries and `anndata` / `zarr-python` "
        "for data plumbing.\n"
        "- For bulk RNA-seq, use `bulk-rnaseq`, `rnaseq-de`, `pydeseq2`, and "
        "`de-summary`.\n"
        "- Use nf-core wrappers when a full pipeline is warranted.\n"
        "- Always state QC assumptions, batch effects, and limitations.\n"
        "- Use `diagrams_mermaid` for analysis DAGs and "
        "`scientific-writing` for methods/results."
    ),
    skill_names=_skills(
        "scanpy",
        "single-cell-rna-qc",
        "scrna-embedding",
        "scrna-orchestrator",
        "scvelo",
        "scvi-tools",
        "cellxgene-census",
        "anndata",
        "zarr-python",
        "bulk-rnaseq",
        "rnaseq-de",
        "pydeseq2",
        "de-summary",
        "nfcore-scrnaseq-wrapper",
        "nfcore-rnaseq-wrapper",
        "sample-qc-triage",
        "umap-learn",
    ),
    tools=[
        "singlecell.cluster",
        "singlecell.trajectory",
        "singlecell.cell_type_annotate",
        "cellxgene.gene_expression",
        "cellxgene.cell_type_markers",
        "cellxgene.dataset_search",
        "omics.cellxgene_search",
        "omics.cellxgene_fetch",
        "omics.deseq2",
        "expression.diff_expression",
        "expression.pathway_enrichment",
    ],
    mcp_catalog_ids=[],
)
