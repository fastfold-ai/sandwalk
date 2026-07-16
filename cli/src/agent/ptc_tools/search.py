"""On-demand tool signature search used by ``search_tools`` and ``tools.search``."""

from __future__ import annotations

import re
from typing import Any

from .common import iter_domain_tools, signature


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", str(text).lower()) if t]


def search_tools_text(
    query: str,
    *,
    category: str | None = None,
    limit: int = 12,
    exclude_categories: set[str] | None = None,
    exclude_tools: set[str] | None = None,
) -> str:
    """Return compact signatures for domain tools matching ``query``.

    Scores tools by token overlap against name + description + parameter
    names/descriptions. Used by the ``search_tools`` tool and ``tools.search``.
    """
    query = (query or "").strip()
    tokens = _tokenize(query)

    scored: list[tuple[int, Any]] = []
    for tool_obj in iter_domain_tools(
        exclude_categories=exclude_categories, exclude_tools=exclude_tools
    ):
        if category and tool_obj.category != category:
            continue
        haystack = " ".join(
            [
                tool_obj.name,
                tool_obj.description or "",
                getattr(tool_obj, "usage_guide", "") or "",
                " ".join((tool_obj.parameters or {}).keys()),
                " ".join(str(v) for v in (tool_obj.parameters or {}).values()),
            ]
        ).lower()

        if not tokens:
            score = 1
        else:
            score = 0
            for tok in tokens:
                if tok in haystack:
                    score += 1
                if tok in tool_obj.name.lower():
                    score += 2  # weight name matches
            if score == 0:
                continue
        scored.append((score, tool_obj))

    scored.sort(key=lambda pair: (-pair[0], pair[1].name))
    top = scored[:limit]

    if not top:
        return f"No domain tools matched '{query}'. Try tools.list() or a broader query."

    lines = [f"Matches for '{query}' (showing {len(top)} of {len(scored)}):"]
    for _score, tool_obj in top:
        desc = (tool_obj.description or "").strip().replace("\n", " ")
        if len(desc) > 160:
            desc = desc[:157] + "..."
        lines.append(f"- {signature(tool_obj)} -> dict")
        if desc:
            lines.append(f"    {desc}")
    return "\n".join(lines)
