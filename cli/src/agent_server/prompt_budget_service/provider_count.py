"""Provider-native input token counting for Context (Provider mode).

Dispatches by ``llm.provider``:
- anthropic → Messages ``count_tokens``
- openai → Responses ``/v1/responses/input_tokens``
- google → Gemini ``models.count_tokens``

Other providers return ``None`` so the estimator keeps the local tiktoken total.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("prompt_budget")


def _parse_tools(tool_texts: list[str]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for text in tool_texts:
        raw = (text or "").strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and parsed.get("name"):
                tools.append(parsed)
                continue
        except Exception:
            pass
        tools.append(
            {
                "name": "tool",
                "description": raw[:500],
                "input_schema": {"type": "object", "properties": {}},
            }
        )
    return tools


def _system_text(system_parts: list[str]) -> str:
    return "\n\n".join(part.strip() for part in system_parts if (part or "").strip())


def _sanitize_google_schema(value: Any) -> Any:
    """Remove JSON Schema metadata unsupported by google.genai ``Schema``."""
    if isinstance(value, list):
        return [_sanitize_google_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        key: _sanitize_google_schema(item)
        for key, item in value.items()
        if not str(key).startswith("$")
    }


def count_anthropic_input_tokens(
    *,
    model: str,
    api_key: str | None,
    system_parts: list[str],
    tool_texts: list[str],
    sample_user: str = "hi",
) -> int | None:
    key = (api_key or "").strip()
    mid = (model or "").strip()
    if not key or not mid:
        return None
    try:
        import anthropic
    except Exception as exc:  # noqa: BLE001
        logger.debug("anthropic import failed: %s", exc)
        return None

    system = [{"type": "text", "text": part} for part in system_parts if (part or "").strip()]
    tools = _parse_tools(tool_texts)
    try:
        client = anthropic.Anthropic(api_key=key)
        kwargs: dict[str, Any] = {
            "model": mid,
            "messages": [{"role": "user", "content": sample_user or "hi"}],
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        result = client.messages.count_tokens(**kwargs)
        return int(getattr(result, "input_tokens", 0) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.info("anthropic count_tokens failed: %s", exc)
        return None


def _openai_count_base_url(base_url: str | None) -> str | None:
    """Only use hosted OpenAI for counting; skip local/compatible proxies."""
    raw = (base_url or "").strip()
    if not raw:
        return None
    lower = raw.lower()
    if "api.openai.com" in lower:
        return raw
    # Local Ollama / LM Studio / custom OpenAI-compatible servers rarely
    # implement /responses/input_tokens.
    return None


def count_openai_input_tokens(
    *,
    model: str,
    api_key: str | None,
    system_parts: list[str],
    tool_texts: list[str],
    sample_user: str = "hi",
    base_url: str | None = None,
) -> int | None:
    """Count via OpenAI Responses ``input_tokens`` (includes tools)."""
    key = (api_key or "").strip()
    mid = (model or "").strip()
    if not key or not mid:
        return None
    # Local / placeholder keys never hit the hosted counting endpoint.
    if key.lower() in {"ollama", "local", "none", "test"}:
        return None
    if base_url and _openai_count_base_url(base_url) is None:
        return None
    try:
        from openai import OpenAI
    except Exception as exc:  # noqa: BLE001
        logger.debug("openai import failed: %s", exc)
        return None

    tools = []
    for tool in _parse_tools(tool_texts):
        params = tool.get("input_schema") or tool.get("parameters") or {
            "type": "object",
            "properties": {},
        }
        tools.append(
            {
                "type": "function",
                "name": str(tool.get("name") or "tool"),
                "description": str(tool.get("description") or "") or None,
                "parameters": params,
                "strict": False,
            }
        )

    kwargs: dict[str, Any] = {"api_key": key}
    resolved = _openai_count_base_url(base_url)
    if resolved:
        kwargs["base_url"] = resolved
    try:
        client = OpenAI(**kwargs)
        result = client.responses.input_tokens.count(
            model=mid,
            instructions=_system_text(system_parts) or None,
            input=[{"role": "user", "content": sample_user or "hi"}],
            tools=tools or None,
        )
        return int(getattr(result, "input_tokens", 0) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.info("openai input_tokens.count failed: %s", exc)
        return None


def count_google_input_tokens(
    *,
    model: str,
    api_key: str | None,
    system_parts: list[str],
    tool_texts: list[str],
    sample_user: str = "hi",
) -> int | None:
    """Count via Gemini ``models.count_tokens`` (system + tools when supported)."""
    key = (api_key or "").strip()
    mid = (model or "").strip()
    if not key or not mid:
        return None
    try:
        from google import genai
        from google.genai import types
    except Exception as exc:  # noqa: BLE001
        logger.debug("google.genai import failed: %s", exc)
        return None

    system = _system_text(system_parts)
    try:
        declarations = []
        for tool in _parse_tools(tool_texts):
            params = tool.get("input_schema") or tool.get("parameters") or {
                "type": "object",
                "properties": {},
            }
            declarations.append(
                types.FunctionDeclaration(
                    name=str(tool.get("name") or "tool"),
                    description=str(tool.get("description") or "") or None,
                    parameters=_sanitize_google_schema(params),
                )
            )
        client = genai.Client(api_key=key)
        config_kwargs: dict[str, Any] = {}
        if system:
            config_kwargs["system_instruction"] = system
        if declarations:
            config_kwargs["tools"] = [
                types.Tool(function_declarations=declarations)
            ]
        result = client.models.count_tokens(
            model=mid,
            contents=sample_user or "hi",
            config=types.CountTokensConfig(**config_kwargs) if config_kwargs else None,
        )
        return int(getattr(result, "total_tokens", 0) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.info("google count_tokens failed: %s", exc)
        # Retry without tools/system config — some Gemini API paths only count contents.
        try:
            client = genai.Client(api_key=key)
            blob = "\n\n".join(
                part for part in (system, sample_user or "hi") if part
            )
            result = client.models.count_tokens(model=mid, contents=blob)
            return int(getattr(result, "total_tokens", 0) or 0)
        except Exception as exc2:  # noqa: BLE001
            logger.info("google count_tokens fallback failed: %s", exc2)
            return None


def count_provider_input_tokens(
    *,
    provider: str,
    model: str,
    api_key: str | None,
    system_parts: list[str],
    tool_texts: list[str],
    sample_user: str = "hi",
    base_url: str | None = None,
) -> tuple[int | None, str | None]:
    """Return ``(tokens, tokenizer_label)`` for the active provider.

    ``tokenizer_label`` is set only when counting succeeds.
    """
    prov = (provider or "").strip().lower()
    if prov == "anthropic":
        tokens = count_anthropic_input_tokens(
            model=model,
            api_key=api_key,
            system_parts=system_parts,
            tool_texts=tool_texts,
            sample_user=sample_user,
        )
        if tokens:
            return tokens, f"anthropic:count_tokens:{model}"
        return None, None
    if prov == "openai":
        tokens = count_openai_input_tokens(
            model=model,
            api_key=api_key,
            system_parts=system_parts,
            tool_texts=tool_texts,
            sample_user=sample_user,
            base_url=base_url,
        )
        if tokens:
            return tokens, f"openai:input_tokens:{model}"
        return None, None
    if prov == "google":
        tokens = count_google_input_tokens(
            model=model,
            api_key=api_key,
            system_parts=system_parts,
            tool_texts=tool_texts,
            sample_user=sample_user,
        )
        if tokens:
            return tokens, f"google:count_tokens:{model}"
        return None, None
    return None, None
