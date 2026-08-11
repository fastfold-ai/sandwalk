"""dna: sequence transform/translation/ORF/codon-optimization tools.

Split from tools/dna.py.
"""

from __future__ import annotations

import re

from tools import registry
from tools.dna_common import (
    _PREF_CODONS,
    _STOP_CODONS,
    _gc_content,
    _reverse_complement,
    _translate_dna,
    _validate_dna,
)


@registry.register(
    name="dna.reverse_complement",
    description="Compute reverse complement of a DNA sequence",
    category="dna",
    parameters={"sequence": "DNA sequence"},
    usage_guide="Use for strand conversion and antisense oligo planning.",
)
def reverse_complement(sequence: str, **kwargs) -> dict:
    seq, err = _validate_dna(sequence)
    if err:
        return {"summary": err, "error": "invalid_sequence"}
    rc = _reverse_complement(seq)
    return {"summary": f"Reverse complement computed ({len(seq)} bp).", "sequence": seq, "reverse_complement": rc}


@registry.register(
    name="dna.translate",
    description="Translate DNA sequence to amino-acid sequence",
    category="dna",
    parameters={
        "sequence": "DNA sequence",
        "frame": "Reading frame 1-3 (default 1)",
        "to_stop": "Stop translation at first stop codon (default false)",
    },
    usage_guide="Use to inspect coding potential and validate ORF translations.",
)
def translate(sequence: str, frame: int = 1, to_stop: bool = False, **kwargs) -> dict:
    seq, err = _validate_dna(sequence)
    if err:
        return {"summary": err, "error": "invalid_sequence"}
    frame = max(1, min(3, int(frame)))
    aa = _translate_dna(seq, frame=frame, to_stop=bool(to_stop))
    return {
        "summary": f"Translated DNA in frame {frame}: {len(aa)} aa.",
        "frame": frame,
        "protein": aa,
        "protein_length": len(aa),
    }


@registry.register(
    name="dna.find_orfs",
    description="Find open reading frames in a DNA sequence",
    category="dna",
    parameters={
        "sequence": "DNA sequence",
        "min_aa_length": "Minimum amino-acid length (default 30)",
        "include_reverse": "Also scan reverse complement (default false)",
    },
    usage_guide="Use to identify candidate coding regions before cloning or expression.",
)
def find_orfs(sequence: str, min_aa_length: int = 30, include_reverse: bool = False, **kwargs) -> dict:
    seq, err = _validate_dna(sequence)
    if err:
        return {"summary": err, "error": "invalid_sequence"}

    min_aa = max(5, int(min_aa_length))
    scans = [("forward", seq)]
    if include_reverse:
        scans.append(("reverse", _reverse_complement(seq)))

    orfs = []
    for strand, dna in scans:
        for frame in (0, 1, 2):
            i = frame
            while i <= len(dna) - 3:
                codon = dna[i : i + 3]
                if codon != "ATG":
                    i += 3
                    continue
                j = i + 3
                while j <= len(dna) - 3:
                    stop = dna[j : j + 3]
                    if stop in _STOP_CODONS:
                        aa_len = (j + 3 - i) // 3
                        if aa_len >= min_aa:
                            nt_seq = dna[i : j + 3]
                            orfs.append(
                                {
                                    "strand": strand,
                                    "frame": frame + 1,
                                    "start": i + 1,
                                    "end": j + 3,
                                    "length_nt": len(nt_seq),
                                    "length_aa": aa_len,
                                    "protein": _translate_dna(nt_seq, frame=1, to_stop=True),
                                }
                            )
                        break
                    j += 3
                i += 3

    orfs.sort(key=lambda x: x["length_aa"], reverse=True)
    return {
        "summary": f"Found {len(orfs)} ORFs with length >= {min_aa} aa.",
        "orfs": orfs,
        "count": len(orfs),
    }


@registry.register(
    name="dna.codon_optimize",
    description="Codon-optimize a protein sequence for a host species",
    category="dna",
    parameters={
        "protein_sequence": "Amino-acid sequence (single-letter, may include *)",
        "species": "Target host codon table: human or ecoli",
    },
    usage_guide="Use for expression construct design in common hosts.",
)
def codon_optimize(protein_sequence: str, species: str = "human", **kwargs) -> dict:
    protein = re.sub(r"\s+", "", str(protein_sequence or "").upper())
    protein = protein.replace("*", "")
    if not protein:
        return {"summary": "protein_sequence is required.", "error": "missing_protein"}

    host = str(species or "human").strip().lower()
    if host not in _PREF_CODONS:
        return {"summary": "Unsupported species. Use human or ecoli.", "error": "invalid_species"}

    mapping = _PREF_CODONS[host]
    invalid = sorted({aa for aa in protein if aa not in mapping})
    if invalid:
        return {"summary": f"Invalid amino acids: {', '.join(invalid)}", "error": "invalid_protein"}

    dna = "".join(mapping[aa] for aa in protein)
    return {
        "summary": f"Codon-optimized sequence generated for {host} ({len(protein)} aa).",
        "species": host,
        "protein_length": len(protein),
        "optimized_dna": dna,
        "gc_content": round(_gc_content(dna), 2),
    }
