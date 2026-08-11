"""
Combination therapy tools: synergy prediction, synthetic lethality, metabolic vulnerability.

References crews-glue-discovery/scripts/synergy_prediction.py and metabolic_vulnerability.py
for scoring logic.

Split across combination_synergy.py, combination_lethality.py, and
combination_metabolic.py (+ combination_metabolic_data.py); re-exported
here for backward compatibility.
"""

from tools.combination_lethality import synthetic_lethality
from tools.combination_metabolic import metabolic_vulnerability
from tools.combination_metabolic_data import METABOLIC_INHIBITORS, METABOLIC_PATHWAYS
from tools.combination_synergy import synergy_predict

__all__ = [
    "synergy_predict",
    "synthetic_lethality",
    "metabolic_vulnerability",
    "METABOLIC_PATHWAYS",
    "METABOLIC_INHIBITORS",
]
