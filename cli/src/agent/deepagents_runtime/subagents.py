"""Domain deepagents subagents that hold heavy prompt packs.

The main agent system prompt stays slim; these subagents receive the former
always-on primers and are invoked via the ``task`` tool when needed.
"""

from __future__ import annotations

from typing import Any

_DOMAIN_EXPERT_PREAMBLE = """\
You are the **domain-expert** subagent for sandwalk.

The parent agent delegated a drug-discovery research question to you. Use the
tool-orientation primer, recommended workflows, and synthesis / domain accuracy
anchors below. Return a complete, accurate answer the parent can relay to the
user — do not invent tool results you did not obtain.
"""

_BIO_CODER_PREAMBLE = """\
You are the **bio-coder** subagent for sandwalk.

Help with ``run_python`` bioinformatics / data-analysis code. Follow the code
generation guide below. Return concrete code and brief usage notes the parent
can relay — keep domain drug-discovery lore out of scope unless the user asked.
"""


def _domain_expert_system_prompt() -> str:
    parts = [_DOMAIN_EXPERT_PREAMBLE]
    try:
        from agent.workflows import format_workflows_for_llm

        workflows = format_workflows_for_llm()
        if workflows:
            parts.append(workflows)
    except Exception:  # noqa: BLE001
        pass
    try:
        from agent.knowledge import KNOWLEDGE_PRIMER, SYNTHESIZER_PRIMER

        parts.append("\n" + KNOWLEDGE_PRIMER)
        parts.append("\n## Synthesis Guidelines\n")
        parts.append(SYNTHESIZER_PRIMER)
    except Exception:  # noqa: BLE001
        pass
    return "\n".join(parts)


def _bio_coder_system_prompt() -> str:
    parts = [_BIO_CODER_PREAMBLE]
    try:
        from tools.code import AGENTIC_CODE_ADDENDUM, BIOINFORMATICS_CODE_GEN_PROMPT

        hints = BIOINFORMATICS_CODE_GEN_PROMPT
        hints = hints.replace(
            "{namespace_description}", "(see run_python tool description)"
        )
        hints = hints.replace(
            "{data_files_description}", "(see data context from the parent)"
        )
        parts.append("\n## Bioinformatics Code Generation Guide\n")
        parts.append(hints)
        parts.append(AGENTIC_CODE_ADDENDUM)
    except Exception:  # noqa: BLE001
        pass
    return "\n".join(parts)


def build_domain_subagents() -> list[dict[str, Any]]:
    """Return deepagents ``SubAgent`` specs for ``create_deep_agent(subagents=...)``."""
    return [
        {
            "name": "domain-expert",
            "description": (
                "Drug-discovery domain expert: tool strategy, recommended "
                "workflows, synthesis quality rules, and accuracy anchors "
                "(CRBN/IMiD, resistance, PROTACs, clinical context). Use for "
                "target/chemistry/clinical research questions that need "
                "domain-accurate synthesis — not for unrelated Q&A or simple "
                "image/file describe turns."
            ),
            "system_prompt": _domain_expert_system_prompt(),
        },
        {
            "name": "bio-coder",
            "description": (
                "Bioinformatics / data-analysis coding specialist for "
                "``run_python`` (pandas, omics tables, stats snippets). Use when "
                "writing or debugging analysis code — not for general chat."
            ),
            "system_prompt": _bio_coder_system_prompt(),
        },
    ]
