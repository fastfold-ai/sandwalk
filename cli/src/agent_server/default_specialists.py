"""Built-in specialists seeded once on first empty boot.

Profiles are focused on installed FastFold + science skills, and reinforce the
matching built-in tools (category.tool_name). Shared CORE_SKILLS are attached to
every default specialist.

Seeding runs only when the store has never been seeded and the specialists
table is empty. After that, users fully own the list — deleted defaults are
not recreated, and existing rows are not overwritten on boot.
"""

from __future__ import annotations

from typing import Any

# Shared across curated defaults — discovery, diagrams, reporting.
CORE_SKILLS: list[str] = [
    "diagrams_mermaid",
    "find-skills",
    "scientific-writing",
    "slack_report",
]


def _skills(*names: str) -> list[str]:
    """Domain skills + core, de-duplicated, stable order."""
    seen: set[str] = set()
    out: list[str] = []
    for name in [*names, *CORE_SKILLS]:
        key = name.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _with_tools(body: str, tools: list[str]) -> str:
    """Append a built-in tools section that pairs well with skills."""
    listed = ", ".join(f"`{name}`" for name in tools)
    return (
        body.rstrip()
        + "\n\n"
        + "Built-in tools (use directly for fast lookups / analysis; prefer skills "
        + "for FastFold Cloud, Boltz API, and multi-step workflows):\n"
        + f"- Prefer: {listed}.\n"
        + "- Skills own long-running jobs and API workflows; tools own quick "
        + "compute, docking, descriptors, DepMap/Open Targets/PDB/UniProt queries, "
        + "and local analysis.\n"
        + "- If a needed skill is missing or disabled, tell the user to install or "
        + "enable it (or use `find-skills`) before continuing that path.\n"
    )


def _profile(
    *,
    name: str,
    slug: str,
    description: str,
    color: str,
    icon: str,
    instructions: str,
    skill_names: list[str],
    tools: list[str],
    mcp_catalog_ids: list[str] | None = None,
) -> dict[str, Any]:
    from agent.tool_tiers import CORE_TOOL_NAMES

    # Core tools (shell/skills/files/lookups) + specialist domain tools.
    tool_names = list(dict.fromkeys([*sorted(CORE_TOOL_NAMES), *tools]))
    return {
        "name": name,
        "slug": slug,
        "description": description,
        "color": color,
        "icon": icon,
        "instructions": _with_tools(instructions, tools),
        "skill_names": skill_names,
        "preferred_tools": list(tools),
        "tool_names": tool_names,
        "mcp_catalog_ids": list(mcp_catalog_ids or []),
        "mcp_server_ids": [],
        "enabled": True,
    }


