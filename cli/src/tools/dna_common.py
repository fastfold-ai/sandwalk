"""Shared constants and helpers for DNA biology tools.

Split from tools/dna.py. Holds codon tables, enzyme motifs, and small sequence
utilities shared by the DNA sequence-analysis and cloning-design submodules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_DNA_ALPHABET = set("ACGTN")
_STOP_CODONS = {"TAA", "TAG", "TGA"}
_CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L", "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M", "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S", "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T", "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*", "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K", "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W", "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R", "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

# Preferred codons (lightweight, pragmatic defaults).
_PREF_CODONS = {
    "human": {
        "A": "GCC", "R": "CGC", "N": "AAC", "D": "GAC", "C": "TGC", "Q": "CAG", "E": "GAG", "G": "GGC",
        "H": "CAC", "I": "ATC", "L": "CTG", "K": "AAG", "M": "ATG", "F": "TTC", "P": "CCC", "S": "AGC",
        "T": "ACC", "W": "TGG", "Y": "TAC", "V": "GTG",
    },
    "ecoli": {
        "A": "GCG", "R": "CGT", "N": "AAC", "D": "GAT", "C": "TGC", "Q": "CAG", "E": "GAA", "G": "GGC",
        "H": "CAT", "I": "ATT", "L": "CTG", "K": "AAA", "M": "ATG", "F": "TTT", "P": "CCG", "S": "TCT",
        "T": "ACC", "W": "TGG", "Y": "TAT", "V": "GTG",
    },
}

_ENZYME_MOTIFS = {
    "EcoRI": "GAATTC",
    "BamHI": "GGATCC",
    "HindIII": "AAGCTT",
    "NotI": "GCGGCCGC",
    "XhoI": "CTCGAG",
    "NheI": "GCTAGC",
    "BsaI": "GGTCTC",
    "BsmBI": "CGTCTC",
}


@dataclass
class _PrimerCandidate:
    seq: str
    tm: float
    gc: float


def _clean_seq(seq: str) -> str:
    return re.sub(r"\s+", "", str(seq or "").upper())


def _validate_dna(seq: str) -> tuple[str, str | None]:
    s = _clean_seq(seq)
    if not s:
        return s, "sequence is required"
    if any(base not in _DNA_ALPHABET for base in s):
        return s, "sequence contains non-DNA characters"
    return s, None


def _reverse_complement(seq: str) -> str:
    table = str.maketrans("ACGTN", "TGCAN")
    return seq.translate(table)[::-1]


def _wallace_tm(seq: str) -> float:
    seq = seq.upper()
    at = seq.count("A") + seq.count("T")
    gc = seq.count("G") + seq.count("C")
    return 2.0 * at + 4.0 * gc


def _gc_content(seq: str) -> float:
    seq = seq.upper()
    gc = seq.count("G") + seq.count("C")
    return (100.0 * gc / len(seq)) if seq else 0.0


def _translate_dna(seq: str, frame: int = 1, to_stop: bool = False) -> str:
    offset = max(0, min(2, frame - 1))
    aa = []
    for i in range(offset, len(seq) - 2, 3):
        codon = seq[i : i + 3]
        residue = _CODON_TABLE.get(codon, "X")
        if residue == "*" and to_stop:
            break
        aa.append(residue)
    return "".join(aa)


def _find_sites(seq: str, motif: str) -> list[int]:
    positions = []
    start = 0
    while True:
        idx = seq.find(motif, start)
        if idx < 0:
            break
        positions.append(idx + 1)  # 1-based
        start = idx + 1
    return positions


def _pick_primer_candidates(seq: str, min_len: int, max_len: int, tm_target: float) -> list[_PrimerCandidate]:
    out = []
    for n in range(min_len, max_len + 1):
        if n > len(seq):
            break
        cand = seq[:n]
        tm = _wallace_tm(cand)
        gc = _gc_content(cand)
        if 35 <= gc <= 70:
            out.append(_PrimerCandidate(seq=cand, tm=tm, gc=gc))
    out.sort(key=lambda c: abs(c.tm - tm_target))
    return out
