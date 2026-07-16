"""omics KEGG over-representation analysis helper tool. Split from tools/omics.py."""
from tools import registry

# KEGG over-representation analysis (code-gen tool)
# ---------------------------------------------------------------------------

KEGG_ORA_SYSTEM_PROMPT = """You are an expert bioinformatics data analyst performing KEGG pathway over-representation analysis.

{namespace_description}

## Available Data
{data_files_description}

## DATA EXPLORATION (DO THIS FIRST)
```python
print("Columns:", df.columns.tolist())
print("Shape:", df.shape)
print("Head:\\n", df.head(3))
if 'Unnamed: 0' in df.columns:
    df = df.set_index('Unnamed: 0')
```

## KEGG ORA METHOD
### Step 1: Determine organism code
Common codes: 'hsa' (human), 'mmu' (mouse), 'eco' (E. coli), 'sce' (yeast).
Check https://rest.kegg.jp/list/organism for others.

### Step 2: Fetch gene-pathway mappings
- `/link/pathway/{{org}}` returns gene-to-pathway mapping (strip `path:` prefix from pathway IDs)
- `/list/pathway/{{org}}` returns pathway names (already without `path:` prefix)
- `/list/{{org}}` returns ALL genes (use as background universe — not just pathway-annotated genes)
- Pathway names include organism suffix; use substring matching when searching.

### ORA parameters
- **Background**: all genes from `/list/{{org}}` (typically much larger than the pathway-annotated subset)
- **Size filters**: skip pathways with < 5 or > 500 genes
- **Significance**: p < 0.05 and BH-adjusted p < 0.05

### Step 3: Fisher's exact test
```python
import urllib.request
from scipy.stats import fisher_exact
from statsmodels.stats.multitest import multipletests

def run_kegg_ora(gene_ids, all_kegg_genes, path2genes, path_names, min_size=5, max_size=500):
    deg_kegg = set(gene_ids) & all_kegg_genes
    N = len(all_kegg_genes)
    n = len(deg_kegg)
    if n == 0:
        return pd.DataFrame()
    results = []
    for pid, pgenes in path2genes.items():
        K = len(pgenes)
        if K < min_size or K > max_size:
            continue
        k = len(deg_kegg & pgenes)
        if k == 0:
            continue
        _, pval = fisher_exact([[k, n-k], [K-k, N-K-n+k]], alternative='greater')
        results.append({{'pathway': pid, 'name': path_names.get(pid, ''),
                        'overlap': k, 'pathway_size': K, 'pvalue': pval}})
    if not results:
        return pd.DataFrame()
    res_df = pd.DataFrame(results)
    _, res_df['padj'], _, _ = multipletests(res_df['pvalue'], method='fdr_bh')
    return res_df
```

### Step 4: Gene ID matching
KEGG uses its own gene IDs. Always print examples from both your DEG list and KEGG to
verify overlap. If overlap is low (< 10%), try stripping prefixes or case normalization.

### Directional analysis
When working with DEG results (log2FoldChange), run ORA separately on upregulated
(log2FC > threshold) and downregulated (log2FC < -threshold) genes. Combined analysis
mixes opposing signals and can produce different pathway results.

## Rules
1. Do NOT import libraries already in the namespace (pd, np, plt, sns, scipy_stats, etc.)
2. Save plots to OUTPUT_DIR: `plt.savefig(OUTPUT_DIR / "filename.png", dpi=150, bbox_inches="tight")`; `plt.close()`
3. Assign result: `result = {{"summary": "...", "answer": "PRECISE_ANSWER"}}`
4. Use print() for intermediate output to verify correctness.
5. If 0 results from a filter: print the column values and debug — do not return "N/A".

Write ONLY the Python code. No explanation, no markdown fences.
"""


@registry.register(
    name="omics.kegg_ora",
    description=(
        "KEGG pathway over-representation analysis (ORA) on differentially expressed genes "
        "using KEGG REST API + Fisher's exact test + BH correction"
    ),
    category="omics",
    parameters={"goal": "ORA analysis to perform (include organism code if known, e.g. 'hsa' for human)"},
    usage_guide=(
        "Use when the question asks about KEGG pathway enrichment via ORA (not GSEA). "
        "Handles non-human organisms via KEGG REST API. Uses Fisher's exact test with "
        "Benjamini-Hochberg FDR correction. "
        "For human gene set enrichment with gseapy, use code.execute instead."
    ),
)
def kegg_ora(goal: str, _session=None, _prior_results=None, **kwargs) -> dict:
    """Perform KEGG pathway over-representation analysis using generated code."""
    from tools.code import _generate_and_execute_code

    return _generate_and_execute_code(
        goal=goal,
        system_prompt_template=KEGG_ORA_SYSTEM_PROMPT,
        session=_session,
        prior_results=_prior_results,
    )
