"""Module-level helpers for AgentRunner: LLM error classification, execution-claim
guardrails, background task output probing, and terminal notification helpers.

Kept separate from ``runner.py`` so that file can focus on the ``AgentRunner``
class itself. These are plain functions (no shared state) re-imported into
``agent.runner`` so existing ``agent.runner.<name>`` monkeypatches used across
the test suite keep working unchanged.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from agent import runner as _runner


def _extract_provider_error_payload(exc: Exception) -> dict | None:
    """Pull a JSON error body from OpenAI / OpenRouter / httpx-style exceptions."""
    for candidate in (
        getattr(exc, "body", None),
        getattr(exc, "response_json", None),
    ):
        if isinstance(candidate, dict):
            return candidate
        if isinstance(candidate, str) and candidate.strip().startswith("{"):
            try:
                parsed = json.loads(candidate)
            except Exception:  # noqa: BLE001
                parsed = None
            if isinstance(parsed, dict):
                return parsed

    response = getattr(exc, "response", None)
    if response is not None:
        try:
            parsed = response.json()
        except Exception:  # noqa: BLE001
            parsed = None
        if isinstance(parsed, dict):
            return parsed
        try:
            text = str(getattr(response, "text", "") or "").strip()
        except Exception:  # noqa: BLE001
            text = ""
        if text.startswith("{"):
            try:
                parsed = json.loads(text)
            except Exception:  # noqa: BLE001
                parsed = None
            if isinstance(parsed, dict):
                return parsed
    return None


def _format_openrouter_provider_detail(payload: dict) -> str | None:
    """Prefer OpenRouter ``error.metadata.raw`` over the opaque wrapper message."""
    err = payload.get("error")
    if not isinstance(err, dict):
        err = payload if isinstance(payload.get("message"), str) else None
    if not isinstance(err, dict):
        return None

    message = str(err.get("message") or "").strip()
    metadata = err.get("metadata") if isinstance(err.get("metadata"), dict) else {}
    raw = str(metadata.get("raw") or metadata.get("error") or "").strip()
    provider = str(
        metadata.get("provider_name")
        or metadata.get("provider")
        or ""
    ).strip()

    # Typical OpenRouter upstream failure: message="Provider returned error"
    # with the real diagnosis in metadata.raw.
    if raw:
        if provider and provider.lower() not in raw.lower():
            return f"{provider}: {raw}"
        return raw
    if message and message.lower() != "provider returned error":
        if provider:
            return f"{provider}: {message}"
        return message
    if provider and message:
        return f"{provider}: {message}"
    return message or None


def _provider_error_detail(exc: Exception, *, limit: int = 360) -> str:
    """Return a single-line, truncated provider error for UI/logs."""
    # Prefer structured OpenRouter/OpenAI bodies so the chat UI shows the
    # upstream diagnosis instead of the opaque "Provider returned error".
    detail = None
    payload = _extract_provider_error_payload(exc)
    if payload is not None:
        detail = _format_openrouter_provider_detail(payload)
    if not detail:
        # Walk causes — LangChain often wraps the OpenAI error.
        cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
        if isinstance(cause, BaseException):
            nested = _extract_provider_error_payload(cause)
            if nested is not None:
                detail = _format_openrouter_provider_detail(nested)
            if not detail:
                detail = " ".join(str(cause).split()) or None

    text = detail or " ".join(str(exc).split())
    # Drop long "how to tune" tails; keep the actionable diagnosis.
    for marker in (
        " Tune or disable via",
        " See also `http_socket_options`",
        " See also http_socket_options",
    ):
        idx = text.find(marker)
        if idx > 40:
            text = text[:idx].rstrip(" .") + "."
            break
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def _is_transient_transport_error(exc: BaseException, low: str | None = None) -> bool:
    """True for dropped TLS / keep-alive failures that are safe to retry once."""
    blob = (low or "") + " " + " ".join(str(exc).split()).lower()
    cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    if isinstance(cause, BaseException):
        blob += " " + " ".join(str(cause).split()).lower()
    return (
        isinstance(exc, (ConnectionError, TimeoutError))
        or "connection error" in blob
        or "timed out" in blob
        or "timeout" in blob
        or "connection refused" in blob
        or "failed to establish a new connection" in blob
        or "max retries exceeded" in blob
        or "temporary failure in name resolution" in blob
        or "name or service not known" in blob
        or "bad record mac" in blob
        or "sslv3_alert" in blob
        or "ssl:" in blob
        or "broken pipe" in blob
        or "connection reset" in blob
    )


def _classify_llm_error(exc: Exception) -> tuple[str, str] | None:
    """Map a known model-provider exception to ``(title, friendly_body)``.

    Returns ``None`` for unrecognized errors so the caller can fall back to the
    generic error path (full traceback in logs). Recognized errors get a short,
    actionable message instead of a multi-frame traceback dumped to the console.
    The first body line is what the chat UI surfaces, so put the provider detail
    there whenever it helps debugging.
    """
    text = str(exc)
    low = text.lower()
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    exc_name = str(getattr(exc.__class__, "__name__", "") or "")
    exc_mod = str(getattr(exc.__class__, "__module__", "") or "").lower()
    detail = _provider_error_detail(exc)

    is_auth = (
        status == 401
        or "authentication_error" in low
        or "invalid x-api-key" in low
        or "invalid api key" in low
        or "incorrect api key" in low
        or ("unauthorized" in low and "401" in low)
    )
    if is_auth:
        return (
            "Authentication failed",
            f"{detail}\n"
            "Your model provider rejected the API key (401 — invalid or missing).\n"
            "Set a valid key, then re-run your query:\n"
            "  • sandwalk config set llm.anthropic_api_key sk-ant-...\n"
            "  • For Local LLM (oMLX/Ollama/…), set the key on that Local LLM profile in Models\n"
            "  • or run: sandwalk setup",
        )

    is_rate = (
        status == 429
        or "rate_limit" in low
        or "rate limit" in low
        or "overloaded" in low
    )
    if is_rate:
        return (
            "Rate limited",
            f"{detail}\n"
            "The model provider is rate-limiting or overloaded (429).\n"
            "Wait a few seconds and try again.",
        )

    is_not_found = (
        status == 404
        or ("model" in low and "not found" in low)
        or "not_found_error" in low
    )
    if is_not_found:
        return (
            "Model or endpoint not found",
            f"{detail}\n"
            "The configured provider returned 404 (model or endpoint not found).\n"
            "Verify `llm.model` and `llm.openai_base_url` for your selected profile,\n"
            "then retry (you can update via `/models` or `sandwalk setup`).",
        )

    # Billing / quota — check before generic context/token phrases ("max_tokens").
    is_credits = (
        "requires more credits" in low
        or "can only afford" in low
        or "add more credits" in low
        or "insufficient credits" in low
        or "insufficient_quota" in low
        or ("quota" in low and ("exceed" in low or "exceeded" in low))
        or ("payment" in low and ("required" in low or "failed" in low))
    )
    if is_credits:
        return (
            "Provider credits / quota",
            f"{detail}\n"
            "The model provider rejected the request for billing or quota reasons.\n"
            "Add credits at the provider (e.g. openrouter.ai/settings/credits),\n"
            "or lower max output tokens / switch to a cheaper model via `/models`.",
        )

    is_context = (
        "context_length" in low
        or "context length" in low
        or "maximum context" in low
        or "too many tokens" in low
        or "token limit" in low
    )
    if is_context:
        return (
            "Context length exceeded",
            f"{detail}\n"
            "The request exceeded the model's context window.\n"
            "Try a shorter prompt, fewer skills/tools, or a larger-context model.",
        )

    # Stream stall: TCP may still be open while the provider stops sending tokens.
    # Must be checked before the generic timeout/connection bucket.
    is_stream_stall = (
        exc_name == "StreamChunkTimeoutError"
        or "streamchunktimeouterror" in low
        or "no streaming chunk received" in low
        or "stream_chunk_timeout" in low
    )
    if is_stream_stall:
        return (
            "Model stream stalled",
            f"{detail}\n"
            "The provider stopped sending tokens mid-response. Retry, switch models, "
            "or raise/disable `stream_chunk_timeout` / "
            "`LANGCHAIN_OPENAI_STREAM_CHUNK_TIMEOUT_S`.",
        )

    is_conn = _is_transient_transport_error(exc, low)
    if is_conn:
        return (
            "Connection problem",
            f"{detail}\n"
            "Could not reach the model provider. Check your network and retry "
            "(TLS keep-alive often drops after Wi-Fi sleep or an API restart).",
        )

    if "failed to load" in low or "unknown model architecture" in low:
        return (
            "Model failed to load",
            f"{detail}\n"
            "llama.cpp started this model and exited. The weights are installed, "
            "but this build of the llama CLI does not understand that architecture. "
            "Update llama (`llama update`) or pick another model.",
        )

    is_server_unavailable = status in {500, 502, 503, 504} or "service unavailable" in low
    if is_server_unavailable:
        return (
            "Provider unavailable",
            f"{detail}\n"
            "The model provider is temporarily unavailable.\n"
            "Try again shortly, or switch models/providers with `/models`.",
        )

    if "recursion" in low and "limit" in low:
        return (
            "Agent step limit reached",
            "LangGraph hit its internal step safety cap for this run.\n"
            "Retry the task, or split the work into a smaller follow-up prompt.",
        )

    if "thought_signature" in low:
        return (
            "Gemini tool-call signature missing",
            "Gemini requires thought signatures to be preserved across tool rounds.\n"
            "sandwalk now uses the native Google GenAI SDK for Gemini — restart "
            "`sandwalk serve` and retry. If this persists, switch models or update "
            "`langchain-google-genai`.",
        )

    # Keep OpenAI-compatible failures concise (including custom providers like
    # Ollama/LM Studio/proxy gateways) instead of printing deep tracebacks.
    # Include the provider detail so the UI/logs are actionable — the previous
    # opaque one-liner hid 400s (bad params, schema, quota, etc.).
    if (
        exc_mod.startswith("openai")
        or exc_mod.startswith("httpx")
        or "langchain_openai" in exc_mod
        or "langchain_google" in exc_mod
        or "google.genai" in exc_mod
    ):
        return (
            "Model provider request failed",
            f"{detail}\n"
            "Check provider health, `llm.model`, and API key, then retry.",
        )

    return None


def _looks_like_unverified_execution_claim(summary: str, tool_calls: list[dict]) -> bool:
    """Detect likely fabricated execution claims when no tool was actually called."""
    if tool_calls:
        return False
    text = str(summary or "").strip().lower()
    if not text:
        return False

    # Strong signal: model invented concrete identifiers.
    if re.search(r"\b(?:fold|job|workflow|wf)_[a-z0-9]{6,}\b", text):
        return True

    has_submit_claim = any(
        phrase in text for phrase in (
            "successfully submitted",
            "i submitted",
            "i successfully submitted",
            "created the job",
            "created a job",
            "job id:",
            "workflow id:",
        )
    )
    if has_submit_claim:
        return True

    if ("is running" in text or "running with" in text) and any(
        key in text for key in ("job", "workflow", "fold")
    ):
        return True

    return False


def _extract_task_output_paths_from_text(full_text: list[str]) -> dict[str, str]:
    """Best-effort extraction of task output file paths from assistant text."""
    joined = "\n".join(full_text or [])
    pattern = re.compile(r"(?P<path>/\S*/tasks/(?P<task_id>[A-Za-z0-9_-]+)\.output)")
    mapping: dict[str, str] = {}
    for match in pattern.finditer(joined):
        path = str(match.group("path") or "").strip().rstrip(".,;)")
        task_id = str(match.group("task_id") or "").strip()
        if path and task_id:
            mapping[task_id] = path
    return mapping


def _default_local_task_output_path(task_id: str) -> str:
    """Best-guess Claude local task output path for current working dir."""
    try:
        uid = os.getuid()
    except Exception:
        uid = None
    if uid is None:
        return ""
    cwd = Path.cwd().resolve().as_posix()
    sanitized = "-" + cwd.lstrip("/").replace("/", "-")
    return f"/private/tmp/claude-{uid}/{sanitized}/tasks/{task_id}.output"


def _discover_local_task_output_file(task_id: str) -> str:
    """Try to locate a local Claude task output file by task id."""
    if not task_id:
        return ""

    direct = _runner._default_local_task_output_path(task_id)
    if direct and Path(direct).exists():
        return direct

    try:
        uid = os.getuid()
    except Exception:
        return ""

    for root in (Path(f"/private/tmp/claude-{uid}"), Path(f"/tmp/claude-{uid}")):
        if not root.exists():
            continue
        # Common layout: /private/tmp/claude-<uid>/<sanitized-cwd>/tasks/<task_id>.output
        matches = list(root.glob(f"*/tasks/{task_id}.output"))
        if matches:
            return str(matches[0])
    return ""


def _parse_task_probe_json(raw_text: str) -> dict[str, str]:
    """Parse strict JSON map from TaskOutput probe response text."""
    text = str(raw_text or "").strip()
    if not text:
        return {}
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    # Try full text first, then first {...} object slice.
    candidates = [text]
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        candidates.append(m.group(0))

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        out: dict[str, str] = {}
        for k, v in payload.items():
            key = str(k or "").strip()
            val = str(v or "").strip().lower()
            if not key:
                continue
            if val not in {"running", "completed", "failed", "stopped", "unknown"}:
                val = "unknown"
            out[key] = val
        if out:
            return out
    return {}


def _is_warp_terminal_env(env: dict[str, str] | None = None) -> bool:
    """Detect whether current terminal is Warp."""
    source = env if env is not None else os.environ
    term_program = str(source.get("TERM_PROGRAM") or "").lower()
    if "warp" in term_program:
        return True
    if str(source.get("WARP_IS_LOCAL_SHELL_SESSION") or "") == "1":
        return True
    if str(source.get("WARP_SESSION_ID") or "").strip():
        return True
    return False


def _sanitize_notification_text(text: str, max_len: int = 220) -> str:
    """Sanitize text for OSC notification payloads."""
    cleaned = str(text or "").replace("\r", " ").replace("\n", " ").replace(";", ",").strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 3] + "..."
    return cleaned
