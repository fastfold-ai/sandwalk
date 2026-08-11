"""Workflow templates: report generation through treatment landscape."""

WORKFLOWS_CLINICAL_STRUCTURE = {
    "report_generation": {
        "description": "Generate and save a research report",
        "trigger_phrases": [
            "write a report", "save report", "export findings",
            "generate report", "create a report",
        ],
        "steps": [
            {"tool": "code.execute", "why": "Run analysis and gather data"},
            {"tool": "files.write_report", "why": "Save formatted report to output directory"},
        ],
    },
    "genetic_evidence": {
        "description": "Build a comprehensive genetic evidence case for a target-disease link",
        "trigger_phrases": [
            "genetic evidence", "causal evidence", "Mendelian randomization",
            "GWAS evidence", "genetic validation", "causal link",
        ],
        "steps": [
            {"tool": "genomics.gwas_lookup", "why": "Find genome-wide significant associations"},
            {"tool": "genomics.eqtl_lookup", "why": "Check expression QTLs across tissues"},
            {"tool": "genomics.mendelian_randomization_lookup", "why": "Assess causal evidence via MR"},
            {"tool": "genomics.coloc", "why": "Test GWAS-eQTL colocalization (shared causal variant)"},
            {"tool": "target.expression_profile", "why": "Understand tissue expression pattern"},
        ],
    },
    "lead_optimization": {
        "description": "Optimize a hit compound into a lead",
        "trigger_phrases": [
            "optimize compound", "lead optimization", "improve potency",
            "SAR", "improve ADMET", "make analogs",
        ],
        "steps": [
            {"tool": "chemistry.sar_analyze", "why": "Understand current SAR landscape"},
            {"tool": "chemistry.mmp_analysis", "why": "Find matched molecular pair transformations that improve properties"},
            {"tool": "chemistry.scaffold_hop", "why": "Generate scaffold-hopped analogs for IP space"},
            {"tool": "design.suggest_modifications", "why": "Get medicinal chemistry modification suggestions"},
            {"tool": "safety.admet_predict", "why": "Predict ADMET for top candidates"},
            {"tool": "chemistry.retrosynthesis", "why": "Check synthetic accessibility of top analogs"},
        ],
    },
    "protein_deep_dive": {
        "description": "Comprehensive protein characterization",
        "trigger_phrases": [
            "tell me about this protein", "protein function", "protein structure",
            "domain architecture", "protein characterization",
        ],
        "steps": [
            {"tool": "protein.function_predict", "why": "Get full UniProt annotation: function, location, GO terms"},
            {"tool": "protein.domain_annotate", "why": "Map domain architecture from InterPro"},
            {"tool": "data_api.pdb_search", "why": "Find experimental structures"},
            {"tool": "target.expression_profile", "why": "Tissue expression from GTEx and HPA"},
            {"tool": "network.ppi_analysis", "why": "Map protein interaction partners"},
        ],
    },
    "drug_repurposing": {
        "description": "Find repurposing opportunities for existing drugs",
        "trigger_phrases": [
            "repurpose", "drug repurposing", "new indication",
            "repositioning", "off-label", "existing drug for",
        ],
        "steps": [
            {"tool": "repurposing.cmap_query", "why": "Match drug expression signature to disease signatures"},
            {"tool": "data_api.drug_info", "why": "Get comprehensive drug profile and known indications"},
            {"tool": "clinical.trial_search", "why": "Check ongoing trials in the new indication"},
            {"tool": "literature.patent_search", "why": "Assess IP landscape for new indication"},
            {"tool": "clinical.competitive_landscape", "why": "Map competitors in the target indication"},
        ],
    },
    "molecular_docking": {
        "description": "Dock compounds into a protein target and analyze binding",
        "trigger_phrases": [
            "dock", "docking", "binding mode", "binding site",
            "virtual screening", "binding affinity",
        ],
        "steps": [
            {"tool": "structure.alphafold_fetch", "why": "Get protein structure (AlphaFold if no experimental)"},
            {"tool": "structure.binding_site", "why": "Identify druggable binding pockets"},
            {"tool": "structure.compound_3d", "why": "Generate 3D ligand conformer"},
            {"tool": "structure.dock", "why": "Dock ligand into binding site"},
            {"tool": "design.suggest_modifications", "why": "Suggest modifications to improve binding"},
        ],
    },
    "resistance_analysis": {
        "description": "Analyze drug resistance mechanisms and predict resistance-associated biomarkers",
        "trigger_phrases": [
            "resistance mechanism", "resistance profile", "drug resistance",
            "resistance mutation", "acquired resistance", "resistance biomarker",
        ],
        "steps": [
            {"tool": "biomarker.mutation_sensitivity", "why": "Identify mutations that alter drug sensitivity — potential resistance drivers"},
            {"tool": "expression.l1000_similarity", "why": "Find compounds with similar transcriptomic signatures to identify resistance-associated expression patterns"},
            {"tool": "expression.pathway_enrichment", "why": "Map resistance-associated expression changes to pathways (e.g., efflux, bypass signaling)"},
            {"tool": "literature.pubmed_search", "why": "Search published literature for known resistance mechanisms to this drug/target class"},
            {"tool": "biomarker.resistance_profile", "why": "Build comprehensive resistance profile combining mutation, expression, and literature data"},
        ],
    },
    "therapeutic_window": {
        "description": "Assess therapeutic window by comparing on-target vs off-target toxicity",
        "trigger_phrases": [
            "therapeutic window", "therapeutic index", "selectivity index",
            "on-target toxicity", "off-target toxicity", "safety margin",
        ],
        "steps": [
            {"tool": "viability.dose_response", "why": "Get dose-response in target cancer cell lines to establish efficacy range"},
            {"tool": "viability.tissue_selectivity", "why": "Compare sensitivity across tissue types to identify selective vs broadly toxic profiles"},
            {"tool": "viability.tissue_selectivity", "why": "Compare sensitivity across lineages to calculate therapeutic window between sensitive and resistant tissue types"},
            {"tool": "safety.antitarget_profile", "why": "Screen for off-target degradation of tumor suppressors and essential proteins"},
            {"tool": "safety.classify", "why": "Get overall safety classification combining all toxicity signals"},
        ],
    },
    "competitive_landscape": {
        "description": "Map the competitive landscape for a drug target or indication",
        "trigger_phrases": [
            "competitive landscape", "competitor analysis", "market landscape",
            "clinical pipeline", "what drugs target", "who else is developing",
        ],
        "steps": [
            {"tool": "clinical.competitive_landscape", "why": "Aggregate competitive intelligence from Open Targets, ChEMBL, and ClinicalTrials.gov"},
            {"tool": "clinical.trial_search", "why": "Search ClinicalTrials.gov for active and recruiting trials in the indication"},
            {"tool": "literature.pubmed_search", "why": "Find recent publications on clinical results and competitor compounds"},
            {"tool": "clinical.indication_map", "why": "Map compound sensitivity to cancer indications to identify positioning opportunities"},
        ],
    },
    "treatment_landscape": {
        "description": "Describe standard of care treatment and where a drug class fits",
        "trigger_phrases": [
            "standard of care", "treatment sequencing", "treatment regimen",
            "approved therapies", "treatment landscape", "where do",
        ],
        "steps": [
            {"tool": "literature.pubmed_search", "why": "Search for current treatment guidelines and landmark trials"},
            {"tool": "clinical.trial_search", "why": "Search ClinicalTrials.gov for current and recent trials establishing standard of care"},
            {"tool": "clinical.competitive_landscape", "why": "Map all approved and investigational drugs for the indication"},
            {"tool": "data_api.opentargets_search", "why": "Get Open Targets disease-level drug and target landscape"},
        ],
    },
}
