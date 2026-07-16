"""
Ghost-text suggestions for the ct interactive terminal.

500 diverse research queries spanning every domain ct supports:
target validation, genetics, chemistry, safety, clinical, omics,
structure, networks, repurposing, biomarkers, experimental design, etc.

Split across per-domain modules to stay under the file-length cap; combined
here into a single flat list. Shuffled at session start so every session
feels different.
"""

from __future__ import annotations

from ui.suggestions.clinical_and_omics import _SUGGESTIONS_CLINICAL_AND_OMICS
from ui.suggestions.specialty_domains import _SUGGESTIONS_SPECIALTY_DOMAINS
from ui.suggestions.structure_and_translational import _SUGGESTIONS_STRUCTURE_AND_TRANSLATIONAL
from ui.suggestions.target_and_chemistry import _SUGGESTIONS_TARGET_AND_CHEMISTRY

DEFAULT_SUGGESTIONS: list[str] = [
    *_SUGGESTIONS_TARGET_AND_CHEMISTRY,
    *_SUGGESTIONS_CLINICAL_AND_OMICS,
    *_SUGGESTIONS_STRUCTURE_AND_TRANSLATIONAL,
    *_SUGGESTIONS_SPECIALTY_DOMAINS,
]

__all__ = ["DEFAULT_SUGGESTIONS"]
