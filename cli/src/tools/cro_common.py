"""Shared CRO database loading and scoring helpers.

PLACEHOLDER IMPLEMENTATION: CRO data comes from a static bundled JSON file,
not a live database. See tools/cro.py for details.
"""

import json
from pathlib import Path

_cro_db_cache = None


def _load_cro_db() -> list[dict]:
    """Load and cache the CRO database from JSON."""
    global _cro_db_cache
    if _cro_db_cache is not None:
        return _cro_db_cache
    db_path = Path(__file__).parent.parent / "data" / "cro_database.json"
    with open(db_path) as f:
        _cro_db_cache = json.load(f)
    return _cro_db_cache


def _score_cro(cro: dict, assay_type: str, target: str | None,
               compound: str | None, species: str, scale: str) -> float:
    """Score a CRO for a specific experiment.

    Weights:
      - service match:       0.4
      - capability match:    0.3
      - therapeutic area:    0.2
      - specialty match:     0.1
    """
    score = 0.0

    # Service category match (0.4)
    service_cats = [s["category"] for s in cro.get("services", [])]
    if assay_type in service_cats:
        score += 0.4
    else:
        # Partial match: check if assay_type words appear in any category
        assay_words = set(assay_type.lower().replace("_", " ").split())
        for cat in service_cats:
            cat_words = set(cat.lower().replace("_", " ").split())
            if assay_words & cat_words:
                score += 0.2
                break

    # Capability match (0.3)
    capabilities_text = " ".join(cro.get("capabilities", [])).lower()
    keywords = []
    if assay_type:
        keywords.extend(assay_type.lower().replace("_", " ").split())
    if target:
        keywords.append(target.lower())
    if compound:
        keywords.append(compound.lower())
    # Add TPD-relevant keywords
    tpd_keywords = ["degradation", "protac", "molecular glue", "tpd",
                     "ubiquitin", "e3 ligase", "ternary", "neo-substrate"]
    for kw in keywords:
        if kw in capabilities_text:
            score += 0.15
            break
    for kw in tpd_keywords:
        if kw in capabilities_text:
            score += 0.15
            break

    # Therapeutic area match (0.2) — oncology is default for TPD
    therapeutic_areas = [t.lower() for t in cro.get("therapeutic_areas", [])]
    if "oncology" in therapeutic_areas:
        score += 0.2

    # Specialty match (0.1)
    specialties_text = " ".join(cro.get("specialties", [])).lower()
    specialty_keywords = keywords + ["degradation", "tpd", "protac", "molecular glue"]
    for kw in specialty_keywords:
        if kw in specialties_text:
            score += 0.1
            break

    # Scale bonus: large CROs score slightly higher for large-scale work
    if scale == "large" and cro.get("size") == "large":
        score += 0.05
    elif scale == "small" and cro.get("size") in ("small", "medium"):
        score += 0.05

    return round(min(score, 1.0), 3)
