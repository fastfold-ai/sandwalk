"""
Experimental assay design tools: protocol templates, timeline estimation, and assay listing.

Provides structured experimental protocols for TPD/molecular glue validation workflows,
covering degradation, binding, viability, expression, structural, and screening assays.

Split across tools/experiment_templates.py (ASSAY_TEMPLATES catalogue) and
tools/experiment_tools.py (list_assays/design_assay/estimate_timeline);
re-exported here for backward compatibility. This module is the canonical
patch target for tests (e.g. ``from tools.experiment import ASSAY_TEMPLATES``).
"""

from __future__ import annotations

import math

from tools.experiment_templates import ASSAY_TEMPLATES
from tools.experiment_tools import design_assay, estimate_timeline, list_assays

__all__ = [
    "math",
    "ASSAY_TEMPLATES",
    "list_assays",
    "design_assay",
    "estimate_timeline",
]
