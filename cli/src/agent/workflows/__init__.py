"""
Workflow templates for common drug discovery research patterns.

These are injected into the planner prompt to guide tool selection and sequencing.
The planner can follow, adapt, or combine workflows as needed.

The templates are split across sibling ``registry_*`` modules to stay under the
file-length cap; this module merges them back into the public ``WORKFLOWS`` dict.
"""

from agent.workflows.registry_clinical_structure import WORKFLOWS_CLINICAL_STRUCTURE
from agent.workflows.registry_omics_late import WORKFLOWS_OMICS_LATE
from agent.workflows.registry_resistance_omics_early import WORKFLOWS_RESISTANCE_OMICS_EARLY
from agent.workflows.registry_validation_safety import WORKFLOWS_VALIDATION_SAFETY

__all__ = ["WORKFLOWS", "format_workflows_for_llm"]

WORKFLOWS: dict = {
    **WORKFLOWS_VALIDATION_SAFETY,
    **WORKFLOWS_CLINICAL_STRUCTURE,
    **WORKFLOWS_RESISTANCE_OMICS_EARLY,
    **WORKFLOWS_OMICS_LATE,
}


def format_workflows_for_llm(allowed_tools: set[str] | None = None) -> str:
    """Format workflow templates as markdown for the planner prompt."""
    lines = ["\n# Recommended Workflows", ""]
    lines.append(
        "These are expert-recommended tool sequences for common drug discovery tasks. "
        "You may follow, adapt, or combine them as appropriate for the query."
    )
    lines.append("")

    for wf_id, wf in WORKFLOWS.items():
        wf_steps = wf["steps"]
        if allowed_tools is not None:
            wf_steps = [s for s in wf_steps if s["tool"] in allowed_tools]
        if not wf_steps:
            continue

        lines.append(f"## {wf_id}: {wf['description']}")
        triggers = ", ".join(f'"{t}"' for t in wf["trigger_phrases"][:3])
        lines.append(f"  Trigger phrases: {triggers}")
        for i, step in enumerate(wf_steps, 1):
            lines.append(f"  {i}. **{step['tool']}** — {step['why']}")
        lines.append("")

    return "\n".join(lines)
