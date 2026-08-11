"""Workflow templates: bulk/epigenomics/multi-omics/spatial omics analyses."""

WORKFLOWS_OMICS_LATE = {
    "omics_bulk_analysis": {
        "description": "Analyze bulk RNA-seq or expression data",
        "trigger_phrases": [
            "bulk RNA-seq", "bulk expression", "differential expression from GEO",
            "analyze expression data", "gene expression dataset",
        ],
        "steps": [
            {"tool": "omics.geo_search", "why": "Search GEO for relevant expression datasets"},
            {"tool": "omics.geo_fetch", "why": "Download the expression matrix"},
            {"tool": "omics.dataset_info", "why": "Inspect dataset structure and dimensions"},
            {"tool": "omics.deseq2", "why": "Run DESeq2 with explicit sample metadata (condition labels) for robust count-based differential expression"},
            {"tool": "expression.pathway_enrichment", "why": "Identify enriched pathways from DEGs"},
        ],
    },
    "omics_data_discovery": {
        "description": "Find and evaluate public datasets for a research question",
        "trigger_phrases": [
            "find dataset", "find public data", "search for datasets",
            "available data", "download data", "data discovery",
        ],
        "steps": [
            {"tool": "omics.geo_search", "why": "Search NCBI GEO for relevant datasets"},
            {"tool": "omics.cellxgene_search", "why": "Search CELLxGENE for curated single-cell data"},
            {"tool": "omics.tcga_search", "why": "Search TCGA/GDC for cancer genomics data"},
            {"tool": "omics.dataset_info", "why": "Inspect and summarize the top dataset"},
        ],
    },
    "omics_methylation_analysis": {
        "description": "Analyze DNA methylation data for differential methylation",
        "trigger_phrases": [
            "methylation analysis", "differential methylation", "DNA methylation",
            "CpG methylation", "epigenetic analysis",
        ],
        "steps": [
            {"tool": "omics.geo_search", "why": "Search GEO for methylation datasets"},
            {"tool": "omics.geo_fetch", "why": "Download methylation beta-value matrix"},
            {"tool": "omics.dataset_info", "why": "Inspect dataset structure"},
            {"tool": "omics.methylation_profile", "why": "Summarize global methylation landscape"},
            {"tool": "omics.methylation_diff", "why": "Identify differentially methylated sites using explicit case/control sample groups"},
            {"tool": "omics.methylation_cluster", "why": "Cluster samples by methylation patterns"},
        ],
    },
    "omics_proteomics_analysis": {
        "description": "Analyze proteomics data for differential protein abundance",
        "trigger_phrases": [
            "proteomics analysis", "differential protein", "protein abundance",
            "mass spectrometry", "TMT proteomics",
        ],
        "steps": [
            {"tool": "omics.dataset_info", "why": "Inspect proteomics data structure"},
            {"tool": "omics.proteomics_diff", "why": "Differential protein abundance analysis with explicit sample grouping"},
            {"tool": "omics.proteomics_enrich", "why": "Pathway enrichment of DE proteins"},
        ],
    },
    "omics_epigenomics_analysis": {
        "description": "Analyze ATAC-seq or ChIP-seq epigenomic data",
        "trigger_phrases": [
            "ATAC-seq analysis", "ChIP-seq analysis", "chromatin accessibility",
            "epigenomic profiling", "open chromatin",
        ],
        "steps": [
            {"tool": "omics.geo_search", "why": "Search GEO for ATAC-seq/ChIP-seq datasets"},
            {"tool": "omics.geo_fetch", "why": "Download peak or count data"},
            {"tool": "omics.atac_peak_annotate", "why": "Annotate peaks by genomic features"},
            {"tool": "omics.chromatin_accessibility", "why": "Differential accessibility between explicit biological groups"},
            {"tool": "omics.chipseq_enrich", "why": "Enrichment analysis of target genes"},
        ],
    },
    "omics_multiomics_integration": {
        "description": "Integrate multiple omics modalities into shared latent space",
        "trigger_phrases": [
            "multi-omics integration", "integrate RNA and ATAC", "MOFA",
            "multiomics", "combine omics modalities",
        ],
        "steps": [
            {"tool": "omics.dataset_info", "why": "Inspect each modality file"},
            {"tool": "omics.multiomics_integrate", "why": "MOFA+ integration into shared latent factors"},
        ],
    },
    "omics_spatial_analysis": {
        "description": "Analyze spatial transcriptomics data",
        "trigger_phrases": [
            "spatial transcriptomics", "Visium", "MERFISH", "spatial gene expression",
            "spatial clustering", "tissue architecture",
        ],
        "steps": [
            {"tool": "omics.cellxgene_search", "why": "Search for spatial datasets"},
            {"tool": "omics.dataset_info", "why": "Inspect spatial data structure"},
            {"tool": "omics.spatial_cluster", "why": "Spatial-aware cell clustering"},
            {"tool": "omics.spatial_autocorrelation", "why": "Identify spatially patterned genes"},
        ],
    },
}
