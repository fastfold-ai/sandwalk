"""Structure prediction and molecular dynamics default specialist profiles."""

from __future__ import annotations

from agent_server.default_specialists.helpers import _profile, _skills

STRUCTURE_PREDICTION = _profile(
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
)

MOLECULAR_DYNAMICS = _profile(
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
)
