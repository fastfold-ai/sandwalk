"""Parsing @ mentions (tools/datasets/workflows) out of user input."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ui.terminal.dataset_catalog import (
    DATASET_CANDIDATES,
    KNOWN_DATASETS,
    _get_workflow_names,
)
from ui.terminal.model_ids import _is_openai_managed_base_url

# Re-export for package consumers / tests that patch ui.terminal.*
__all__ = [
    "DATASET_CANDIDATES",
    "KNOWN_DATASETS",
    "MentionCandidate",
    "_extract_llm_suggestions",
    "_get_workflow_names",
    "_is_openai_managed_base_url",
    "build_mention_context",
    "extract_mentions",
]


@dataclass
class MentionCandidate:
    """A candidate item for the @ mention autocomplete."""
    name: str          # e.g., "target.coessentiality" or "depmap"
    kind: str          # "tool", "database", or "file"
    category: str      # e.g., "target", "dataset", "file"
    description: str   # truncated for display


def _shield_multimodal_paths(text: str) -> tuple[str, list[str]]:
    """Replace ``@uploads/…`` / other multimodal @paths with placeholders.

    Prevents tool/dataset stripping from mangling path-like tokens such as
    ``@uploads/foo.png`` (would otherwise become ``/foo.png``).
    """
    try:
        from agent.runner.multimodal_user_message import _AT_PATH_RE
    except Exception:  # noqa: BLE001
        return text, []

    protected: list[str] = []

    def _protect(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"\x00PATH{len(protected) - 1}\x00"

    return _AT_PATH_RE.sub(_protect, text), protected


def _restore_multimodal_paths(text: str, protected: list[str]) -> str:
    out = text
    for i, token in enumerate(protected):
        out = out.replace(f"\x00PATH{i}\x00", token)
    return out


def extract_mentions(text: str):
    """Parse @mentions from input text.

    Returns:
        tuple of (cleaned_query, tool_names, dataset_names, workflow_names)

    Multimodal ``@path`` tokens (e.g. ``@uploads/foo.png``) are preserved in
    the cleaned query so vision injection still sees them.
    """
    dataset_names_set = {d[0] for d in DATASET_CANDIDATES}
    workflow_names_set = _get_workflow_names()
    tool_pattern = re.compile(r"@(\w+\.\w+)")
    word_pattern = re.compile(r"@(\w+)")

    tools = []
    datasets = []
    workflows = []

    shielded, protected = _shield_multimodal_paths(text)

    # Find @category.tool_name mentions first
    for m in tool_pattern.finditer(shielded):
        tools.append(m.group(1))

    # Find @dataset and @workflow mentions (single word, no dot)
    cleaned = tool_pattern.sub("", shielded)
    for m in word_pattern.finditer(cleaned):
        name = m.group(1)
        if name in dataset_names_set:
            datasets.append(name)
        elif name in workflow_names_set:
            workflows.append(name)

    # Strip recognized tool/dataset/workflow @mentions only — keep @path media.
    query = re.sub(r"@\w+(?:\.\w+)?", "", shielded).strip()
    query = _restore_multimodal_paths(query, protected)
    # Collapse multiple spaces (but keep newlines for compose multiline)
    query = re.sub(r"[^\S\n]{2,}", " ", query)
    query = re.sub(r"\n{3,}", "\n\n", query)

    return query, tools, datasets, workflows


def build_mention_context(tools: list[str], datasets: list[str], workflows: list[str] | None = None) -> str:
    """Build context string from extracted mentions for planner injection."""
    parts = []
    if tools:
        tool_list = ", ".join(tools)
        parts.append(
            f"User specifically requested these tools: {tool_list}. "
            f"You MUST include these tools in your plan."
        )
    if datasets:
        for ds in datasets:
            desc = next(
                (d[2] for d in DATASET_CANDIDATES if d[0] == ds), ds
            )
            parts.append(f"User requested dataset: {ds} ({desc}).")
    if workflows:
        try:
            from agent.workflows import WORKFLOWS
            for wf_name in workflows:
                wf = WORKFLOWS.get(wf_name)
                if wf:
                    steps = ", ".join(s["tool"] for s in wf.get("steps", []))
                    parts.append(
                        f"User requested workflow '{wf_name}': {wf['description']}. "
                        f"Follow this tool sequence: {steps}"
                    )
        except Exception:
            pass
    return "\n".join(parts)


def _extract_llm_suggestions(synthesis_text: str) -> list[str]:
    """Extract follow-up suggestions from the LLM synthesis output.

    Looks for a 'Suggested Next Steps' section and extracts bullet/numbered items.
    Handles various formats: **"quoted text"**, plain bullets, numbered lists.
    """
    suggestions = []
    in_section = False

    for line in synthesis_text.split("\n"):
        stripped = line.strip()

        # Detect the suggested next steps section
        if "suggested next" in stripped.lower() or "follow-up" in stripped.lower():
            if stripped.startswith("#") or stripped.startswith("**"):
                in_section = True
                continue

        if in_section:
            # Stop at next heading (not related to suggestions)
            if stripped.startswith("#") and "suggested" not in stripped.lower() and "follow" not in stripped.lower():
                break
            # Extract bullet items (-, *, 1., 2., etc.)
            if stripped and (stripped[0] in "-*" or (len(stripped) > 1 and stripped[0].isdigit() and stripped[1] in ".)")):
                # Remove bullet prefix
                text = stripped.lstrip("-*0123456789.) ").strip()
                # Extract quoted text from **"..."** or "..." patterns
                quoted = re.findall(r'["\u201c]([^"\u201d]+)["\u201d]', text)
                if quoted:
                    # Use the longest quoted string (the actual query)
                    text = max(quoted, key=len)
                else:
                    # Remove markdown formatting
                    text = text.strip("`").strip("*").strip("_")
                # Skip if it's a header or too short
                if len(text) > 10 and not text.startswith("#"):
                    suggestions.append(text)

    return suggestions[:5]
