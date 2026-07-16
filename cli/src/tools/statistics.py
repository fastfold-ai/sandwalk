"""Statistical analysis tools: survival, dose-response, biomarker panels.

Split across tools/statistics_dose_response.py (dose_response_fit),
tools/statistics_survival.py (survival_analysis), and
tools/statistics_enrichment.py (enrichment_test/_get_hallmark_sets);
re-exported here for backward compatibility. This module is the canonical
patch target for tests (e.g. ``from tools.statistics import dose_response_fit``).
"""

import numpy as np

from tools.statistics_dose_response import dose_response_fit
from tools.statistics_enrichment import _get_hallmark_sets, enrichment_test
from tools.statistics_survival import survival_analysis

__all__ = [
    "np",
    "dose_response_fit",
    "survival_analysis",
    "enrichment_test",
    "_get_hallmark_sets",
]
