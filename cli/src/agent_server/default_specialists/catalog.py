"""Assembled list of curated default specialists, in display order."""

from __future__ import annotations

from typing import Any

from agent_server.default_specialists.profiles_design import (
    PROTEIN_DESIGNER,
    SMALL_MOLECULE_SCREEN,
)
from agent_server.default_specialists.profiles_genomics import GENOMICS_ANALYST
from agent_server.default_specialists.profiles_omics import (
    SINGLE_CELL_ANALYST,
    TARGET_DISCOVERY,
)
from agent_server.default_specialists.profiles_personas import (
    AMBITIOUS_GENERALIST,
    DREAMER,
    OTIUM_RELAXED,
    PERSONA_SPECIALISTS,
    PROJECT_MANAGER,
    SKEPTICAL_REVIEWER,
)
from agent_server.default_specialists.profiles_structure import (
    MOLECULAR_DYNAMICS,
    STRUCTURE_PREDICTION,
)

DEFAULT_SPECIALISTS: list[dict[str, Any]] = [
    PROTEIN_DESIGNER,
    SMALL_MOLECULE_SCREEN,
    STRUCTURE_PREDICTION,
    MOLECULAR_DYNAMICS,
    TARGET_DISCOVERY,
    SINGLE_CELL_ANALYST,
    GENOMICS_ANALYST,
]

__all__ = ["DEFAULT_SPECIALISTS", "PERSONA_SPECIALISTS"]
