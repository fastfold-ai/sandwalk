"""
Target discovery tools: neosubstrate scoring, degron prediction, co-essentiality.

Split across tools/target_essentiality.py (neosubstrate_score/coessentiality),
tools/target_degron.py (degron_predict), tools/target_druggability.py
(druggability), tools/target_expression.py (expression_profile), and
tools/target_disease.py (disease_association); re-exported here for backward
compatibility. This module is the canonical patch target for tests.
"""

from tools.http_client import request
from tools.target_degron import degron_predict
from tools.target_disease import disease_association
from tools.target_druggability import druggability
from tools.target_essentiality import coessentiality, neosubstrate_score
from tools.target_expression import expression_profile

__all__ = [
    "request",
    "neosubstrate_score",
    "coessentiality",
    "degron_predict",
    "druggability",
    "expression_profile",
    "disease_association",
]
