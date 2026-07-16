"""Protein design and small-molecule screening default specialist profiles."""

from __future__ import annotations

from agent_server.default_specialists.helpers import _profile, _skills

PROTEIN_DESIGNER = _profile(
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
)

SMALL_MOLECULE_SCREEN = _profile(
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
)
