"""Shared HTTP probe for LLM provider API keys.

Used by doctor and by Integrations ``/validate``. Every provider gets a real
auth check: a 1-token chat/messages call (GET /models is not trusted — some
gateways publish the catalog without a valid key).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelsProbeResult:
    ok: bool
    message: str
    model_count: int = 0
    status_code: int | None = None
    # When set, caller may persist this as the provider's working base URL.
    base_url: str | None = None


_AUTH_MARKERS = (
    "incorrect api key",
    "invalid api key",
    "invalid_api_key",
    "api key not valid",
    "pass a valid api key",
    "please pass a valid api key",
    "unauthorized",
    "authentication",
    "authorization failed",
    "api key provided",
    "invalid authentication",
    "invalid x-api-key",
)

# Cheap models for the 1-token ping (override provider default when useful).
_PROBE_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-5-nano",
    "google": "gemini-3.1-flash-lite",
    "xai": "grok-4.5",
    "moonshot": "kimi-k2.7-code-highspeed",
    "nvidia": "meta/llama-3.1-8b-instruct",
    "opencode": "gpt-5-nano",
    "deepseek": "deepseek-v4-flash",
    "minimax": "MiniMax-M2.5",
    "mistral": "mistral-small-latest",
    "qwen": "qwen3.7-plus",
    # Curated serverless id from the Together catalog (non-serverless
    # Meta-Llama Turbo returns HTTP 400 "Unable to access non-serverless model").
    "together": "zai-org/GLM-5.2",
    # OpenRouter free-tier ping; curated catalog default is Claude Sonnet.
    "openrouter": "openai/gpt-4o-mini",
}

# Models vary by Qwen plan; try a few cheap/common ids per endpoint.
_QWEN_PROBE_MODELS = (
    "qwen3.7-plus",
    "qwen3.6-plus",
    "qwen3.5-plus",
    "qwen3-max",
    "qwen3-coder-plus",
)

_QWEN_MODEL_MISS_MARKERS = (
    "model not exist",
    "model_not_found",
    "model not found",
    "not supported",
    "access to model denied",
    "not exist",
)


def _error_snippet(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    err = payload.get("error")
    if isinstance(err, dict):
        return str(err.get("message") or err.get("error") or "").strip()
    if err:
        return str(err).strip()
    detail = str(payload.get("detail") or "").strip()
    if detail:
        return detail
    return str(payload.get("message") or "").strip()


def _classify_http_result(
    *,
    label: str,
    code: int,
    body_text: str,
    payload: object | None,
    success_message: str,
) -> ModelsProbeResult:
    body_lower = (body_text or "").lower()
    if code < 300:
        return ModelsProbeResult(
            ok=True,
            message=success_message,
            status_code=code,
        )
    snippet = _error_snippet(payload)[:160] if payload is not None else ""
    if code in (401, 403):
        detail = f" ({snippet})" if snippet else ""
        return ModelsProbeResult(
            ok=False,
            message=f"Invalid API key.{detail}",
            status_code=code,
        )
    if any(m in body_lower for m in _AUTH_MARKERS):
        detail = f" ({snippet})" if snippet else ""
        return ModelsProbeResult(
            ok=False,
            message=f"Invalid API key.{detail}",
            status_code=code,
        )
    if snippet:
        return ModelsProbeResult(
            ok=False,
            message=f"{label} returned HTTP {code}: {snippet}",
            status_code=code,
        )
    return ModelsProbeResult(
        ok=False,
        message=f"{label} returned HTTP {code}.",
        status_code=code,
    )


def _reply_from_openai_chat(payload: object | None) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict):
        return str(message.get("content") or "").strip()
    return str(first.get("text") or "").strip()


def _reply_from_anthropic(payload: object | None) -> str:
    if not isinstance(payload, dict):
        return ""
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = str(block.get("text") or "").strip()
            if text:
                parts.append(text)
    return " ".join(parts).strip()


def _success_message(label: str, reply: str) -> str:
    if reply:
        return f"{label} API key works — model replied: {reply[:80]}"
    return f"{label} API key works."


def probe_chat_completions(
    url: str,
    headers: dict[str, str],
    *,
    label: str,
    model: str,
    timeout: float = 30.0,
) -> ModelsProbeResult:
    """Auth-check via a 1-token OpenAI-compatible chat completion."""
    try:
        import httpx
    except ImportError:
        return ModelsProbeResult(
            ok=False,
            message="httpx is not installed — cannot test the API key.",
        )

    try:
        resp = httpx.post(
            url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (compatible; Sandwalk/1.0; "
                    "+https://github.com/fastfold-ai/sandwalk)"
                ),
                **headers,
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "temperature": 0,
            },
            timeout=timeout,
            follow_redirects=True,
        )
    except Exception as exc:
        return ModelsProbeResult(
            ok=False,
            message=f"Couldn't reach {label} ({exc.__class__.__name__}).",
        )

    payload: object | None = None
    try:
        payload = resp.json()
    except Exception:
        payload = None
    return _classify_http_result(
        label=label,
        code=resp.status_code,
        body_text=(resp.text or ""),
        payload=payload,
        success_message=_success_message(label, _reply_from_openai_chat(payload)),
    )


def probe_anthropic_messages(
    api_key: str,
    *,
    label: str = "Anthropic",
    model: str = "claude-haiku-4-5-20251001",
    timeout: float = 30.0,
) -> ModelsProbeResult:
    """Auth-check via a 1-token Anthropic Messages call."""
    try:
        import httpx
    except ImportError:
        return ModelsProbeResult(
            ok=False,
            message="httpx is not installed — cannot test the API key.",
        )

    try:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "User-Agent": (
                    "Mozilla/5.0 (compatible; Sandwalk/1.0; "
                    "+https://github.com/fastfold-ai/sandwalk)"
                ),
            },
            json={
                "model": model,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}],
            },
            timeout=timeout,
            follow_redirects=True,
        )
    except Exception as exc:
        return ModelsProbeResult(
            ok=False,
            message=f"Couldn't reach {label} ({exc.__class__.__name__}).",
        )

    payload: object | None = None
    try:
        payload = resp.json()
    except Exception:
        payload = None
    return _classify_http_result(
        label=label,
        code=resp.status_code,
        body_text=(resp.text or ""),
        payload=payload,
        success_message=_success_message(label, _reply_from_anthropic(payload)),
    )


def supports_llm_key_probe(provider_key: str) -> bool:
    """True when ``provider_key`` has a live auth probe we can run."""
    from agent.config import OPENAI_COMPATIBLE_PROVIDERS

    return provider_key in ("anthropic", "openai") or provider_key in OPENAI_COMPATIBLE_PROVIDERS


def _probe_model_for(provider_key: str) -> str:
    from agent.config import OPENAI_COMPATIBLE_PROVIDERS

    if provider_key in _PROBE_MODELS:
        return _PROBE_MODELS[provider_key]
    meta = OPENAI_COMPATIBLE_PROVIDERS.get(provider_key) or {}
    return str(meta.get("default_model") or "").strip() or "gpt-5-nano"


def probe_llm_api_key(
    provider_key: str,
    api_key: str,
    *,
    label: str | None = None,
    timeout: float = 30.0,
) -> ModelsProbeResult:
    """Live-validate an LLM provider API key with a 1-token model call."""
    from agent.config import OPENAI_COMPATIBLE_PROVIDERS

    key = (api_key or "").strip()
    name = label or provider_key
    if not key:
        return ModelsProbeResult(
            ok=False,
            message=f"Enter a {name} API key to test.",
        )
    if not supports_llm_key_probe(provider_key):
        return ModelsProbeResult(
            ok=False,
            message=f"Live key test is not supported for {name}.",
        )

    model = _probe_model_for(provider_key)
    wait = max(timeout, 30.0)

    if provider_key == "anthropic":
        return probe_anthropic_messages(
            key,
            label=label or "Anthropic",
            model=model,
            timeout=wait,
        )

    if provider_key == "openai":
        return probe_chat_completions(
            "https://api.openai.com/v1/chat/completions",
            {"Authorization": f"Bearer {key}"},
            label=label or "OpenAI",
            model=model,
            timeout=wait,
        )

    meta = OPENAI_COMPATIBLE_PROVIDERS[provider_key]
    resolved = str(meta.get("label") or provider_key)
    if provider_key == "qwen":
        return _probe_qwen_api_key(key, label=label or resolved, timeout=wait)
    base = str(meta["base_url"]).rstrip("/")
    headers = {"Authorization": f"Bearer {key}"}
    if provider_key == "openrouter":
        from agent.deepagents_runtime.openrouter_attribution import (
            openrouter_attribution_headers,
        )

        headers.update(openrouter_attribution_headers())
    return probe_chat_completions(
        f"{base}/chat/completions",
        headers,
        label=label or resolved,
        model=model,
        timeout=wait,
    )


def _qwen_model_miss(result: ModelsProbeResult) -> bool:
    text = (result.message or "").lower()
    return any(marker in text for marker in _QWEN_MODEL_MISS_MARKERS)


def _probe_qwen_api_key(
    api_key: str,
    *,
    label: str,
    timeout: float,
) -> ModelsProbeResult:
    """Try Token Plan / Coding Plan / pay-as-you-go hosts until auth succeeds."""
    from agent.config import (
        Config,
        normalize_qwen_base_url,
        qwen_base_url_candidates,
    )

    headers = {"Authorization": f"Bearer {api_key}"}
    configured = normalize_qwen_base_url(
        str(Config.load().get("llm.qwen_base_url") or "")
    )
    bases = [configured] if configured else qwen_base_url_candidates(api_key)
    last = ModelsProbeResult(
        ok=False,
        message=f"Couldn't validate {label} API key against known Qwen Cloud endpoints.",
    )
    for base in bases:
        host = str(base).rstrip("/")
        if not host:
            continue
        endpoint_auth_failed = False
        for model in _QWEN_PROBE_MODELS:
            result = probe_chat_completions(
                f"{host}/chat/completions",
                headers,
                label=label,
                model=model,
                timeout=timeout,
            )
            last = result
            if result.ok:
                return ModelsProbeResult(
                    ok=True,
                    message=result.message,
                    status_code=result.status_code,
                    base_url=host,
                )
            # Auth failure ⇒ wrong plan host (or truly bad key); try next host.
            if result.status_code in (401, 403) and not _qwen_model_miss(result):
                endpoint_auth_failed = True
                break
            # Model missing/denied on this host ⇒ key is accepted; try next model.
            if _qwen_model_miss(result):
                continue
            # Other errors (rate limit, network): surface them with this host.
            return ModelsProbeResult(
                ok=False,
                message=result.message,
                status_code=result.status_code,
                base_url=host,
            )
        if endpoint_auth_failed:
            if configured:
                return ModelsProbeResult(
                    ok=False,
                    message=(
                        f"Invalid API key for the selected endpoint ({host}). "
                        "Try Auto-detect, or pick the plan that matches your key."
                    ),
                    status_code=last.status_code,
                    base_url=host,
                )
            continue
        # Authenticated but no probe model worked — still remember the host.
        return ModelsProbeResult(
            ok=False,
            message=(
                f"{label} key is accepted at {host}, but no probe model responded. "
                "Try setting a Token Plan model such as qwen3.7-plus."
            ),
            status_code=last.status_code,
            base_url=host,
        )
    return last


# Back-compat aliases used by older doctor helpers / tests.
CHAT_PROBE_PROVIDERS = frozenset(
    {
        "anthropic",
        "openai",
        "google",
        "xai",
        "moonshot",
        "nvidia",
        "opencode",
        "deepseek",
        "minimax",
        "mistral",
        "qwen",
        "together",
        "openrouter",
    }
)


def probe_models_endpoint(
    url: str,
    headers: dict[str, str],
    *,
    label: str,
    timeout: float = 10.0,
) -> ModelsProbeResult:
    """Legacy GET /models helper (not used for key validation anymore)."""
    try:
        import httpx
    except ImportError:
        return ModelsProbeResult(
            ok=False,
            message="httpx is not installed — cannot test the API key.",
        )

    try:
        resp = httpx.get(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (compatible; Sandwalk/1.0; "
                    "+https://github.com/fastfold-ai/sandwalk)"
                ),
                **headers,
            },
            timeout=timeout,
            follow_redirects=True,
        )
    except Exception as exc:
        return ModelsProbeResult(
            ok=False,
            message=f"Couldn't reach {label} ({exc.__class__.__name__}).",
        )

    payload: object | None = None
    try:
        payload = resp.json()
    except Exception:
        payload = None
    count = 0
    if isinstance(payload, dict):
        data = payload.get("data") or payload.get("models")
        if isinstance(data, list):
            count = len(data)
    if count:
        noun = "model" if count == 1 else "models"
        success = f"{label} API key works ({count} {noun})."
    else:
        success = f"{label} API key works."
    result = _classify_http_result(
        label=label,
        code=resp.status_code,
        body_text=(resp.text or ""),
        payload=payload,
        success_message=success,
    )
    if result.ok and count:
        return ModelsProbeResult(
            ok=True,
            message=success,
            model_count=count,
            status_code=result.status_code,
        )
    return result


def resolve_llm_probe_target(
    provider_key: str, api_key: str
) -> tuple[str, str, dict[str, str]] | None:
    """Deprecated: validation no longer uses GET /models targets."""
    return None
