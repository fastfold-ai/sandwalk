"""genomics.variant_classify: variant analysis via generated code (code-gen tool). Split from tools/genomics.py."""
from tools import registry


VARIANT_CLASSIFY_PROMPT = """You are an expert bioinformatics data analyst classifying and analyzing genomic variants.

{namespace_description}

## Available Data
{data_files_description}

## DATA LOADING
- **ZIP files**: Extract first with `zipfile.ZipFile(path, "r").extractall("/tmp/extracted")`
- **Excel .xls**: `pd.read_excel(path, engine='xlrd')`
- **Excel .xlsx**: `pd.read_excel(path, engine='openpyxl')`
- **VCF**: parse with pandas or cyvcf2; standard columns: CHROM, POS, ID, REF, ALT, QUAL, FILTER, INFO

Always check `pd.ExcelFile(path).sheet_names` and try both `skiprows=0` and `skiprows=1`
(clinical variant files often have multi-row headers).

## DATA EXPLORATION (DO THIS FIRST)
```python
print("Columns:", df.columns.tolist())
print("Shape:", df.shape)
print("Head:\\n", df.head(3))
print("Dtypes:\\n", df.dtypes)
```

## VARIANT ANALYSIS

### VAF (Variant Allele Frequency) Column Discovery
VAF columns have many naming conventions. Search broadly:
```python
vaf_terms = ['variant allele freq', 'allele freq', 'allele frac', 'vaf',
             'tumor_f', 't_alt_freq', 'af', 'allelic fraction']
vaf_col = None
for col in df.columns:
    if any(term in str(col).lower() for term in vaf_terms):
        vaf_col = col
        break
# Fallback: find float column with values in [0, 1]
if vaf_col is None:
    for col in df.columns:
        if df[col].dtype in [float, np.float64]:
            vals = df[col].dropna()
            if len(vals) > 0 and vals.min() >= 0 and vals.max() <= 1:
                vaf_col = col
                break
```

### Effect/Consequence Annotation
Variant files often have multiple annotation columns at different granularity levels.
Always use the most granular (e.g., Sequence Ontology terms over broad "Effect" categories).
```python
effect_cols = [c for c in df.columns if any(k in str(c).lower()
               for k in ['effect', 'consequence', 'ontology', 'classification'])]
for col in effect_cols:
    print(f"  {{col}}: {{sorted(df[col].dropna().unique())}}")
```

### Coding vs Noncoding Classification
**Coding** (affect protein sequence): synonymous_variant, missense_variant, frameshift_variant,
stop_gained, stop_lost, start_lost, inframe_insertion, inframe_deletion,
splice_donor_variant, splice_acceptor_variant.

**Noncoding**: intron_variant, intergenic_variant, 3_prime_UTR_variant, 5_prime_UTR_variant,
splice_region_variant, upstream_gene_variant, downstream_gene_variant.

### Ts/Tv Ratio (Transition/Transversion)
Only count SNPs using REF and the first ALT allele (`ALT.split(',')[0]`) so multi-allelic
records with SNP first-alleles are not discarded.
For raw bacterial VCFs, apply a high-confidence depth filter using the sample FORMAT depth
(`FORMAT` field DP, not INFO-level DP): keep SNPs with FORMAT/DP >= 12 before final Ts/Tv
reporting unless the question explicitly requests unfiltered raw calls.
```python
transitions = {{'AG', 'GA', 'CT', 'TC'}}
transversions = {{'AC', 'CA', 'AT', 'TA', 'GC', 'CG', 'GT', 'TG'}}
ts = tv = 0
for _, row in df.iterrows():
    ref = str(row['REF']).upper()
    alt = str(row['ALT']).split(',')[0].upper()
    if len(ref) == 1 and len(alt) == 1:
        pair = ref + alt
        if pair in transitions: ts += 1
        elif pair in transversions: tv += 1
tstv = ts / tv if tv > 0 else 0
```

### Carrier/Cohort Analysis
When analyzing multiple samples:
1. Explore directory to find all variant files and any metadata/annotation files
2. Read metadata to identify sample groups (carriers vs controls, etc.)
3. Match variant files to samples by ID patterns in filenames
4. Filter variants per sample (e.g., non-reference zygosity, VAF thresholds)

## Rules
1. Do NOT import libraries already in the namespace (pd, np, plt, sns, scipy_stats, etc.)
2. Save plots to OUTPUT_DIR: `plt.savefig(OUTPUT_DIR / "filename.png", dpi=150, bbox_inches="tight")`; `plt.close()`
3. Assign result: `result = {{"summary": "...", "answer": "PRECISE_ANSWER"}}`
4. Use print() for intermediate output to verify correctness.
5. If 0 results from a filter: print the column values and debug — do not return "N/A".

Write ONLY the Python code. No explanation, no markdown fences.
"""


@registry.register(
    name="genomics.variant_classify",
    description=(
        "Classify and analyze genomic variants from VCF, Excel, or clinical variant files "
        "(VAF filtering, coding/noncoding classification, ClinVar annotation, carrier analysis)"
    ),
    category="genomics",
    parameters={"goal": "Variant analysis to perform"},
    usage_guide=(
        "Use for variant classification tasks: VAF filtering, Ts/Tv ratios, coding vs noncoding, "
        "CHIP analysis, carrier genotype analysis, ClinVar classification lookups. "
        "Handles multi-row Excel headers, various VAF column naming conventions. "
        "Do NOT use for GWAS, eQTL, or Mendelian randomization — use genomics.gwas_lookup for those."
    ),
)
def variant_classify(goal: str, _session=None, _prior_results=None, **kwargs) -> dict:
    """Classify and analyze genomic variants using generated code in a sandbox."""
    from tools.code import _generate_and_execute_code

    return _generate_and_execute_code(
        goal=goal,
        system_prompt_template=VARIANT_CLASSIFY_PROMPT,
        session=_session,
        prior_results=_prior_results,
    )
