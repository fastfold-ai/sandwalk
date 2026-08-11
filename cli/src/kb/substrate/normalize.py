"""Identifier normalization and coarse entity-type inference."""

from __future__ import annotations

import re

_GENE_RE = re.compile(r"^[A-Z][A-Z0-9-]{1,9}$")


def normalize_identifier(entity_type: str, value: str) -> str:
    """Normalize external identifiers into stable canonical keys."""
    et = (entity_type or "unknown").strip().lower()
    raw = (value or "").strip()
    if not raw:
        raw = "unknown"

    if et == "gene":
        norm = re.sub(r"[^A-Za-z0-9-]", "", raw).upper()
        return norm or "UNKNOWN"
    if et in {"disease", "indication", "pathway", "phenotype"}:
        norm = re.sub(r"\s+", " ", raw.lower()).strip()
        return norm or "unknown"
    if et in {"compound", "drug"}:
        norm = re.sub(r"\s+", " ", raw).strip()
        return norm
    if et in {"publication", "trial"}:
        return raw.upper()
    return re.sub(r"\s+", " ", raw).strip()


def infer_entity_type(text: str) -> str:
    """Infer coarse entity type from surface form."""
    token = (text or "").strip()
    if not token:
        return "unknown"
    if token.upper().startswith("PMID"):
        return "publication"
    if token.upper().startswith("NCT") and token[3:].isdigit():
        return "trial"
    if _GENE_RE.match(token):
        return "gene"
    if any(c.isdigit() for c in token) and "-" in token:
        return "compound"
    if len(token.split()) >= 2:
        return "disease"
    return "unknown"
