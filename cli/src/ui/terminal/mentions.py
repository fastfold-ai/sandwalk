"""@ mention parsing and related helpers for the interactive terminal.

Covers dataset/workflow mention extraction, mention-derived planner context,
and small LLM-output helpers (base-url classification, follow-up suggestion
extraction) used while building the terminal's mention experience.
"""

import re
from dataclasses import dataclass


@dataclass
class MentionCandidate:
    """A candidate item for the @ mention autocomplete."""
    name: str          # e.g., "target.coessentiality" or "depmap"
    kind: str          # "tool", "database", or "file"
    category: str      # e.g., "target", "dataset", "file"
    description: str   # truncated for display


def _is_openai_managed_base_url(base_url: str | None) -> bool:
    """Return True for OpenAI-managed API hosts."""
    from urllib.parse import urlparse

    value = str(base_url or "").strip()
    if not value:
        return True
    try:
        host = (urlparse(value).hostname or "").strip().lower()
    except Exception:
        return False
    if not host:
        return False
    return host == "api.openai.com" or host.endswith(".openai.com")


# ---------------------------------------------------------------------------
# @ Mention: datasets and completer
# ---------------------------------------------------------------------------

DATASET_CANDIDATES = [
    ("depmap", "dataset", "DepMap CRISPR/model data"),
    ("prism", "dataset", "PRISM drug sensitivity"),
    ("l1000", "dataset", "L1000 gene expression signatures"),
    ("proteomics", "dataset", "Proteomics log2FC matrix"),
    ("msigdb", "dataset", "MSigDB gene sets"),
    ("string", "dataset", "STRING protein interaction network"),
]

KNOWN_DATASETS = frozenset(d[0] for d in DATASET_CANDIDATES)


def _get_workflow_names() -> frozenset[str]:
    """Lazily load workflow names."""
    try:
        from agent.workflows import WORKFLOWS
        return frozenset(WORKFLOWS.keys())
    except Exception:
        return frozenset()


def extract_mentions(text: str):
    """Parse @mentions from input text.

    Returns:
        tuple of (cleaned_query, tool_names, dataset_names, workflow_names)
    """
    # Imported from the package namespace (rather than called directly) so
    # that tests can monkeypatch `ui.terminal._get_workflow_names`.
    from ui.terminal import _get_workflow_names as get_workflow_names

    dataset_names_set = {d[0] for d in DATASET_CANDIDATES}
    workflow_names_set = get_workflow_names()
    tool_pattern = re.compile(r"@(\w+\.\w+)")
    word_pattern = re.compile(r"@(\w+)")

    tools = []
    datasets = []
    workflows = []

    # Find @category.tool_name mentions first
    for m in tool_pattern.finditer(text):
        tools.append(m.group(1))

    # Find @dataset and @workflow mentions (single word, no dot)
    cleaned = tool_pattern.sub("", text)
    for m in word_pattern.finditer(cleaned):
        name = m.group(1)
        if name in dataset_names_set:
            datasets.append(name)
        elif name in workflow_names_set:
            workflows.append(name)

    # Strip all recognized @mentions from query
    query = re.sub(r"@\w+(?:\.\w+)?", "", text).strip()
    # Collapse multiple spaces
    query = re.sub(r"\s{2,}", " ", query)

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
