"""Workflow templates: target validation through script authoring."""

WORKFLOWS_VALIDATION_SAFETY = {
    "target_validation": {
        "description": "Validate a potential drug target",
        "trigger_phrases": [
            "validate target", "is this a good target", "target assessment",
            "druggable target", "target validation",
        ],
        "steps": [
            {"tool": "target.coessentiality", "why": "Find functionally related genes and synthetic lethal partners"},
            {"tool": "literature.pubmed_search", "why": "Check published validation data and known biology"},
            {"tool": "clinical.indication_map", "why": "Map to cancer indications with PRISM sensitivity data"},
            {"tool": "biomarker.mutation_sensitivity", "why": "Check if mutations in the target affect drug response"},
            {"tool": "clinical.tcga_stratify", "why": "Assess target expression across cancer types via TCGA"},
        ],
    },
    "compound_safety": {
        "description": "Full safety assessment of a compound",
        "trigger_phrases": [
            "safety assessment", "is this compound safe", "toxicity profile",
            "safety check", "off-target",
        ],
        "steps": [
            {"tool": "safety.antitarget_profile", "why": "Screen for off-target degradation of tumor suppressors and essential proteins"},
            {"tool": "safety.sall4_risk", "why": "Assess teratogenicity risk via SALL4 degradation (IMiD-type liability)"},
            {"tool": "safety.classify", "why": "Get overall SAFE/CAUTION/DANGEROUS verdict combining all signals"},
            {"tool": "viability.tissue_selectivity", "why": "Check for broad vs selective killing across tissue types"},
        ],
    },
    "hit_characterization": {
        "description": "Characterize a hit compound from a screen",
        "trigger_phrases": [
            "characterize compound", "hit characterization", "what does this compound do",
            "compound profile", "hit profiling",
        ],
        "steps": [
            {"tool": "chemistry.descriptors", "why": "Get molecular properties, drug-likeness, and Lipinski profile"},
            {"tool": "viability.dose_response", "why": "Understand potency across cell lines with IC50 estimates"},
            {"tool": "expression.pathway_enrichment", "why": "Identify affected pathways from L1000 transcriptomic signature"},
            {"tool": "safety.classify", "why": "Quick safety classification before advancing the compound"},
            {"tool": "literature.chembl_query", "why": "Find related compounds and known bioactivity in ChEMBL"},
        ],
    },
    "combination_therapy": {
        "description": "Design a combination therapy strategy",
        "trigger_phrases": [
            "combination therapy", "synergy", "combine with", "drug combination",
            "synthetic lethality", "combination strategy",
        ],
        "steps": [
            {"tool": "combination.synergy_predict", "why": "Find synergistic partners via anti-correlated transcriptomic signatures"},
            {"tool": "combination.synthetic_lethality", "why": "Mine DepMap for synthetic lethal gene pairs"},
            {"tool": "combination.metabolic_vulnerability", "why": "Identify exploitable metabolic dependencies for combination"},
            {"tool": "expression.immune_score", "why": "Check IO potential for immuno-oncology combinations"},
        ],
    },
    "clinical_positioning": {
        "description": "Position a compound for clinical development",
        "trigger_phrases": [
            "clinical positioning", "which indication", "patient population",
            "go-to-market", "clinical strategy", "indication selection",
        ],
        "steps": [
            {"tool": "clinical.indication_map", "why": "Map compound sensitivity to cancer indications"},
            {"tool": "clinical.population_size", "why": "Estimate addressable patient populations per indication"},
            {"tool": "biomarker.mutation_sensitivity", "why": "Identify predictive biomarkers for patient selection"},
            {"tool": "clinical.tcga_stratify", "why": "Validate target expression in patient tumors via TCGA"},
            {"tool": "clinical.trial_design_benchmark", "why": "Benchmark endpoint and protocol design patterns in the current trial landscape"},
            {"tool": "literature.pubmed_search", "why": "Review clinical landscape and competitor data"},
        ],
    },
    "cro_engagement": {
        "description": "Design experiment and engage a CRO for outsourced work",
        "trigger_phrases": [
            "find a CRO", "outsource experiment", "CRO inquiry",
            "contract research", "send to CRO",
        ],
        "steps": [
            {"tool": "experiment.design_assay", "why": "Generate a detailed assay protocol"},
            {"tool": "experiment.estimate_timeline", "why": "Get time and cost estimates for the experiment"},
            {"tool": "cro.match_experiment", "why": "Find best-fit CROs for the assay type"},
            {"tool": "cro.draft_inquiry", "why": "Generate a professional inquiry email to the top CRO"},
        ],
    },
    "structure_prediction": {
        "description": "Predict ternary complex structure for a molecular glue",
        "trigger_phrases": [
            "predict structure", "ternary complex", "structural prediction",
            "dock compound", "binding mode",
        ],
        "steps": [
            {"tool": "structure.alphafold_fetch", "why": "Download AlphaFold structure for the target protein"},
            {"tool": "structure.compound_3d", "why": "Generate 3D conformer for the compound"},
            {"tool": "structure.ternary_predict", "why": "Predict ternary complex (E3 + compound + target)"},
            {"tool": "chemistry.descriptors", "why": "Get molecular properties for structure-activity context"},
        ],
    },
    "gpu_computation": {
        "description": "Submit and manage GPU compute jobs",
        "trigger_phrases": [
            "GPU computation", "run Boltz", "run AlphaFold", "submit job",
            "cloud compute", "estimate cost",
        ],
        "steps": [
            {"tool": "compute.estimate_cost", "why": "Get cost and time estimate before committing resources"},
            {"tool": "compute.list_providers", "why": "Review available GPU providers and pricing"},
            {"tool": "compute.submit_job", "why": "Submit the computation job (dry_run by default)"},
        ],
    },
    "custom_analysis": {
        "description": "Custom data exploration or visualization",
        "trigger_phrases": [
            "create a plot", "make a visualization", "custom analysis",
            "heatmap", "volcano plot", "statistical test", "scatter plot",
        ],
        "steps": [
            {"tool": "code.execute", "why": "Generate custom analysis code"},
        ],
    },
    "script_authoring": {
        "description": "Write or update a standalone script/code file in the workspace",
        "trigger_phrases": [
            "write a python script", "save as .py", "create script file",
            "generate a script",
        ],
        "steps": [
            {"tool": "files.create_file", "why": "Create the requested script file with full code content"},
            {"tool": "files.read_file", "why": "Verify file contents after writing"},
        ],
    },
}
