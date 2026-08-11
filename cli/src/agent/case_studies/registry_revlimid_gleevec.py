"""Case study entries: Revlimid (lenalidomide) and Gleevec (imatinib)."""

from agent.case_studies.model import CaseStudy

REVLIMID = CaseStudy(
    id="revlimid",
    name="Revlimid (lenalidomide)",
    compound="lenalidomide",
    targets=["CRBN", "IKZF1", "IKZF3"],
    indication="multiple myeloma",
    description=(
        "Lenalidomide is the poster child of molecular glue degraders — "
        "an IMiD that hijacks CRBN to degrade IKZF1/3 transcription factors. "
        "A $12B/yr blockbuster that transformed myeloma treatment."
    ),
    thread_goals=[
        {
            "angle": "Target Biology & Mechanism",
            "goal": (
                "Investigate CRBN E3 ligase biology, IKZF1/IKZF3 neosubstrate "
                "degradation mechanism, and co-essential gene networks for "
                "lenalidomide targets in multiple myeloma."
            ),
            "suggested_tools": [
                "target.druggability",
                "target.expression_profile",
                "target.coessentiality",
                "target.disease_association",
            ],
        },
        {
            "angle": "Chemical Analysis & SAR",
            "goal": (
                "Analyze lenalidomide structure, SAR landscape, find similar "
                "IMiD compounds in ChEMBL, and assess ADMET properties."
            ),
            "suggested_tools": [
                "chemistry.similarity_search",
                "chemistry.sar_analyze",
                "chemistry.descriptors",
                "safety.admet_predict",
            ],
        },
        {
            "angle": "Clinical Landscape",
            "goal": (
                "Map lenalidomide clinical indications, competitive landscape "
                "in multiple myeloma, active clinical trials, and patient "
                "population estimates."
            ),
            "suggested_tools": [
                "clinical.indication_map",
                "clinical.competitive_landscape",
                "clinical.trial_search",
                "clinical.population_size",
            ],
        },
        {
            "angle": "Safety & Resistance",
            "goal": (
                "Profile lenalidomide safety: SALL4 risk, antitarget activity, "
                "known resistance mutations in CRBN, and biomarker strategy "
                "for patient selection."
            ),
            "suggested_tools": [
                "safety.sall4_risk",
                "safety.antitarget_profile",
                "biomarker.resistance_profile",
                "biomarker.mutation_sensitivity",
            ],
        },
    ],
)

GLEEVEC = CaseStudy(
    id="gleevec",
    name="Gleevec (imatinib)",
    compound="imatinib",
    targets=["BCR-ABL", "ABL1", "KIT", "PDGFRA"],
    indication="chronic myeloid leukemia",
    description=(
        "Imatinib revolutionized cancer therapy as the first rationally "
        "designed kinase inhibitor. It transformed CML from a fatal "
        "diagnosis to a manageable chronic condition."
    ),
    thread_goals=[
        {
            "angle": "Target Biology & Selectivity",
            "goal": (
                "Investigate BCR-ABL fusion biology, ABL1 kinase domain, "
                "off-target kinase activity on KIT and PDGFRA, and "
                "expression profiles across leukemia subtypes."
            ),
            "suggested_tools": [
                "target.druggability",
                "target.expression_profile",
                "data_api.uniprot_lookup",
                "network.ppi_analysis",
            ],
        },
        {
            "angle": "Structural & Chemical Analysis",
            "goal": (
                "Analyze imatinib binding mode, SAR of 2-phenylaminopyrimidine "
                "scaffold, compare with nilotinib/dasatinib, and assess "
                "key pharmacophore features."
            ),
            "suggested_tools": [
                "chemistry.sar_analyze",
                "chemistry.similarity_search",
                "chemistry.pharmacophore",
                "structure.binding_site",
            ],
        },
        {
            "angle": "Resistance & Biomarkers",
            "goal": (
                "Profile imatinib resistance mutations (T315I gatekeeper), "
                "resistance mechanisms, and biomarker-guided treatment "
                "selection strategies in CML."
            ),
            "suggested_tools": [
                "biomarker.resistance_profile",
                "biomarker.mutation_sensitivity",
                "genomics.variant_annotate",
                "literature.pubmed_search",
            ],
        },
    ],
)
