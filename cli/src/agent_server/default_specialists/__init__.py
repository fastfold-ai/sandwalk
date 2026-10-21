"""Built-in specialists seeded once on first empty boot.

Profiles are focused on installed FastFold + science skills, and reinforce the
matching built-in tools (category.tool_name). Shared CORE_SKILLS are attached
to every default specialist.

Seeding runs only when the store has never been seeded and the specialists
table is empty. After that, users fully own the list — deleted defaults are
not recreated, and existing rows are not overwritten on boot.

This is a package so the profile catalog, seeding, and the lightweight Fast
computational scientist can live in their own modules. Import from
``agent_server.default_specialists`` as before — this module re-exports the
public API.
"""

from __future__ import annotations

from agent_server.default_specialists.catalog import DEFAULT_SPECIALISTS
from agent_server.default_specialists.fast_computational_scientist import (
    FAST_COMPUTATIONAL_SCIENTIST_META_KEY,
    FAST_COMPUTATIONAL_SCIENTIST_SLUG,
    ensure_fast_computational_scientist,
)
from agent_server.default_specialists.mcp_filter import filter_mcp_servers_for_specialist
from agent_server.default_specialists.seeding import (
    DEFAULT_SPECIALIST_TOOL_NAMES_META_KEY,
    DEFAULT_SPECIALISTS_SEEDED_META_KEY,
    PERSONA_SPECIALISTS_SEEDED_META_KEY,
    ensure_default_specialist_tool_names,
    ensure_default_specialists,
    ensure_persona_specialists,
)

__all__ = [
    "DEFAULT_SPECIALIST_TOOL_NAMES_META_KEY",
    "DEFAULT_SPECIALISTS",
    "DEFAULT_SPECIALISTS_SEEDED_META_KEY",
    "FAST_COMPUTATIONAL_SCIENTIST_META_KEY",
    "FAST_COMPUTATIONAL_SCIENTIST_SLUG",
    "PERSONA_SPECIALISTS_SEEDED_META_KEY",
    "ensure_default_specialist_tool_names",
    "ensure_default_specialists",
    "ensure_fast_computational_scientist",
    "ensure_persona_specialists",
    "filter_mcp_servers_for_specialist",
]
