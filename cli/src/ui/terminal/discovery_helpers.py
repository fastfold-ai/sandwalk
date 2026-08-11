"""Mixin: _openai_models_url_from_base, _truncate_discovery_detail, _extract_discovery_error_message, _read_http_error_body, _report_discovery_http_error, _report_discovery_exception."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse
import json
import urllib.error
import urllib.request


class _DiscoveryHelpersMixin:
    @staticmethod
    def _openai_models_url_from_base(base_url: str) -> str:
        """Build an OpenAI-compatible /v1/models URL from base URL."""
        parsed = urlparse(str(base_url or "").strip())
        path = (parsed.path or "").rstrip("/")
        if path.endswith("/v1"):
            models_path = f"{path}/models"
        elif path:
            models_path = f"{path}/v1/models"
        else:
            models_path = "/v1/models"
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                models_path,
                "",
                "",
                "",
            )
        )

    @staticmethod
    def _truncate_discovery_detail(text: str, max_chars: int = 320) -> str:
        value = str(text or "").strip()
        if len(value) <= max_chars:
            return value
        return value[:max_chars] + f"... [{len(value)} chars total]"

    @staticmethod
    def _extract_discovery_error_message(raw: str) -> str:
        """Extract a compact human-readable message from API error payloads."""
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

    @staticmethod
    def _read_http_error_body(exc: urllib.error.HTTPError) -> str:
        """Best-effort read of HTTPError response body."""
        try:
            body = exc.read()
        except Exception:
            return ""
        if not body:
            return ""
        return body.decode("utf-8", errors="replace").strip()

    def _report_discovery_http_error(self, endpoint: str, url: str, exc: urllib.error.HTTPError) -> None:
        status = int(getattr(exc, "code", 0) or 0)
        reason = str(getattr(exc, "reason", "") or getattr(exc, "msg", "")).strip()
        body_raw = self._read_http_error_body(exc)
        body_msg = self._extract_discovery_error_message(body_raw)

        self.console.print(
            f"  [yellow]{endpoint} request failed[/yellow] "
            f"[dim](status={status or 'unknown'}, url={url})[/dim]"
        )
        if reason:
            self.console.print(f"  [dim]Reason:[/dim] {reason}")
        if body_msg:
            self.console.print(
                f"  [dim]Response:[/dim] {self._truncate_discovery_detail(body_msg)}",
                markup=False,
            )

    def _report_discovery_exception(self, endpoint: str, url: str, exc: Exception) -> None:
        self.console.print(
            f"  [yellow]{endpoint} request failed[/yellow] [dim](url={url})[/dim]"
        )
        self.console.print(
            f"  [dim]Error:[/dim] {self._truncate_discovery_detail(str(exc))}",
            markup=False,
        )
