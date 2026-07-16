"""dna: restriction analysis, virtual digest, primer design, and PCR protocol tools.

Split from tools/dna.py.
"""

from __future__ import annotations

from tools import registry
from tools.dna_common import (
    _ENZYME_MOTIFS,
    _find_sites,
    _pick_primer_candidates,
    _reverse_complement,
    _validate_dna,
)


@registry.register(
    name="dna.restriction_sites",
    description="Find common restriction enzyme sites in a DNA sequence",
    category="dna",
    parameters={
        "sequence": "DNA sequence",
        "enzymes": "Optional list or comma-separated enzyme names",
    },
    usage_guide="Use to choose cloning strategy and verify unwanted cut sites.",
)
def restriction_sites(sequence: str, enzymes: list[str] | str | None = None, **kwargs) -> dict:
    seq, err = _validate_dna(sequence)
    if err:
        return {"summary": err, "error": "invalid_sequence"}

    if enzymes is None:
        selected = list(_ENZYME_MOTIFS.keys())
    elif isinstance(enzymes, str):
        selected = [x.strip() for x in enzymes.split(",") if x.strip()]
    else:
        selected = [str(x).strip() for x in enzymes if str(x).strip()]

    unknown = [e for e in selected if e not in _ENZYME_MOTIFS]
    if unknown:
        return {
            "summary": f"Unknown enzymes: {', '.join(unknown)}",
            "error": "invalid_enzyme",
            "available_enzymes": sorted(_ENZYME_MOTIFS.keys()),
        }

    matches = []
    for enzyme in selected:
        motif = _ENZYME_MOTIFS[enzyme]
        positions = _find_sites(seq, motif)
        matches.append(
            {
                "enzyme": enzyme,
                "motif": motif,
                "n_sites": len(positions),
                "positions": positions,
            }
        )

    total = sum(m["n_sites"] for m in matches)
    return {
        "summary": f"Restriction scan complete: {total} total sites across {len(selected)} enzymes.",
        "sequence_length": len(seq),
        "results": matches,
    }


@registry.register(
    name="dna.virtual_digest",
    description="Perform an in-silico digest and return fragment sizes",
    category="dna",
    parameters={
        "sequence": "DNA sequence",
        "enzymes": "List or comma-separated enzymes (supported: EcoRI,BamHI,HindIII,NotI,XhoI,NheI,BsaI,BsmBI)",
        "circular": "Treat sequence as circular (default false)",
    },
    usage_guide="Use to predict gel band patterns before running wet-lab digests.",
)
def virtual_digest(sequence: str, enzymes: list[str] | str, circular: bool = False, **kwargs) -> dict:
    seq, err = _validate_dna(sequence)
    if err:
        return {"summary": err, "error": "invalid_sequence"}

    site_result = restriction_sites(seq, enzymes=enzymes)
    if site_result.get("error"):
        return site_result

    cut_positions = sorted({p for item in site_result["results"] for p in item["positions"]})
    if not cut_positions:
        return {
            "summary": "No cut sites found.",
            "fragments_bp": [len(seq)],
            "n_fragments": 1,
            "cut_positions": [],
        }

    cuts = [p - 1 for p in cut_positions]  # 0-based
    if circular:
        cuts = sorted(cuts)
        fragments = []
        for idx, cut in enumerate(cuts):
            nxt = cuts[(idx + 1) % len(cuts)]
            if nxt > cut:
                fragments.append(nxt - cut)
            else:
                fragments.append((len(seq) - cut) + nxt)
    else:
        points = [0] + cuts + [len(seq)]
        fragments = [points[i + 1] - points[i] for i in range(len(points) - 1) if points[i + 1] - points[i] > 0]

    fragments = sorted(fragments, reverse=True)
    return {
        "summary": f"Virtual digest produced {len(fragments)} fragments.",
        "n_fragments": len(fragments),
        "fragments_bp": fragments,
        "cut_positions": cut_positions,
        "circular": bool(circular),
    }


