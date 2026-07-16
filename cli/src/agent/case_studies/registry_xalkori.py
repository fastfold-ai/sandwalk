"""Case study entry: Xalkori (crizotinib)."""

from agent.case_studies.model import CaseStudy

XALKORI = CaseStudy(
    id="xalkori",
    name="Xalkori (crizotinib)",
    compound="crizotinib",
    targets=["ALK", "ROS1", "MET"],
    indication="ALK+ non-small cell lung cancer",
    description=(
        "Crizotinib pioneered precision oncology — the first ALK inhibitor "
        "approved alongside a companion diagnostic. It proved that matching "
        "drugs to molecular subtypes transforms outcomes."
    ),
    thread_goals=[
        {
            "angle": "Target Biology & Fusions",
            "goal": (
                "Investigate ALK fusion biology (EML4-ALK), ROS1 "
                "rearrangements, MET amplification, and expression/dependency "
                "profiles across NSCLC subtypes."
            ),
            "suggested_tools": [
                "target.druggability",
                "target.expression_profile",
                "target.disease_association",
                "genomics.variant_annotate",
            ],
        },
        {
            "angle": "Chemical SAR & Next-Gen Inhibitors",
            "goal": (
                "Analyze crizotinib SAR (aminopyridine scaffold), compare "
                "with next-gen ALK inhibitors (alectinib, lorlatinib), "
                "and structural basis for selectivity."
            ),
            "suggested_tools": [
                "chemistry.sar_analyze",
                "chemistry.similarity_search",
                "chemistry.descriptors",
                "structure.binding_site",
            ],
        },
        {
            "angle": "Resistance & Companion Diagnostics",
            "goal": (
                "Profile crizotinib resistance mutations (L1196M, G1269A), "
                "next-gen ALK inhibitor strategies, and companion diagnostic "
                "requirements for ALK/ROS1 testing."
            ),
            "suggested_tools": [
                "biomarker.resistance_profile",
                "biomarker.mutation_sensitivity",
                "biomarker.panel_select",
                "literature.pubmed_search",
            ],
        },
    ],
)
