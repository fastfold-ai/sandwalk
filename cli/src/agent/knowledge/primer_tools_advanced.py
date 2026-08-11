"""Second half of the domain-knowledge tool primer (single-cell onward) plus cross-disciplinary thinking patterns and the closing key-principle section."""

PRIMER_TOOLS_ADVANCED = """### Single-Cell & Spatial
- **singlecell**: cluster (Leiden/Louvain), trajectory (pseudotime), cell_type_annotate (marker-based)
- USE WHEN: "Cluster these cells", "Trajectory analysis", "Annotate cell types"

### Imaging & Compound Profiling
- **imaging**: cellpainting_lookup (PubChem bioactivity + RDKit mechanism class), morphology_similarity (structural fingerprint similarity as phenotypic proxy)
- USE WHEN: "Compound bioactivity profile?", "Structural similarity?", "Mechanism class?"

### Literature & Patents
- **literature**: pubmed_search, chembl_query, openalex_search, patent_search, preprint_search
- USE WHEN: "Recent publications?", "Known bioactivity?", "Patent landscape?"

### Platform Data APIs
- **data_api**: depmap_search, opentargets_search, uniprot_lookup, pdb_search, ensembl_lookup, ncbi_gene, chembl_advanced, drug_info, mygene_lookup, mydisease_lookup, myvariant_lookup, mytaxon_lookup, mychem_lookup, pdbe_search, reactome_pathway_search
- USE WHEN: You need rich, detailed data from a specific platform beyond what specialized tools provide

### DNA Biology & Cloning
- **dna**: reverse_complement, translate, find_orfs, codon_optimize, restriction_sites, virtual_digest, primer_design, pcr_protocol, gibson_design, golden_gate_design
- USE WHEN: sequence design, cloning strategy, primer planning, codon optimization, and construct sanity checks.

### Experimental Design & CRO
- **experiment**: design_assay, estimate_timeline, list_assays (12 assay templates)
- **cro**: search, match_experiment, compare, draft_inquiry, send_inquiry (from built-in CRO directory)
- USE WHEN: "Design an experiment", "Find a CRO", "Cost estimate?"
- WARNING: cro.* is placeholder/static directory data and may be disabled in production planner runs.

### Compute & Infrastructure
- **compute**: list_providers, estimate_cost (from built-in reference pricing), submit_job, job_status
- WARNING: compute.* tools are reference-only and disabled for GPU inference. Do NOT use them for protein folding.
- For protein structure prediction, use the **fold skill** (FastFold Cloud API) instead — see Structure section above.

### Utility
- **claude**: reason, compare, summarize (LLM reasoning for complex questions)
- USE claude.reason WHEN: you need to synthesize or reason about information from multiple prior steps
- IMPORTANT: code.execute, files.*, and shell.* are NOT available. Use only pre-built research tools.

### Research Ops & Workflow Memory
- **ops**: notebook_add, notebook_search, todo_add, todo_list, workflow_save
- USE WHEN: capturing decisions, tracking follow-up actions, and preserving reusable plan templates.
- THINK: after each substantive run, log key findings, add actionable todos, and save successful plan patterns.

### Omics Data Discovery & Analysis
- **omics** (discovery): geo_search, geo_fetch, cellxgene_search, cellxgene_fetch, tcga_search, tcga_fetch, dataset_info
- **omics** (methylation): methylation_diff, methylation_profile, methylation_cluster
- **omics** (proteomics): proteomics_diff, proteomics_enrich
- **omics** (epigenomics): atac_peak_annotate, chromatin_accessibility, chipseq_enrich
- **omics** (spatial): spatial_cluster, spatial_autocorrelation
- **omics** (cytometry): cytof_cluster
- **omics** (3D genome): hic_compartments
- **omics** (bulk DE): deseq2 (proper negative binomial, falls back to Mann-Whitney)
- **omics** (multi-omics): multiomics_integrate (MOFA+ via muon)
- USE WHEN: user mentions scRNA-seq, single-cell, bulk RNA-seq, GEO, CELLxGENE, TCGA, methylation, ATAC-seq, ChIP-seq, proteomics, spatial transcriptomics, CyTOF, flow cytometry, Hi-C, "find dataset", "download data", "analyze expression data"
- IMPORTANT: Differential tools require explicit group labels/metadata for reliable inference:
  - omics.deseq2: provide metadata_path with a condition column (infer_metadata only for quick exploration)
  - omics.methylation_diff / omics.proteomics_diff / omics.chromatin_accessibility: provide explicit group1/group2 sample lists
- THINK: data discovery → download → inspect → modality-specific analysis
  1. omics.geo_search / omics.cellxgene_search / omics.tcga_search — find relevant datasets
  2. omics.geo_fetch / omics.cellxgene_fetch / omics.tcga_fetch — download to local
  3. omics.dataset_info — inspect the downloaded file (shape, metadata)
  4. Route to modality-specific tools:
     - scRNA-seq: singlecell.cluster → singlecell.cell_type_annotate → expression.pathway_enrichment
     - Methylation: omics.methylation_profile → omics.methylation_diff → omics.methylation_cluster
     - Proteomics: omics.proteomics_diff → omics.proteomics_enrich
     - Bulk RNA-seq DE: omics.deseq2 (preferred, uses pyDESeq2 negative binomial model)
     - Multi-omics: omics.multiomics_integrate (MOFA+ via muon, needs ≥2 h5ad modalities)
     - ATAC-seq: omics.atac_peak_annotate → omics.chromatin_accessibility
     - ChIP-seq: omics.chipseq_enrich
     - Spatial: omics.spatial_cluster → omics.spatial_autocorrelation
     - CyTOF/flow: omics.cytof_cluster
     - Hi-C: omics.hic_compartments
     - Bulk RNA-seq: omics.deseq2 (preferred) or expression.diff_expression or code.execute
- KEY INSIGHT: Always search + inspect before analysis. Large datasets may exceed download limits.
- For bulk RNA-seq count data, prefer omics.deseq2 over Mann-Whitney — it uses the proper negative binomial model.
- For multi-omics integration (RNA + ATAC, RNA + protein), use omics.multiomics_integrate with MOFA+.
- For methylation clustering, use omics.methylation_cluster (episcanpy-aware, sklearn fallback).

## Cross-Disciplinary Thinking Patterns

When a user asks about a **target**:
1. Genetic validation: GWAS → eQTL → MR → coloc (causal evidence chain)
2. Functional validation: coessentiality → PPI network → pathway context
3. Expression: tissue expression profile → single-cell → disease vs normal
4. Druggability: protein class → binding sites → known drugs (ChEMBL) → clinical trials
5. Safety: what happens if you modulate it? Essential gene? Tumor suppressor?
6. Commercial: competitive landscape → patent search → population size

When a user asks about a **compound**:
1. Identity: PubChem lookup → ChEMBL → DrugBank → structural properties
2. Mechanism: L1000 signature → pathway enrichment → TF activity → CMap connectivity
3. Optimization: SAR → MMP → scaffold hopping → pharmacophore → design suggestions
4. Safety: ADMET → antitarget → DDI → SALL4 → classify
5. Translatability: dose-response → indication map → biomarkers → clinical trials
6. Synthesis: retrosynthesis → CRO engagement

When a user asks about a **disease/indication**:
1. Target landscape: Open Targets → GWAS → expression → essentiality
2. Existing therapies: clinical trials → competitive landscape → DrugBank
3. Unmet need: population size → standard of care → biomarkers
4. Opportunities: repurposing → combination therapy → novel targets
5. Patient selection: mutation sensitivity → TCGA stratification → biomarker panels

When a user asks about **data or results**:
1. Statistical rigor: enrichment tests → survival analysis → dose-response fitting
2. Validation: orthogonal evidence from different data types
3. Confounders: lineage effects, batch effects, sample size
4. Translatability: in vitro → in vivo → clinical relevance

## Key Principle

Always think about what the researcher should do NEXT. After every analysis, consider:
- What's the most impactful follow-up? (not just the obvious one)
- Is there orthogonal evidence that could strengthen or challenge the finding?
- What would a drug discovery team discuss in their next meeting?
- Are there risks or red flags that need immediate attention?
- What data is missing that could change the conclusion?
"""
