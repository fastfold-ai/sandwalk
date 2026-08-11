"""
DNA biology utilities for sequence analysis and planning.

Includes sequence transforms, ORF detection, primer suggestions, codon optimization,
restriction analysis, and assembly helper templates.

Split across tools/dna_common.py (constants/helpers), tools/dna_sequence.py
(reverse_complement/translate/find_orfs/codon_optimize), tools/dna_cloning.py
(restriction_sites/virtual_digest/primer_design/pcr_protocol), and
tools/dna_assembly.py (gibson_design/golden_gate_design); re-exported here
for backward compatibility. This module is the canonical patch target for
tests (e.g. ``from tools.dna import reverse_complement``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tools.dna_assembly import gibson_design, golden_gate_design
from tools.dna_cloning import pcr_protocol, primer_design, restriction_sites, virtual_digest
from tools.dna_common import (
    _CODON_TABLE,
    _clean_seq,
    _DNA_ALPHABET,
    _ENZYME_MOTIFS,
    _find_sites,
    _gc_content,
    _pick_primer_candidates,
    _PREF_CODONS,
    _PrimerCandidate,
    _reverse_complement,
    _STOP_CODONS,
    _translate_dna,
    _validate_dna,
    _wallace_tm,
)
from tools.dna_sequence import codon_optimize, find_orfs, reverse_complement, translate

__all__ = [
    "re",
    "dataclass",
    "_DNA_ALPHABET",
    "_STOP_CODONS",
    "_CODON_TABLE",
    "_PREF_CODONS",
    "_ENZYME_MOTIFS",
    "_PrimerCandidate",
    "_clean_seq",
    "_validate_dna",
    "_reverse_complement",
    "_wallace_tm",
    "_gc_content",
    "_translate_dna",
    "_find_sites",
    "_pick_primer_candidates",
    "reverse_complement",
    "translate",
    "find_orfs",
    "codon_optimize",
    "restriction_sites",
    "virtual_digest",
    "primer_design",
    "pcr_protocol",
    "gibson_design",
    "golden_gate_design",
]