DEFAULT_SPECIALISTS: list[dict[str, Any]] = [
    _profile(
        name="Protein Designer",
        slug="protein-designer",
        description="Binder and protein design with BoltzGen, Boltz design/screen, and sequence tools.",
        color="violet",
        icon="flask",
        instructions=(
            "You are a protein-design specialist.\n"
            "- Lead with `protein_design_boltzgen` for FastFold BoltzGen design-spec workflows.\n"
            "- Use `boltz` for Boltz API `protein:design` / `protein:library-screen` "
            "(estimate-cost → confirm → run; never resubmit to recover results).\n"
            "- Use sequence/MSA helpers (`protein-sequence-msa`, "
            "`protein-sequence-similarity-search`, `recombinator`) when designing from "
            "homologs or libraries.\n"
            "- Prefer `glycoengineering` when glycosylation or glycan design matters.\n"
            "- Summarize candidate metrics clearly and keep iteration loops tight.\n"
            "- Use `diagrams_mermaid` for multi-step design pipelines and "
            "`scientific-writing` / `slack_report` for deliverables.\n"
            "- If Tamarind MCP is connected, use it only when it clearly complements "
            "FastFold design skills."
        ),
        skill_names=_skills(
            "protein_design_boltzgen",
            "boltz",
            "protein-sequence-msa",
            "protein-sequence-similarity-search",
            "recombinator",
            "glycoengineering",
            "target-validation-scorer",
            "esm",
            "uniprot-database",
        ),
        tools=[
            "design.suggest_modifications",
            "protein.embed",
            "protein.function_predict",
            "protein.domain_annotate",
            "dna.codon_optimize",
            "dna.primer_design",
            "dna.gibson_design",
            "structure.ternary_predict",
            "structure.batch_screen",
            "data_api.uniprot_lookup",
            "data_api.pdb_search",
        ],
        mcp_catalog_ids=["tamarind"],
    ),
    _profile(
        name="Small Molecule Screen",
        slug="small-molecule-screen",
        description="Ligand design/screening, ADME, docking, and cheminformatics.",
        color="orange",
        icon="target",
        instructions=(
            "You are a small-molecule discovery specialist.\n"
            "- Prefer `boltz` for Boltz API `small-molecule:design`, "
            "`small-molecule:library-screen`, and ADME (`predictions:adme`) — always "
            "estimate-cost and get explicit approval before billable runs.\n"
            "- Use `rdkit`, `medchem`, `datamol`, `molfeat`, and `matchms` for local "
            "cheminformatics, filters, and descriptors.\n"
            "- Use `chembl-database` / `pubchem-database` for ligand lookups and "
            "`diffdock` for structure-based docking when a receptor pose is needed.\n"
            "- Use `drug-repurposing-screen`, `deepchem`, `torchdrug`, and `pytdc` for "
            "library triage and ML-assisted screens.\n"
            "- Keep SAR notes crisp; flag ADMET risks early.\n"
            "- Use `diagrams_mermaid` for screening funnels and "
            "`scientific-writing` / `slack_report` for readouts.\n"
            "- If Tamarind or Neurosnap MCP is connected, use them as optional "
            "complements—not replacements—for Boltz / local chem tools."
        ),
        skill_names=_skills(
            "boltz",
            "rdkit",
            "medchem",
            "datamol",
            "molfeat",
            "matchms",
            "chembl-database",
            "pubchem-database",
            "diffdock",
            "drug-repurposing-screen",
            "deepchem",
            "torchdrug",
            "pytdc",
            "opentargets-database",
        ),
        tools=[
            "chemistry.descriptors",
            "chemistry.similarity_search",
            "chemistry.sar_analyze",
            "chemistry.mmp_analysis",
            "chemistry.scaffold_hop",
            "chemistry.pubchem_lookup",
            "chemistry.sa_score",
            "chemistry.pharmacophore",
            "chemistry.retrosynthesis",
            "structure.dock",
            "structure.binding_site",
            "structure.compound_3d",
            "structure.batch_screen",
            "data_api.chembl_advanced",
            "data_api.drug_info",
            "clue.compound_signature",
            "repurposing.cmap_query",
            "viability.dose_response",
        ],
        mcp_catalog_ids=["tamarind", "neurosnap"],
    ),
    _profile(
        name="Structure Prediction",
        slug="structure-prediction",
        description="Fold proteins/complexes, fetch known structures, and inspect confidence.",
        color="blue",
        icon="dna",
        instructions=(
            "You are a structure-prediction specialist.\n"
            "- Prefer `fold` for FastFold Cloud jobs (Boltz-2, OpenFold3, Chai-1, etc.).\n"
            "- Use `boltz` for Boltz API structure-and-binding (`sab`) when the user "
            "wants Boltz-native S&B or binding estimates.\n"
            "- Use `alphafold-database-fetch-and-analyze`, `pdb-database`, "
            "`foldseek-structural-search`, and `struct-predictor` to reuse known "
            "structures before spending on new folds.\n"
            "- Use `esm` for embeddings / quick sequence-structure priors when helpful.\n"
            "- Use `pymol` / `diffdock` for inspection or docking follow-ups.\n"
            "- Always report confidence (pLDDT, PAE, ipTM) and surface CIF/PDB links.\n"
            "- If Neurosnap MCP is connected, treat it as optional complementary "
            "folding/docking—prefer FastFold skills when FastFold Cloud is configured."
        ),
        skill_names=_skills(
            "fold",
            "boltz",
            "alphafold-database-fetch-and-analyze",
            "pdb-database",
            "foldseek-structural-search",
            "struct-predictor",
            "esm",
            "pymol",
            "diffdock",
            "uniprot-database",
        ),
        tools=[
            "structure.alphafold_fetch",
            "structure.ternary_predict",
            "structure.batch_screen",
            "structure.dock",
            "structure.binding_site",
            "structure.compound_3d",
            "protein.embed",
            "protein.function_predict",
            "protein.domain_annotate",
            "data_api.pdb_search",
            "data_api.pdbe_search",
            "data_api.uniprot_lookup",
        ],
        mcp_catalog_ids=["neurosnap"],
    ),
    _profile(
        name="Molecular Dynamics",
        slug="molecular-dynamics",
        description="CALVADOS/OpenMM, OpenMMDL, and simulation analysis workflows.",
        color="teal",
        icon="atom",
        instructions=(
            "You are a molecular-dynamics specialist.\n"
            "- Prefer `md_openmm_calvados` for CALVADOS/OpenMM and `md_openmmdl` for "
            "OpenMMDL FastFold Workflows.\n"
            "- Use `molecular-dynamics` / `rowan` for complementary local MD tooling "
            "when FastFold workflows are not the right fit.\n"
            "- Chain from `fold` when the user starts from sequence or needs a "
            "structure before simulation.\n"
            "- Keep workflows private unless the user asks for public links; report "
            "wait times, metrics, and frame extraction clearly.\n"
            "- Use `pymol` for trajectory/structure inspection and "
            "`diagrams_mermaid` for simulation pipelines.\n"
            "- If Latch MCP is connected, use it for platform workflows that "
            "complement FastFold MD skills."
        ),
        skill_names=_skills(
            "md_openmm_calvados",
            "md_openmmdl",
            "molecular-dynamics",
            "fold",
            "rowan",
            "pymol",
        ),
        tools=[
            "structure.md_simulate",
            "structure.fep",
            "structure.dock",
            "structure.binding_site",
            "structure.alphafold_fetch",
            "data_api.pdb_search",
            "data_api.uniprot_lookup",
        ],
        mcp_catalog_ids=["latch"],
    ),
    _profile(
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
    ),
    _profile(
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
    ),
    _profile(
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
    ),
]

