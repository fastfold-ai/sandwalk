"""Workflow guides, domain knowledge primer, code-gen hints, synthesis guidelines."""

from __future__ import annotations

import logging

logger = logging.getLogger("system_prompt")


def build_knowledge_sections() -> str:
    """Assemble workflow guides + domain knowledge primer + code-gen hints +
    synthesis guidelines. Each source is optional and failures are logged, not
    raised, so a broken import never breaks prompt construction.
    """
    parts: list[str] = []

    # Workflow guides (compact — key sequences for common tasks)
    try:
        from agent.workflows import format_workflows_for_llm

        workflows = format_workflows_for_llm()
        if workflows:
            parts.append(workflows)
    except Exception as e:
        logger.warning("Could not load workflows: %s", e)

    # Domain knowledge primer (CRITICAL for drug discovery accuracy).
    # NOTE: The KNOWLEDGE_PRIMER contains both tool orientation AND domain facts.
    # The tool orientation section overlaps with MCP tool descriptions but the
    # cross-disciplinary thinking patterns and domain-specific accuracy anchors
    # are essential. Include in full.
    try:
        from agent.knowledge import KNOWLEDGE_PRIMER

        parts.append("\n" + KNOWLEDGE_PRIMER)
    except Exception as e:
        logger.warning("Could not load knowledge primer: %s", e)

    # Bioinformatics code-gen hints (CRITICAL for BixBench performance)
    try:
        from tools.code import AGENTIC_CODE_ADDENDUM, BIOINFORMATICS_CODE_GEN_PROMPT

        # Strip the template placeholders and include the raw hints
        hints = BIOINFORMATICS_CODE_GEN_PROMPT
        # Remove the {namespace_description} and {data_files_description} placeholders
        hints = hints.replace("{namespace_description}", "(see run_python tool description)")
        hints = hints.replace("{data_files_description}", "(see data context below)")
        parts.append("\n## Bioinformatics Code Generation Guide\n")
        parts.append(
            "When using ``run_python`` for bioinformatics analysis, follow these "
            "patterns and guidelines:\n"
        )
        parts.append(hints)
        parts.append(AGENTIC_CODE_ADDENDUM)
    except Exception as e:
        logger.warning("Could not load code-gen hints: %s", e)

    # Synthesis rules
    try:
        from agent.knowledge import SYNTHESIZER_PRIMER

        parts.append("\n## Synthesis Guidelines\n")
        parts.append(SYNTHESIZER_PRIMER)
    except Exception as e:
        logger.warning("Could not load synthesizer primer: %s", e)

    return "".join(parts)
