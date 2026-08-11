"""data_api: shared HTTP helpers and query normalization. Split from tools/data_api.py."""
import logging
import re

from tools.http_client import request


def _http_get(url: str, *, params=None, headers=None, timeout: int = 15, retries: int = 2):
    """GET helper with transient retry/backoff semantics."""
    import httpx

    # Preserve historical semantics where `retries` represented max attempts.
    resp, error = request(
        "GET",
        url,
        params=params,
        headers=headers,
        timeout=timeout,
        retries=max(retries - 1, 0),
        raise_for_status=False,
    )
    if error:
        raise httpx.HTTPError(error)
    return resp


def _http_post(url: str, *, json=None, data=None, params=None,
               headers=None, timeout: int = 15, retries: int = 2):
    """POST helper with transient retry/backoff semantics."""
    import httpx

    # Preserve historical semantics where `retries` represented max attempts.
    resp, error = request(
        "POST",
        url,
        json=json,
        data=data,
        params=params,
        headers=headers,
        timeout=timeout,
        retries=max(retries - 1, 0),
        raise_for_status=False,
    )
    if error:
        raise httpx.HTTPError(error)
    return resp

_logger = logging.getLogger("data_api")


def _normalize_gene_name(gene: str) -> str:
    """Normalize a gene symbol: uppercase, strip whitespace, remove common prefixes."""
    gene = gene.strip()
    # Strip common noise prefixes that confuse APIs
    for prefix in ("gene ", "Gene ", "GENE ", "human ", "Human "):
        if gene.startswith(prefix):
            gene = gene[len(prefix):]
    gene = gene.strip()
    # Gene symbols should be uppercase alphanumeric (with hyphens/dots allowed)
    # If it looks like a gene symbol, uppercase it
    if re.match(r'^[A-Za-z][A-Za-z0-9._-]*$', gene):
        gene = gene.upper()
    return gene


def _normalize_drug_query(query: str) -> str:
    """Strip noise words from drug name queries that confuse APIs."""
    noise_prefixes = [
        "fda-approved ", "fda approved ", "approved drug ",
        "drug ", "compound ", "the drug ", "the compound ",
        "investigational ", "experimental ",
    ]
    cleaned = query.strip()
    # Keep stripping prefixes (case-insensitive) until none match
    changed = True
    while changed:
        changed = False
        lower = cleaned.lower()
        for prefix in noise_prefixes:
            if lower.startswith(prefix):
                cleaned = cleaned[len(prefix):]
                changed = True
                break
    return cleaned.strip()
