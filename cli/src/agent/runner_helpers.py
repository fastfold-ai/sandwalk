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


def _provider_error_detail(exc: Exception, *, limit: int = 240) -> str:
    """Return a single-line, truncated provider error for UI/logs."""
    text = " ".join(str(exc).split())
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def _classify_llm_error(exc: Exception) -> tuple[str, str] | None:
    """Map a known model-provider exception to ``(title, friendly_body)``.

    Returns ``None`` for unrecognized errors so the caller can fall back to the
    generic error path (full traceback in logs). Recognized errors get a short,
    actionable message instead of a multi-frame traceback dumped to the console.
    """
    text = str(exc)
    low = text.lower()
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
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
            "The configured provider returned 404 (model or endpoint not found).\n"
            "Verify `llm.model` and `llm.openai_base_url` for your selected profile,\n"
            "then retry (you can update via `/model` or `sandwalk setup`).",
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
            "The request exceeded the model's context window.\n"
            f"Provider detail: {detail}\n"
            "Try a shorter prompt, fewer skills/tools, or a larger-context model.",
        )

    is_conn = (
        isinstance(exc, (ConnectionError, TimeoutError))
        or "connection error" in low
        or "timed out" in low
        or "timeout" in low
        or "connection refused" in low
        or "failed to establish a new connection" in low
        or "max retries exceeded" in low
        or "temporary failure in name resolution" in low
        or "name or service not known" in low
    )
    if is_conn:
        return (
            "Connection problem",
            "Could not reach the model provider.\n"
            "Check your network connection and try again.",
        )

    is_server_unavailable = status in {500, 502, 503, 504} or "service unavailable" in low
    if is_server_unavailable:
        return (
            "Provider unavailable",
            "The model provider is temporarily unavailable.\n"
            "Try again shortly, or switch models/providers with `/model`.",
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
