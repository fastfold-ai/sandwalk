"""Workflow templates: mutation resistance through single-cell omics."""

WORKFLOWS_RESISTANCE_OMICS_EARLY = {
    "mutation_resistance": {
        "description": "Identify clinically observed resistance mutations for a drug or drug class",
        "trigger_phrases": [
            "resistance mutation", "clinically observed mutation", "mutation frequency",
            "IMiD resistance", "drug resistance mutation", "acquired resistance",
        ],
        "steps": [
            {"tool": "literature.pubmed_search", "why": "Search for publications on clinically observed resistance mutations"},
            {"tool": "data_api.opentargets_search", "why": "Get known genetic associations and somatic mutations from Open Targets"},
            {"tool": "biomarker.mutation_sensitivity", "why": "Check if mutations correlate with drug sensitivity in preclinical data"},
            {"tool": "biomarker.resistance_profile", "why": "Build comprehensive resistance profile"},
            {"tool": "literature.openalex_search", "why": "Search for additional clinical mutation data in recent literature"},
        ],
    },
    "protac_design": {
        "description": "Analyze PROTAC linker and component properties",
        "trigger_phrases": [
            "PROTAC", "linker length", "linker composition", "bifunctional degrader",
            "dBET", "MZ1", "ARV", "PROTAC design",
        ],
        "steps": [
            {"tool": "chemistry.pubchem_lookup", "why": "Look up PROTAC structures and molecular properties"},
            {"tool": "chemistry.descriptors", "why": "Calculate molecular descriptors including MW, logP, TPSA for PROTACs"},
            {"tool": "literature.chembl_query", "why": "Find ChEMBL bioactivity data for PROTACs"},
            {"tool": "literature.pubmed_search", "why": "Search for PROTAC SAR and linkerology publications"},
        ],
    },
    "compound_comparison": {
        "description": "Compare two or more compounds on activity and selectivity",
        "trigger_phrases": [
            "compare compounds", "versus", "differential sensitivity",
            "compare selectivity", "compare potency", "which is more potent",
        ],
        "steps": [
            {"tool": "chemistry.pubchem_lookup", "why": "Look up each compound separately to get structures and properties"},
            {"tool": "viability.dose_response", "why": "Get dose-response for first compound (run separately for each)"},
            {"tool": "viability.tissue_selectivity", "why": "Get tissue selectivity for first compound"},
            {"tool": "literature.pubmed_search", "why": "Search published head-to-head comparisons"},
            {"tool": "literature.chembl_query", "why": "Get bioactivity data from ChEMBL for comparison"},
        ],
    },
    "patient_population": {
        "description": "Estimate addressable patient population for a drug concept",
        "trigger_phrases": [
            "patient population", "addressable population", "market sizing",
            "how many patients", "incidence", "prevalence",
        ],
        "steps": [
            {"tool": "clinical.population_size", "why": "Get SEER incidence data for the indication"},
            {"tool": "clinical.trial_search", "why": "Check current trials for treatment rates and eligible populations"},
            {"tool": "clinical.competitive_landscape", "why": "Understand competitive landscape and unmet need"},
            {"tool": "literature.pubmed_search", "why": "Find epidemiology data and treatment utilization rates"},
        ],
    },
    "omics_scrnaseq_analysis": {
        "description": "Analyze single-cell RNA-seq data for a gene or disease",
        "trigger_phrases": [
            "single-cell analysis", "scRNA-seq", "analyze single-cell",
            "single cell RNA", "cell type composition",
        ],
        "steps": [
            {"tool": "omics.geo_search", "why": "Search GEO for relevant scRNA-seq datasets"},
            {"tool": "omics.cellxgene_search", "why": "Search CELLxGENE for curated single-cell datasets"},
            {"tool": "omics.geo_fetch", "why": "Download the most relevant dataset"},
            {"tool": "omics.dataset_info", "why": "Inspect dataset structure and metadata"},
            {"tool": "singlecell.cluster", "why": "Cluster cells and identify populations"},
            {"tool": "singlecell.cell_type_annotate", "why": "Annotate cell types using marker genes"},
            {"tool": "expression.pathway_enrichment", "why": "Identify enriched pathways in cell populations"},
        ],
    },
}
