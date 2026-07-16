"""dna: Gibson and Golden Gate assembly planning tools.

Split from tools/dna.py.
"""

from __future__ import annotations

from tools import registry
from tools.dna_common import _ENZYME_MOTIFS, _gc_content, _validate_dna


@registry.register(
    name="dna.gibson_design",
    description="Suggest overlap sequences for Gibson assembly fragments",
    category="dna",
    parameters={
        "fragments": "Ordered list of DNA fragment sequences",
        "overlap_length": "Desired overlap length (default 25)",
    },
    usage_guide="Use to draft overlap strategy for multi-fragment Gibson assembly.",
)
def gibson_design(fragments: list[str], overlap_length: int = 25, **kwargs) -> dict:
    if not isinstance(fragments, list) or len(fragments) < 2:
        return {"summary": "Provide at least two fragment sequences.", "error": "invalid_fragments"}

    ov = max(15, min(60, int(overlap_length)))
    cleaned = []
    for idx, fragment in enumerate(fragments, 1):
        seq, err = _validate_dna(fragment)
        if err:
            return {"summary": f"Fragment {idx}: {err}", "error": "invalid_sequence"}
        if len(seq) < ov:
            return {"summary": f"Fragment {idx} shorter than overlap_length {ov}.", "error": "fragment_too_short"}
        cleaned.append(seq)

    joins = []
    for i in range(len(cleaned) - 1):
        left = cleaned[i][-ov:]
        right = cleaned[i + 1][:ov]
        joins.append(
            {
                "join": f"{i + 1}->{i + 2}",
                "left_tail": left,
                "right_head": right,
                "gc_percent": round((_gc_content(left) + _gc_content(right)) / 2.0, 2),
            }
        )

    return {
        "summary": f"Generated Gibson overlap plan for {len(cleaned)} fragments ({len(joins)} joins).",
        "overlap_length": ov,
        "joins": joins,
        "note": "Ensure overlaps are unique and avoid strong secondary structures.",
    }


@registry.register(
    name="dna.golden_gate_design",
    description="Suggest Golden Gate-compatible overhang plan",
    category="dna",
    parameters={
        "parts": "Ordered list of DNA part names or labels",
        "enzyme": "Type IIS enzyme (BsaI or BsmBI; default BsaI)",
    },
    usage_guide="Use to draft overhang strategy for modular Golden Gate assemblies.",
)
def golden_gate_design(parts: list[str], enzyme: str = "BsaI", **kwargs) -> dict:
    if not isinstance(parts, list) or len(parts) < 2:
        return {"summary": "Provide at least two part labels.", "error": "invalid_parts"}

    enzyme_norm = str(enzyme or "BsaI").strip()
    if enzyme_norm not in {"BsaI", "BsmBI"}:
        return {"summary": "Unsupported enzyme. Use BsaI or BsmBI.", "error": "invalid_enzyme"}

    # Simple deterministic non-palindromic overhang set.
    overhang_pool = ["AATG", "GCTT", "CGAA", "TGCC", "ACTA", "GGCT", "TTAC", "CAGG", "AGTC", "TCGA"]
    n_joins = len(parts) - 1
    if n_joins > len(overhang_pool):
        return {"summary": "Too many parts for built-in overhang pool.", "error": "too_many_parts"}

    joins = []
    for i in range(n_joins):
        joins.append(
            {
                "from_part": str(parts[i]),
                "to_part": str(parts[i + 1]),
                "overhang": overhang_pool[i],
            }
        )

    motif = _ENZYME_MOTIFS[enzyme_norm]
    return {
        "summary": f"Golden Gate plan generated for {len(parts)} parts using {enzyme_norm}.",
        "enzyme": enzyme_norm,
        "enzyme_motif": motif,
        "joins": joins,
        "note": "Validate overhang uniqueness and absence of internal Type IIS sites before synthesis.",
    }
