"""
Genomics tools: GWAS lookup, eQTL analysis, variant annotation, Mendelian randomization,
colocalization, and variant classification.

These are REST/GraphQL API wrappers -- no local data required.

Split across tools/genomics_*.py sibling modules; re-exported here for backward
compatibility. This module is the canonical patch target for tests (e.g.
``patch("tools.genomics.request_json")``); submodules access shared helpers
indirectly via ``from tools import genomics as _genomics`` so that such
patches take effect regardless of which submodule performs the call.
"""

from tools.genomics_coloc import coloc
from tools.genomics_eqtl import eqtl_lookup
from tools.genomics_gwas import gwas_lookup
from tools.genomics_mr import mendelian_randomization_lookup
from tools.genomics_variant import variant_annotate
from tools.genomics_variant_classify import VARIANT_CLASSIFY_PROMPT, variant_classify
from tools.http_client import request, request_json

__all__ = [
    "request",
    "request_json",
    "gwas_lookup",
    "eqtl_lookup",
    "variant_annotate",
    "mendelian_randomization_lookup",
    "coloc",
    "variant_classify",
    "VARIANT_CLASSIFY_PROMPT",
]
