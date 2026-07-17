"""
Unified system prompt builder for the agent runner.

Assembles a slim always-on prompt (identity, workspace, tools, skills index,
workflow index, short synthesis checklist). Heavy domain primers and bio
code-gen live on deepagents subagents (``domain-expert``, ``bio-coder``).

Split into `text_blocks.py`, `workspace_section.py`, `tools_section.py`,
`skills_section.py`, and `knowledge_section.py` combined in `builder.py`;
re-exported here so `from agent.system_prompt import build_system_prompt`
keeps working unchanged.
"""

from .builder import build_system_prompt
from .skills_section import _load_installed_skills

__all__ = ["build_system_prompt"]