_LEGACY_SLUG_REDIRECTS: dict[str, str] = {
    "protein-design": "protein-designer",
}

DEFAULT_SPECIALISTS_SEEDED_META_KEY = "default_specialists_seeded"


def _migrate_legacy_slugs(store: Any) -> None:
    for legacy_slug, new_slug in _LEGACY_SLUG_REDIRECTS.items():
        legacy = store.get_specialist_by_slug(legacy_slug)
        if legacy is None:
            continue
        target = store.get_specialist_by_slug(new_slug)
        if target is None:
            store.update_specialist(legacy.id, slug=new_slug)
        else:
            store.delete_specialist(legacy.id)


def ensure_default_specialists(store: Any) -> list[Any]:
    """Seed curated specialists once on a fresh empty store.

    Safe to call on every boot. After the one-time seed (or when the store
    already had any specialists), never creates or updates defaults again so
    deletes and edits stay under user control.
    """
    _migrate_legacy_slugs(store)

    if store.get_meta(DEFAULT_SPECIALISTS_SEEDED_META_KEY) == "1":
        return []

    existing = store.list_specialists()
    if existing:
        # Prior install / user-owned data — mark seeded without backfilling.
        store.set_meta(DEFAULT_SPECIALISTS_SEEDED_META_KEY, "1")
        return []

    created: list[Any] = []
    for spec in DEFAULT_SPECIALISTS:
        created.append(
            store.create_specialist(
                slug=str(spec["slug"]),
                name=str(spec["name"]),
                description=str(spec.get("description") or "") or None,
                instructions=str(spec.get("instructions") or "") or None,
                color=str(spec.get("color") or "ink"),
                icon=str(spec.get("icon") or "git-branch"),
                skill_names=list(spec.get("skill_names") or []),
                tool_names=list(spec.get("tool_names") or spec.get("preferred_tools") or []),
                mcp_server_ids=list(spec.get("mcp_server_ids") or []),
                mcp_catalog_ids=list(spec.get("mcp_catalog_ids") or []),
                enabled=bool(spec.get("enabled", True)),
            )
        )
    store.set_meta(DEFAULT_SPECIALISTS_SEEDED_META_KEY, "1")
    return created


FAST_COMPUTATIONAL_SCIENTIST_SLUG = "fast-computational-scientist"
FAST_COMPUTATIONAL_SCIENTIST_META_KEY = "fast_computational_scientist_seeded"
DEFAULT_SPECIALIST_TOOL_NAMES_META_KEY = "default_specialist_tool_names_backfilled"


