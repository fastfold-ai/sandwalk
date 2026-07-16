"""Tokenizer estimate + tool-schema text helpers for the prompt budget."""

from __future__ import annotations

import json
from typing import Any

from agent_server.models import PromptBudgetBucket


def estimate_tokens(text: str, *, model: str | None = None) -> tuple[int, str]:
    """Return (tokens, tokenizer_label). Prefer tiktoken on real text."""
    raw = text or ""
    if not raw:
        return 0, "tiktoken"
    try:
        import tiktoken

        encoding_name = "o200k_base"
        try:
            enc = tiktoken.encoding_for_model(str(model or "gpt-4o"))
            encoding_name = getattr(enc, "name", encoding_name) or encoding_name
        except Exception:
            try:
                enc = tiktoken.get_encoding("o200k_base")
            except Exception:
                enc = tiktoken.get_encoding("cl100k_base")
                encoding_name = "cl100k_base"
        # Cap encode size for pathological MCP dumps; scale linearly.
        limit = 400_000
        if len(raw) <= limit:
            return len(enc.encode(raw)), f"tiktoken:{encoding_name}"
        probe = len(enc.encode(raw[:limit]))
        return int(probe * (len(raw) / limit)), f"tiktoken:{encoding_name}"
    except Exception:
        return max(0, (len(raw) + 3) // 4), "chars/4"


def tool_schema_text(tool: Any) -> str:
    name = str(getattr(tool, "name", "") or "")
    description = str(getattr(tool, "description", "") or "")
    schema: Any = {}
    args_schema = getattr(tool, "args_schema", None)
    if args_schema is not None:
        try:
            if hasattr(args_schema, "model_json_schema"):
                schema = args_schema.model_json_schema()
            elif isinstance(args_schema, dict):
                schema = args_schema
        except Exception:
            schema = {}
    try:
        schema_text = json.dumps(schema, ensure_ascii=True, default=str)
    except Exception:
        schema_text = str(schema)
    return f"{name}\n{description}\n{schema_text}"


def bucket_from_text(
    *,
    id: str,
    label: str,
    text: str,
    model: str | None,
    count: int | None = None,
    children: list[PromptBudgetBucket] | None = None,
) -> PromptBudgetBucket:
    raw = text or ""
    tokens, _ = estimate_tokens(raw, model=model)
    return PromptBudgetBucket(
        id=id,
        label=label,
        tokens=tokens,
        chars=len(raw),
        count=count,
        children=children or [],
    )
