"""
Safety profiling tools: anti-target screening, multi-modal safety classification, SALL4 risk,
FAERS pharmacovigilance, ADMET prediction, and drug-drug interaction prediction.

References crews-glue-discovery/analysis/safety_profile.md for classification logic
and anti-target lists.

Split across tools/safety_common.py (UniProt/gene mappings), tools/safety_antitarget.py
(antitarget_profile/classify/sall4_risk), tools/safety_faers.py (FAERS/label pharmacovigilance),
tools/safety_admet.py (admet_predict), and tools/safety_ddi.py (ddi_predict); re-exported here
for backward compatibility. This module is the canonical patch target for tests
(e.g. ``patch("tools.safety.request_json")``); submodules that call ``request_json``
access it indirectly via ``from tools import safety as _safety`` so that such patches
take effect regardless of which submodule performs the call.
"""

from tools.http_client import request_json
from tools.safety_admet import admet_predict
from tools.safety_antitarget import antitarget_profile, classify, sall4_risk
from tools.safety_common import (
    CRBN_SUBSTRATES,
    GENE_TO_UNIPROT,
    HEME_TFS,
    TERATOGENIC_SUBSTRATES,
    TUMOR_SUPPRESSORS,
    UNIPROT_TO_GENE,
    _display_name,
    _gene_ids,
)
from tools.safety_ddi import ddi_predict
from tools.safety_faers import (
    _OPENFDA_DRUG_EVENT_URL,
    _OPENFDA_DRUG_LABEL_URL,
    _faers_signal_metrics,
    _openfda_escape,
    _openfda_total,
    faers_signal_scan,
    label_risk_extract,
)

__all__ = [
    "request_json",
    "UNIPROT_TO_GENE",
    "GENE_TO_UNIPROT",
    "TUMOR_SUPPRESSORS",
    "HEME_TFS",
    "TERATOGENIC_SUBSTRATES",
    "CRBN_SUBSTRATES",
    "_gene_ids",
    "_display_name",
    "antitarget_profile",
    "classify",
    "sall4_risk",
    "_OPENFDA_DRUG_EVENT_URL",
    "_OPENFDA_DRUG_LABEL_URL",
    "_openfda_escape",
    "_openfda_total",
    "_faers_signal_metrics",
    "faers_signal_scan",
    "label_risk_extract",
    "admet_predict",
    "ddi_predict",
]
