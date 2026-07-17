"""Slim always-on knowledge: workflow index only.

Heavy primers (tool orientation, synthesis rules, CRBN/IMiD anchors, bio
code-gen) live on deepagents subagents — see
``agent.deepagents_runtime.subagents``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("system_prompt")


def build_knowledge_sections() -> str:
    """Assemble the compact always-on knowledge block for the main agent."""
    parts: list[str] = []

    try:
        from agent.workflows import format_workflow_index_for_llm

        index = format_workflow_index_for_llm()
        if index:
            parts.append(index)
    except Exception as e:
        logger.warning("Could not load workflow index: %s", e)

    return "".join(parts)