@registry.register(
    name="dna.primer_design",
    description="Design simple PCR primers around a target region",
    category="dna",
    parameters={
        "sequence": "Template DNA sequence",
        "target_start": "Target region start (1-based, optional)",
        "target_end": "Target region end (1-based, optional)",
        "primer_min_len": "Minimum primer length (default 18)",
        "primer_max_len": "Maximum primer length (default 24)",
        "tm_target": "Target primer Tm in C (default 60)",
    },
    usage_guide="Use as a fast first-pass primer suggestion before detailed wet-lab validation.",
)
def primer_design(
    sequence: str,
    target_start: int | None = None,
    target_end: int | None = None,
    primer_min_len: int = 18,
    primer_max_len: int = 24,
    tm_target: float = 60.0,
    **kwargs,
) -> dict:
    seq, err = _validate_dna(sequence)
    if err:
        return {"summary": err, "error": "invalid_sequence"}

    min_len = max(16, int(primer_min_len))
    max_len = max(min_len, min(35, int(primer_max_len)))
    tm_target = float(tm_target)

    start = int(target_start) if target_start else 1
    end = int(target_end) if target_end else len(seq)
    start = max(1, min(start, len(seq)))
    end = max(start, min(end, len(seq)))

    left_window = seq[max(0, start - 1 - 80) : start - 1 + max_len]
    right_window = seq[max(0, end - max_len) : min(len(seq), end + 80)]

    left_cands = _pick_primer_candidates(left_window, min_len, max_len, tm_target)
    right_rev = _reverse_complement(right_window)
    right_cands = _pick_primer_candidates(right_rev, min_len, max_len, tm_target)

    if not left_cands or not right_cands:
        return {"summary": "Unable to design primers in target windows.", "error": "design_failed"}

    fwd = left_cands[0]
    rev = right_cands[0]

    # Approximate amplicon based on target bounds (not exact genomic placement).
    amplicon_bp = max(1, end - start + 1 + len(fwd.seq) + len(rev.seq))

    return {
        "summary": f"Designed primer pair (F {len(fwd.seq)} nt, R {len(rev.seq)} nt) for ~{amplicon_bp} bp amplicon.",
        "forward_primer": {
            "sequence": fwd.seq,
            "length": len(fwd.seq),
            "tm_c": round(fwd.tm, 2),
            "gc_percent": round(fwd.gc, 2),
        },
        "reverse_primer": {
            "sequence": rev.seq,
            "length": len(rev.seq),
            "tm_c": round(rev.tm, 2),
            "gc_percent": round(rev.gc, 2),
        },
        "target_region": {"start": start, "end": end},
        "estimated_amplicon_bp": amplicon_bp,
        "note": "Heuristic first-pass design; verify specificity with BLAST/in-silico PCR.",
    }


@registry.register(
    name="dna.pcr_protocol",
    description="Generate a PCR thermal cycling protocol",
    category="dna",
    parameters={
        "product_size_bp": "Expected amplicon size",
        "primer_tm": "Primer melting temperature in C",
        "polymerase": "Polymerase name (default Q5)",
        "cycles": "Number of PCR cycles (default 30)",
    },
    usage_guide="Use to quickly draft PCR conditions aligned with primer and amplicon properties.",
)
def pcr_protocol(
    product_size_bp: int = 1000,
    primer_tm: float = 60.0,
    polymerase: str = "Q5",
    cycles: int = 30,
    **kwargs,
) -> dict:
    size_bp = max(50, int(product_size_bp))
    tm = float(primer_tm)
    cycles = max(15, min(40, int(cycles)))

    anneal = max(45.0, min(72.0, tm - 3.0))
    extension_s = max(10, int(round(size_bp / 1000.0 * 30)))

    protocol = [
        {"step": "Initial denaturation", "temperature_c": 98, "time_s": 30},
        {"step": f"{cycles} cycles: denaturation", "temperature_c": 98, "time_s": 10},
        {"step": f"{cycles} cycles: annealing", "temperature_c": round(anneal, 1), "time_s": 20},
        {"step": f"{cycles} cycles: extension", "temperature_c": 72, "time_s": extension_s},
        {"step": "Final extension", "temperature_c": 72, "time_s": 120},
        {"step": "Hold", "temperature_c": 4, "time_s": 0},
    ]

    return {
        "summary": f"PCR protocol generated for {size_bp} bp product using {polymerase}.",
        "polymerase": polymerase,
        "cycles": cycles,
        "product_size_bp": size_bp,
        "annealing_temp_c": round(anneal, 1),
        "extension_time_s": extension_s,
        "protocol": protocol,
        "note": "General starting conditions; optimize empirically for template/primers/polymerase buffer.",
    }
