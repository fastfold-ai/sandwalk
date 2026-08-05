"""Tool result formatting and ct-tool-parameters → JSON Schema conversion."""

from __future__ import annotations

from typing import Any


def _format_tool_result(result: Any, max_chars: int = 8000) -> str:
    """Format a ct tool result dict into text for the Agent SDK."""
    if not isinstance(result, dict):
        text = str(result)
        return text[:max_chars] if len(text) > max_chars else text

    parts = []

    # Summary first (most important)
    summary = result.get("summary", "")
    if summary:
        parts.append(summary)

    # Absolute download paths next — keep them whole so the model can cite them
    # even when stdout is dominated by long CloudFront URLs.
    skip = {"summary"}
    local_paths = result.get("local_paths")
    if isinstance(local_paths, list) and local_paths:
        listed = "\n".join(str(p) for p in local_paths if str(p).strip())
        if listed:
            parts.append(f"local_paths:\n{listed}")
        skip.add("local_paths")

    # Include key data fields
    compact = {"top_hits", "top_terms"}
    # Prefer more room for stdout when it carries download paths.
    stdout_budget = 4000 if "local_paths" in skip else 1500
    for key, val in result.items():
        if key in skip:
            continue
        if key in compact and isinstance(val, (dict, list)):
            count = len(val)
            parts.append(f"{key}: {type(val).__name__} with {count} entries")
            continue
        val_str = str(val)
        budget = stdout_budget if key == "stdout" else 1500
        if len(val_str) > budget:
            val_str = val_str[:budget] + f"... [{len(val_str)} chars total]"
        parts.append(f"{key}: {val_str}")

    text = "\n".join(parts)
    return text[:max_chars] if len(text) > max_chars else text


_PY_TYPE_MAP = {
    "str": "string",
    "string": "string",
    "int": "integer",
    "integer": "integer",
    "float": "number",
    "number": "number",
    "bool": "boolean",
    "boolean": "boolean",
    "list": "array",
    "dict": "object",
}


def _params_to_json_schema(parameters: dict) -> dict:
    """Convert a ct tool parameters dict to a JSON Schema object.

    ct tools describe parameters as ``{param_name: description_string}``.
    We map these to string-typed JSON Schema properties since the LLM
    produces string values that tools coerce internally.
    """
    if not parameters:
        return {"type": "object", "properties": {}}

    properties = {}
    for name, desc in parameters.items():
        # Extract type hint from description if present (e.g., "gene name (str)")
        prop = {"type": "string", "description": str(desc)}
        properties[name] = prop

    return {
        "type": "object",
        "properties": properties,
    }
