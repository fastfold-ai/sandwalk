"""Shared helpers for clean-room parity tools.

Split from tools/parity.py. Holds small utilities used across the parity
submodules (response clipping, int coercion, hit-list flattening, and
MyGene.info species normalization).
"""

from __future__ import annotations

import re


def _clip(value, n: int = 240) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= n:
        return text
    return text[: n - 3] + "..."


def _coerce_int(value, default: int, minimum: int = 1, maximum: int = 100) -> int:
    try:
        out = int(value)
    except Exception:
        out = default
    return min(max(out, minimum), maximum)


def _flatten_hits(payload, key: str = "hits") -> list[dict]:
    hits = payload.get(key, []) if isinstance(payload, dict) else []
    if isinstance(hits, dict):
        # my* APIs sometimes return dict hits keyed by ids
        hits = list(hits.values())
    return [h for h in hits if isinstance(h, dict)]


_MYGENE_SPECIES_MAP = {
    "human": "human",
    "mouse": "mouse",
    "rat": "rat",
    "zebrafish": "zebrafish",
    "drosophila": "fly",
    "yeast": "yeast",
    "schistosoma mansoni": "6183",
    "fasciola hepatica": "6192",
    "heligmosomoides polygyrus": "6337",
    "nippostrongylus brasiliensis": "27835",
    "trichuris muris": "70415",
    "brugia malayi": "6279",
}


def _normalize_mygene_species(species: str) -> str:
    s = (species or "human").strip().lower()
    if not s:
        return "human"
    if s.isdigit():
        return s
    if s in _MYGENE_SPECIES_MAP:
        return _MYGENE_SPECIES_MAP[s]

    # Extract likely binomial species from noisy planner text.
    m = re.search(r"([A-Za-z][a-z]+)\s+([a-z][a-z]+)", s)
    if m:
        candidate = f"{m.group(1)} {m.group(2)}".lower()
        if candidate in _MYGENE_SPECIES_MAP:
            return _MYGENE_SPECIES_MAP[candidate]

    # Fallback to original value; caller can still get API errors surfaced.
    return species
