"""
Protein analysis tools: embedding generation, function prediction, domain annotation.

Uses ESM-2 for embeddings (optional), UniProt API for function data, and InterPro API for domains.

Split across tools/protein_embed.py (embed), tools/protein_function.py
(function_predict), and tools/protein_domains.py (domain_annotate);
re-exported here for backward compatibility. This module is the canonical
patch target for tests.
"""

from tools.http_client import request
from tools.protein_domains import domain_annotate
from tools.protein_embed import embed
from tools.protein_function import function_predict

__all__ = [
    "request",
    "embed",
    "function_predict",
    "domain_annotate",
]
