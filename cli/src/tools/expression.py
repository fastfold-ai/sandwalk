"""
Expression analysis tools: L1000 signatures, pathway enrichment, TF activity, immune scoring.

Split across tools/expression_pathway.py (pathway_enrichment), tools/expression_immune.py
(immune_score/deconvolution), tools/expression_similarity.py (l1000_similarity),
tools/expression_tf.py (tf_activity), and tools/expression_diff.py (diff_expression);
re-exported here for backward compatibility. This module is the canonical patch
target for tests (e.g. ``patch("tools.expression.pathway_enrichment")``);
submodules access this indirectly via ``from tools import expression as _expression``
so that such patches take effect regardless of which submodule performs the call.
"""

from tools.expression_diff import _resolve_groups_by_lineage, diff_expression
from tools.expression_immune import IMMUNE_MARKERS, deconvolution, immune_score
from tools.expression_pathway import _get_default_gene_sets, pathway_enrichment
from tools.expression_similarity import l1000_similarity
from tools.expression_tf import TF_REGULONS, tf_activity

__all__ = [
    "pathway_enrichment",
    "_get_default_gene_sets",
    "immune_score",
    "l1000_similarity",
    "_resolve_groups_by_lineage",
    "IMMUNE_MARKERS",
    "TF_REGULONS",
    "deconvolution",
    "tf_activity",
    "diff_expression",
]
