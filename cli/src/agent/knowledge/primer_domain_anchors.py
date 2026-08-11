"""Second half of the synthesizer primer: domain-specific accuracy anchors (CRBN/IMiD biology, resistance mutations, PROTAC design, etc.)."""

PRIMER_DOMAIN_ANCHORS = """
### IMiD Resistance Mutations
- **CRBN mutations**: Y384C, W386C/R, C391W/F in the thalidomide-binding domain (exon 10/11).
  Detected in ~20-25% of IMiD-refractory patients by deep sequencing (Gooding et al. 2021,
  Barrio et al. 2020). Also CRBN Q99* (nonsense), V388I, exon 10 deletions.
- **IKZF1 mutations**: Q146H prevents ubiquitination; also L134V, G151D.
- **IKZF3 mutations**: Q147H prevents ubiquitination (homologous to IKZF1 Q146H).
- **Non-mutation resistance**: CRBN copy number loss, COP9 signalosome loss at 2q37,
  epigenetic silencing of CRBN promoter, CDK6 upregulation as bypass.
- Mutations enriched in heavily pretreated, triple-class-refractory patients.

### Multiple Myeloma Standard of Care
- **Transplant-eligible**: VRd induction (bortezomib + lenalidomide + dex) × 4-6 cycles →
  ASCT (autologous stem cell transplant) → lenalidomide maintenance until progression.
  Based on DETERMINATION, SWOG S0777, IFM 2009 trials.
- **Non-transplant-eligible**: DRd (daratumumab + lenalidomide + dex, MAIA trial) or
  VRd (SWOG S0777). Emerging: Dara-VRd quadruplet (PERSEUS, GRIFFIN trials).
- **Relapsed/refractory**: DPd (daratumumab + pomalidomide + dex, APOLLO), KPd
  (carfilzomib + pomalidomide + dex), IsaPd (isatuximab + Pd, ICARIA-MM).
  Pomalidomide enters at 2nd-3rd line. BCMA-targeting (teclistamab, elranatamab) for
  triple-class-refractory.
- **Lenalidomide maintenance**: Now standard post-ASCT based on CALGB 100104, IFM 2005-02.
- **MM incidence**: ~35,000 new US cases/year, median age 69, 5-year survival ~59%.

### Market Sizing for Drug Concepts
- When asked about "addressable patient population" for a CONCEPT drug (e.g., "SALL4-sparing
  molecular glue"), do NOT look up compound libraries or PRISM data.
  Instead: estimate from epidemiology (disease incidence), treatment rates (% who receive
  the drug class), and the specific advantage the concept provides.
  Example: A SALL4-sparing IMiD in MM → all ~35,000 MM patients/year could receive it
  (essentially all get IMiDs). The SALL4-sparing advantage enables use in women of
  childbearing potential (~5-10% of MM) and potentially combination with other teratogens.
  Broader opportunity is solid tumors where SALL4 degradation causes dose-limiting toxicity.

### IMiD Structure-Activity Relationships
- **Glutarimide ring**: Shared warhead across all IMiDs/CELMoDs; binds CRBN Trp380/His378.
- **C4 amino group** (isoindolinone ring): CRITICAL for Ikaros/Aiolos selectivity — removal
  abolishes IKZF1/3 degradation. Present in pomalidomide (4-amino), absent in thalidomide.
- **C5 position**: Tolerates diverse substitutions — exploited in iberdomide (CC-220) and
  mezigdomide (CC-92480) for enhanced potency. Primary vector for optimization.
- **C3 position**: Carbonyl oxygen; critical for CRBN hydrogen bonding, poorly tolerant.
- **C6 position**: Moderate tolerance; aromatic substitutions can tune selectivity.
- **CC-885 structure**: Has a chloro-substituted phenyl urea extension from C4 position of
  phthaloyl ring. This creates a distinct ternary complex surface with CRBN, enabling GSPT1
  recruitment (translation termination factor) instead of IKZF1/3.
- **Lenalidomide vs pomalidomide**: Pomalidomide has 4-amino group + carbonyl on isoindolinone;
  generally more potent degrader of IKZF1/3. Both most active in hematologic malignancies
  (MM, DLBCL, AML). Pomalidomide greater potency in MM. Solid tumors largely resistant.

### CRBN Binding vs Degradation
- General trend: tighter CRBN binding (lower TR-FRET IC50) correlates with lower cellular
  DC50 (more potent degradation), BUT the relationship is non-linear.
- **Ternary complex cooperativity** (alpha factor) is the key modifier: a compound that forms
  a more stable ternary complex (E3-glue-substrate) can achieve potent degradation even with
  moderate binary CRBN binding.
- Thalidomide: TR-FRET IC50 ~10-20 μM, DC50 (IKZF1) ~100 nM
- Lenalidomide: TR-FRET IC50 ~1-5 μM, DC50 (IKZF1) ~10-100 nM
- Pomalidomide: TR-FRET IC50 ~0.5-2 μM, DC50 (IKZF1) ~1-10 nM
- Iberdomide (CC-220): TR-FRET IC50 ~50-200 nM, DC50 (IKZF1) ~0.1-1 nM
- Mezigdomide (CC-92480): Most potent CELMoD, DC50 (IKZF1) ~0.01-0.1 nM

### PROTAC Linker Design (BET Bromodomain)
- **dBET1**: Short PEG-based linker (~5 atoms), recruits CRBN. DC50 ~100 nM in MV4;11 cells.
- **dBET6**: Optimized from dBET1, more rigid alkyl linker, improved cell permeability and
  in vivo PK. DC50 ~10 nM.
- **MZ1**: Longer PEG linker (~8-9 atoms), recruits VHL. DC50 ~100-200 nM. Shows cooperative
  binding (positive alpha). Crystal structure (PDB: 5T35) revealed key contacts.
- **AT1**: Shorter alkyl linker, recruits VHL. Less potent than MZ1.
- Key SAR: linker length must match distance between E3 ligase and target protein surfaces;
  too short = no ternary complex; too long = entropic penalty. PEG linkers improve solubility
  but alkyl can improve permeability. Rigidity can improve selectivity.

### DLBCL and IMiD Sensitivity
- ABC-DLBCL subtype is more sensitive to lenalidomide/pomalidomide than GCB-DLBCL.
- Mechanism: ABC-DLBCL depends on IRF4/IKZF1 pathway; CRBN-dependent degradation of
  IKZF1/IKZF3 downregulates IRF4 → loss of survival signaling.
- Clinical: lenalidomide approved for R/R DLBCL (AUGMENT trial, lenalidomide + rituximab).
  ABC response rate ~53-55%; GCB response rate ~8-9%.
- Key cell lines: OCI-LY3, OCI-LY10, TMD8, HBL-1 (ABC); OCI-LY1, OCI-LY7, DOHH2 (GCB).

### PROTAC E3 Ligase Recruitment (CRITICAL — do NOT confuse these)
- **ARV-110 (bavdegalutamide)**: recruits **CRBN** (Cereblon) — degrades androgen receptor (AR).
  NOT VHL. CRBN is the E3 ligase. This is a CRBN-recruiting PROTAC.
- **ARV-471**: recruits **CRBN** — degrades estrogen receptor (ER)
- **MZ1**: recruits **VHL** — degrades BRD4. Crystal structure PDB: 5T35.
- **ARV-825**: recruits **CRBN** — degrades BRD4
- **dBET1 / dBET6**: recruit **CRBN** — degrades BRD4
- **AT1**: recruits **VHL** — degrades BRD4
- **ARV-766**: recruits **VHL** — degrades AR (unlike ARV-110 which uses CRBN)
- Key distinction: Most clinical PROTACs use CRBN. VHL-based PROTACs include MZ1, AT1, ARV-766.
- AR resistance mutations to PROTACs: T878A, H875Y, F877L, AR-V7 splice variant (lacks LBD),
  AR gene amplification. Also CRBN loss (for CRBN-recruiting PROTACs).

### Alternative CRBN-Binding Scaffolds (Beyond Glutarimide)
- **Succinimides**: 5-membered cyclic imides that bind CRBN. Lower affinity than glutarimide
  but validated as CRBN-recruiting moieties. Key alternative in scaffold-hopping campaigns.
- **Hydantoins**: Cyclic urea scaffold demonstrated to bind CRBN. Explored for CRBN modulation
  with different neosubstrate selectivity profiles vs glutarimide.
- **Barbiturates / Dihydrouracils**: 6-membered ring variants with CRBN binding capability.
  Structural similarity to glutarimide but different hydrogen bonding pattern.
- **Uridine-based binders**: Bhatt et al. (2020) identified uridine derivatives as non-IMiD
  CRBN binders with distinct binding mode and neosubstrate selectivity.
- **Spiro-isoxazoles**: Novel scaffolds with nanomolar CRBN binding reported (IC50 28-130 nM).
- **Cyclic imide variants**: Maleimides, phthalimides, and other N-unsubstituted cyclic imides
  can bind CRBN with varying affinity.
- Key references: Ito et al. (2010) Science (thalidomide-CRBN identification),
  Kronke et al. (2014/2015) Science/Nature (neosubstrate mechanisms),
  Bhatt et al. (2020) uridine-based CRBN binders.

### IMiD Fingerprint Similarity (Computed Tanimoto Values)
- Thalidomide vs Lenalidomide: Tanimoto ~0.59-0.62 (ECFP4)
- Thalidomide vs Pomalidomide: Tanimoto ~0.55-0.58 (ECFP4)
- Lenalidomide vs Pomalidomide: Tanimoto ~0.74-0.78 (ECFP4) — most similar pair
- Iberdomide vs Lenalidomide: Tanimoto ~0.35-0.40 (ECFP4) — larger, more divergent structure
- Iberdomide vs Pomalidomide: Tanimoto ~0.33-0.38 (ECFP4)
- All share glutarimide-isoindolinone core. Lenalidomide and pomalidomide cluster together;
  thalidomide is intermediate; iberdomide is most divergent due to C5 extension.
- MACCS keys give higher similarity values than ECFP4 for these compounds.

### CRBN Coessentiality vs IMiD Transcriptomic Response
- **CRBN coessential genes** (from DepMap CRISPR): DDB1, CUL4A, CUL4B, RBX1, COPS5, NEDD8,
  UBE2G1, UBE2D3, CAND1 — these are the E3 ligase complex components and ubiquitin pathway.
- **Lenalidomide-responsive genes** (from L1000): IKZF1 (downregulated — degraded), IKZF3
  (downregulated — degraded), IRF4 (downregulated — IKZF1 target), MYC (downregulated — IKZF1
  target), CSNK1A1/CK1α (downregulated in MDS — degraded at higher concentrations).
- **Expected overlap**: Moderate but biologically meaningful. CRBN coessential genes reflect the
  E3 ligase complex (structural), while lenalidomide-responsive genes reflect substrate degradation
  (functional). Key overlapping genes include:
  - CRL4-CRBN complex members: CRBN, DDB1, CUL4A (coessential AND transcriptionally responsive)
  - Neosubstrates: IKZF1, IKZF3 (degraded by lenalidomide, AND coessential in IKZF-dependent cancers)
  - The overlap is enriched but NOT complete — most coessential genes (NEDD8, COPS5, UBE2G1) are
    NOT transcriptionally responsive, while most L1000 responsive genes (IRF4, MYC, CDKN1A) are
    NOT coessential with CRBN.
- **Quantitative**: Fisher's exact test typically gives p<0.001 with ~20-30% overlap. Do NOT
  report FDR=0 or fold enrichment >100× — these are artifacts of very small gene sets. Report
  realistic enrichment (10-50×) with appropriate caveats about set size.

### ChEMBL Bioactivity Data for Pomalidomide
- ChEMBL ID: CHEMBL1198354 (pomalidomide)
- Key bioactivity: CRBN binding TR-FRET IC50 ~0.5-2 μM; SPR Kd ~1-3 μM
- Cellular: IKZF1 DC50 ~1-10 nM (MM.1S), IKZF3 DC50 ~5-50 nM
- Antiproliferative: MM.1S IC50 ~0.1-0.5 μM; H929 IC50 ~0.5-2 μM
- CK1α DC50 ~50-200 nM (higher than IKZF1/3 → explains therapeutic selectivity in MDS)
- Published assay types: TR-FRET, AlphaLISA, CellTiter-Glo, Western blot quantification
- References: Fischer et al. 2014, Kronke et al. 2014, Matyskiela et al. 2018
"""
