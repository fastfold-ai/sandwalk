"""Shared helpers for CDISC regulatory lint tools.

Split from tools/regulatory.py. Holds constants and small utilities shared by
the dataset lint, Define-XML lint, and submission-package check submodules.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

_COLUMN_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_ISO8601_PARTIAL_RE = re.compile(
    r"^\d{4}(-\d{2}){0,2}((T\d{2}(:\d{2}){0,2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?)?$"
)

_DOMAIN_REQUIRED = {
    "DM": ["SUBJID", "SEX", "RFSTDTC"],
    "AE": ["AESEQ", "AETERM", "AESTDTC"],
    "LB": ["LBSEQ", "LBTEST", "LBORRES", "LBDTC"],
    "VS": ["VSSEQ", "VSTEST", "VSORRES", "VSDTC"],
    "CM": ["CMSEQ", "CMTRT", "CMSTDTC"],
    "EX": ["EXSEQ", "EXTRT", "EXSTDTC"],
    "MH": ["MHSEQ", "MHTERM"],
}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _issue(
    issues: list[dict],
    severity: str,
    code: str,
    message: str,
    field: str | None = None,
) -> None:
    payload = {"severity": severity, "code": code, "message": message}
    if field:
        payload["field"] = field
    issues.append(payload)


def _score_quality(errors: int, warnings: int) -> int:
    return max(0, int(100 - errors * 12 - warnings * 4))


def _read_tabular(path: Path) -> tuple[pd.DataFrame | None, str | None]:
    suffix = path.suffix.lower()
    try:
        if suffix in {".csv"}:
            return pd.read_csv(path), None
        if suffix in {".tsv", ".txt"}:
            return pd.read_csv(path, sep="\t"), None
        if suffix == ".parquet":
            return pd.read_parquet(path), None
        if suffix == ".xpt":
            return pd.read_sas(path, format="xport"), None
        return None, f"Unsupported dataset format '{suffix or '<none>'}'"
    except Exception as exc:
        return None, f"Failed to read dataset: {exc}"


def _infer_domain_from_path(path: Path) -> str:
    stem = path.stem.upper()
    tokens = [t for t in re.split(r"[^A-Z0-9]+", stem) if t]
    for token in tokens:
        if token in _DOMAIN_REQUIRED:
            return token
    alpha = "".join(ch for ch in stem if ch.isalpha())
    return alpha[:2] if len(alpha) >= 2 else ""


def _duplicate_oids(elements: list[ET.Element]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for elem in elements:
        oid = str(elem.attrib.get("OID", "")).strip()
        if not oid:
            continue
        if oid in seen:
            duplicates.add(oid)
        seen.add(oid)
    return duplicates


def _attr_by_local_name(elem: ET.Element, local_name: str) -> str:
    for key, value in elem.attrib.items():
        if _local_name(key) == local_name:
            return str(value).strip()
    return ""


def _extract_leaf_hrefs(xml_path: Path) -> tuple[list[str], str | None]:
    try:
        root = ET.parse(xml_path).getroot()
    except Exception as exc:
        return [], str(exc)

    hrefs = []
    for leaf in [x for x in root.iter() if _local_name(x.tag).lower() == "leaf"]:
        href = _attr_by_local_name(leaf, "href")
        if href:
            hrefs.append(href.strip())
    return hrefs, None
