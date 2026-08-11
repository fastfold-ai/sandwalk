"""Case study entries: Keytruda (pembrolizumab) and Ozempic (semaglutide)."""

from agent.case_studies.model import CaseStudy

KEYTRUDA = CaseStudy(
    id="keytruda",
    name="Keytruda (pembrolizumab)",
    compound="pembrolizumab",
    targets=["PD-1", "PDCD1"],
    indication="non-small cell lung cancer",
    description=(
        "Pembrolizumab is the world's best-selling drug ($25B/yr) — "
        "a PD-1 checkpoint inhibitor that unleashes the immune system "
        "against cancer. Approved in 30+ tumor types."
    ),
    thread_goals=[
        {
            "angle": "Immuno-Oncology Mechanism",
            "goal": (
                "Investigate PD-1/PD-L1 checkpoint biology, immune evasion "
                "mechanisms, and immune cell infiltration patterns across "
                "pembrolizumab-responsive tumor types."
            ),
            "suggested_tools": [
                "target.expression_profile",
                "target.disease_association",
                "expression.immune_score",
                "expression.deconvolution",
            ],
        },
        {
            "angle": "Biomarker Strategy",
            "goal": (
                "Analyze pembrolizumab biomarkers: PD-L1 expression (TPS/CPS), "
                "MSI-H/dMMR, TMB, and emerging biomarkers for response "
                "prediction across indications."
            ),
            "suggested_tools": [
                "biomarker.panel_select",
                "biomarker.mutation_sensitivity",
                "genomics.gwas_lookup",
                "literature.pubmed_search",
            ],
        },
        {
            "angle": "Clinical Positioning",
            "goal": (
                "Map pembrolizumab across 30+ approved indications, "
                "competitive landscape vs nivolumab/atezolizumab, ongoing "
                "combination trials, and market positioning."
            ),
            "suggested_tools": [
                "clinical.indication_map",
                "clinical.competitive_landscape",
                "clinical.trial_search",
                "clinical.population_size",
            ],
        },
        {
            "angle": "Combination & Resistance",
            "goal": (
                "Explore pembrolizumab combination strategies (chemo, TKIs, "
                "other I/O agents), mechanisms of acquired resistance, and "
                "potential synergy partners."
            ),
            "suggested_tools": [
                "combination.synergy_predict",
                "biomarker.resistance_profile",
                "literature.pubmed_search",
                "expression.pathway_enrichment",
            ],
        },
    ],
)

OZEMPIC = CaseStudy(
    id="ozempic",
    name="Ozempic (semaglutide)",
    compound="semaglutide",
    targets=["GLP1R"],
    indication="type 2 diabetes / obesity",
    description=(
        "Semaglutide is the GLP-1 receptor agonist behind the obesity "
        "revolution. Originally for T2D, it crossed over into obesity, "
        "cardiovascular protection, and potentially NASH/MASH."
    ),
    thread_goals=[
        {
            "angle": "Target Biology & Signaling",
            "goal": (
                "Investigate GLP-1 receptor biology, downstream signaling "
                "cascades, expression across metabolic tissues, and "
                "structural basis for semaglutide binding."
            ),
            "suggested_tools": [
                "target.druggability",
                "target.expression_profile",
                "data_api.uniprot_lookup",
                "expression.pathway_enrichment",
            ],
        },
        {
            "angle": "Clinical Indications & Expansion",
            "goal": (
                "Map semaglutide clinical indications (T2D, obesity, CVOT), "
                "pipeline expansion into NASH/MASH and Alzheimer's, "
                "competitive landscape vs tirzepatide."
            ),
            "suggested_tools": [
                "clinical.indication_map",
                "clinical.competitive_landscape",
                "clinical.trial_search",
                "clinical.population_size",
            ],
        },
        {
            "angle": "Safety & Pharmacology",
            "goal": (
                "Assess semaglutide safety profile: GI side effects, "
                "thyroid C-cell risk, pancreatitis signal, and long-term "
                "cardiovascular outcomes data."
            ),
            "suggested_tools": [
                "safety.admet_predict",
                "safety.classify",
                "literature.pubmed_search",
                "data_api.drug_info",
            ],
        },
    ],
)
