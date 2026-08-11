"""
Regulatory tools for CDISC delivery quality checks.

Focused on pragmatic linting of SDTM-like tabular datasets and Define-XML files.

Split across tools/regulatory_common.py (shared constants/helpers),
tools/regulatory_cdisc.py (cdisc_lint), tools/regulatory_define_xml.py
(define_xml_lint), and tools/regulatory_submission.py
(submission_package_check); re-exported here for backward compatibility.
This module is the canonical patch target for tests
(e.g. ``patch("tools.regulatory.cdisc_lint")``); submodules access
cross-cluster tools indirectly via ``from tools import regulatory as
_regulatory`` so that such patches take effect regardless of which
submodule performs the call.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from tools.regulatory_cdisc import cdisc_lint
from tools.regulatory_common import (
    _COLUMN_RE,
    _DOMAIN_REQUIRED,
    _ISO8601_PARTIAL_RE,
    _attr_by_local_name,
    _duplicate_oids,
    _extract_leaf_hrefs,
    _infer_domain_from_path,
    _issue,
    _local_name,
    _read_tabular,
    _score_quality,
)
from tools.regulatory_define_xml import define_xml_lint
from tools.regulatory_submission import submission_package_check

__all__ = [
    "re",
    "ET",
    "Path",
    "pd",
    "_COLUMN_RE",
    "_ISO8601_PARTIAL_RE",
    "_DOMAIN_REQUIRED",
    "_local_name",
    "_issue",
    "_score_quality",
    "_read_tabular",
    "_infer_domain_from_path",
    "cdisc_lint",
    "_duplicate_oids",
    "_attr_by_local_name",
    "define_xml_lint",
    "_extract_leaf_hrefs",
    "submission_package_check",
]
