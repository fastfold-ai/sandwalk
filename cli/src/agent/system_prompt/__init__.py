"""
Unified system prompt builder for the Claude Agent SDK runner.

Merges the domain knowledge primer, workflow guides, bioinformatics code-gen
hints, synthesis rules, tool catalog, and dynamic data context into a single
system prompt that Claude uses throughout the agentic loop.

Split into `text_blocks.py` (static identity/synthesis/compute-policy text),
`workspace_section.py`, `tools_section.py`, `skills_section.py`, and
`knowledge_section.py` (per-section builders) combined in `builder.py`;
re-exported here so `from agent.system_prompt import build_system_prompt`
keeps working unchanged.
"""

from .builder import build_system_prompt
from .skills_section import _load_installed_skills

__all__ = ["build_system_prompt"]
