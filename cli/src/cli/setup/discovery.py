"""URL-building and error-reporting helpers for compatible-endpoint discovery."""

import json
import urllib.error
from urllib.parse import urlparse

from cli.app import console


def _ollama_tags_url_from_base(base_url: str) -> str:
    """Build an Ollama /api/tags URL from an OpenAI-compatible base URL."""
    parsed = urlparse(str(base_url or "").strip())
    path = (parsed.path or "").rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3]
    tags_path = f"{path}/api/tags" if path else "/api/tags"
    return parsed._replace(path=tags_path, query="", fragment="").geturl()


def _openai_models_url_from_base(base_url: str) -> str:
    """Build a /v1/models URL from an OpenAI-compatible base URL."""
    parsed = urlparse(str(base_url or "").strip())
    path = (parsed.path or "").rstrip("/")
    if not path.endswith("/v1"):
        path = f"{path}/v1" if path else "/v1"
    models_path = f"{path}/models"
    return parsed._replace(path=models_path, query="", fragment="").geturl()


def _truncate_discovery_detail(text: str, max_chars: int = 320) -> str:
    value = str(text or "").strip()
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + f"... [{len(value)} chars total]"


def _extract_discovery_error_message(raw: str) -> str:
    """Extract concise API error messages from JSON payloads when available."""
    value = str(raw or "").strip()
    if not value:
        return ""
    try:
        payload = json.loads(value)
    except Exception:
        return value

    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            msg = str(err.get("message") or err.get("detail") or "").strip()
            code = str(err.get("code") or "").strip()
            if msg:
                return f"{msg} (code={code})" if code else msg
        for key in ("message", "detail", "description", "error_description"):
            msg = payload.get(key)
            if isinstance(msg, str) and msg.strip():
                return msg.strip()
    return value


def _read_http_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read()
    except Exception:
        return ""
    if not body:
        return ""
    return body.decode("utf-8", errors="replace").strip()


def _report_discovery_http_error(endpoint: str, url: str, exc: urllib.error.HTTPError) -> None:
    status = int(getattr(exc, "code", 0) or 0)
    reason = str(getattr(exc, "reason", "") or getattr(exc, "msg", "")).strip()
    body_raw = _read_http_error_body(exc)
    body_msg = _extract_discovery_error_message(body_raw)

    console.print(
        f"  [yellow]{endpoint} request failed[/yellow] "
        f"[dim](status={status or 'unknown'}, url={url})[/dim]"
    )
    if reason:
        console.print(f"  [dim]Reason:[/dim] {reason}")
    if body_msg:
        console.print(
            f"  [dim]Response:[/dim] {_truncate_discovery_detail(body_msg)}",
            markup=False,
        )


def _report_discovery_exception(endpoint: str, url: str, exc: Exception) -> None:
    console.print(f"  [yellow]{endpoint} request failed[/yellow] [dim](url={url})[/dim]")
    console.print(
        f"  [dim]Error:[/dim] {_truncate_discovery_detail(str(exc))}",
        markup=False,
    )