def ensure_default_specialist_tool_names(store: Any) -> int:
    """One-shot: fill empty ``tool_names`` on curated defaults from seed profiles.

    Existing specialists were created before the allowlist field existed, so the
    UI shows ``0 tools``. Populate from ``DEFAULT_SPECIALISTS`` (core + domain
    extras). Never overwrites a non-empty allowlist (user edits win).
    """
    if store.get_meta(DEFAULT_SPECIALIST_TOOL_NAMES_META_KEY) == "1":
        return 0

    updated = 0
    by_slug = {
        str(spec.get("slug") or "").strip(): spec for spec in DEFAULT_SPECIALISTS
    }
    for slug, spec in by_slug.items():
        if not slug:
            continue
        existing = store.get_specialist_by_slug(slug)
        if existing is None:
            continue
        if list(existing.tool_names or []):
            continue
        tools = list(spec.get("tool_names") or spec.get("preferred_tools") or [])
        if not tools:
            continue
        store.update_specialist(existing.id, tool_names=tools)
        updated += 1

    store.set_meta(DEFAULT_SPECIALIST_TOOL_NAMES_META_KEY, "1")
    return updated


def _fast_computational_scientist_spec() -> dict[str, Any]:
    from agent.tool_tiers import CORE_TOOL_NAMES

    core_tools = sorted(CORE_TOOL_NAMES)
    instructions = (
        "You are a Fast computational scientist — a lightweight FastFold-first agent.\n"
        "- Prefer FastFold featured skills for cloud jobs: `fold`, "
        "`protein_design_boltzgen`, `md_openmm_calvados`, `md_openmmdl`.\n"
        "- Use `shell.run` to execute skill scripts; use `run_python` only for "
        "small local analysis or plotting.\n"
        "- Keep tool use minimal. Do not invent skills that are not installed — "
        "tell the user to install/enable them (or use `find-skills`).\n"
        "- Do not pull in broad MCP tool surfaces; stay on FastFold workflows.\n"
    )
    return {
        "name": "Fast computational scientist",
        "slug": FAST_COMPUTATIONAL_SCIENTIST_SLUG,
        "description": (
            "Lightweight FastFold-first profile: featured fold/design/MD skills "
            "and core tools only."
        ),
        "color": "teal",
        "icon": "lightning",
        "instructions": instructions,
        "skill_names": [
            "fold",
            "protein_design_boltzgen",
            "md_openmm_calvados",
            "md_openmmdl",
            "find-skills",
        ],
        "tool_names": core_tools,
        "mcp_catalog_ids": [],
        "mcp_server_ids": [],
        "enabled": True,
    }


def ensure_fast_computational_scientist(store: Any) -> Any | None:
    """Upsert the lightweight FastFold specialist once for existing stores."""
    if store.get_meta(FAST_COMPUTATIONAL_SCIENTIST_META_KEY) == "1":
        existing = store.get_specialist_by_slug(FAST_COMPUTATIONAL_SCIENTIST_SLUG)
        return existing

    spec = _fast_computational_scientist_spec()
    existing = store.get_specialist_by_slug(FAST_COMPUTATIONAL_SCIENTIST_SLUG)
    if existing is not None:
        store.set_meta(FAST_COMPUTATIONAL_SCIENTIST_META_KEY, "1")
        return existing

    created = store.create_specialist(
        slug=str(spec["slug"]),
        name=str(spec["name"]),
        description=str(spec.get("description") or "") or None,
        instructions=str(spec.get("instructions") or "") or None,
        color=str(spec.get("color") or "teal"),
        icon=str(spec.get("icon") or "lightning"),
        skill_names=list(spec.get("skill_names") or []),
        tool_names=list(spec.get("tool_names") or []),
        mcp_server_ids=list(spec.get("mcp_server_ids") or []),
        mcp_catalog_ids=list(spec.get("mcp_catalog_ids") or []),
        enabled=bool(spec.get("enabled", True)),
    )
    store.set_meta(FAST_COMPUTATIONAL_SCIENTIST_META_KEY, "1")
    return created


def filter_mcp_servers_for_specialist(
    servers: list[dict[str, Any]],
    *,
    mcp_server_ids: list[str] | None,
    mcp_catalog_ids: list[str] | None,
) -> list[dict[str, Any]]:
    """Keep runtime MCP servers allowed by specialist server ids and/or catalog ids."""
    allowed_ids = {str(item).strip() for item in (mcp_server_ids or []) if str(item).strip()}
    allowed_catalogs = {
        str(item).strip() for item in (mcp_catalog_ids or []) if str(item).strip()
    }
    if not allowed_ids and not allowed_catalogs:
        return []
    matched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for server in servers:
        server_id = str(server.get("id") or "").strip()
        catalog_id = str(server.get("catalog_id") or "").strip()
        if server_id and server_id in allowed_ids:
            pass
        elif catalog_id and catalog_id in allowed_catalogs:
            pass
        else:
            continue
        key = server_id or catalog_id
        if not key or key in seen:
            continue
        seen.add(key)
        matched.append(server)
    return matched
