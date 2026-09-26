"""Harden outbound LLM HTTP so stale TLS keep-alives cannot fail a turn.

``SSLV3_ALERT_BAD_RECORD_MAC`` shows up on macOS when httpx reuses a
keep-alive socket after Wi-Fi sleep, an API restart, or IPv6/IPv4 flip.
OpenAI and Anthropic both retry that *same* pooled connection, so the
turn still dies. Disable keep-alive, skip TLS tickets, and prefer IPv4
on Darwin.
"""

from __future__ import annotations

import os
import ssl
import sys
from typing import Any

_INSTALLED = False


def _tls_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    no_ticket = getattr(ssl, "OP_NO_TICKET", 0)
    if no_ticket:
        ctx.options |= no_ticket
    return ctx


def _force_ipv4() -> bool:
    if os.environ.get("SANDWALK_LLM_IPV4", "1").strip() == "0":
        return False
    return sys.platform == "darwin"


def _stable_limits(existing: Any | None) -> Any:
    import httpx

    max_conn = 40
    if existing is not None:
        max_conn = int(getattr(existing, "max_connections", 40) or 40)
    return httpx.Limits(max_keepalive_connections=0, max_connections=max_conn)


def install_stable_tls_httpx() -> None:
    """Patch httpx clients used by OpenAI / Anthropic / OpenRouter SDKs."""
    global _INSTALLED
    if _INSTALLED:
        return

    import httpx

    orig_sync = httpx.Client.__init__
    orig_async = httpx.AsyncClient.__init__

    def _prepare(kwargs: dict[str, Any], *, async_client: bool) -> dict[str, Any]:
        next_kwargs = dict(kwargs)
        limits = _stable_limits(next_kwargs.get("limits"))
        next_kwargs["limits"] = limits
        next_kwargs.setdefault("http2", False)
        verify = next_kwargs.get("verify", True)
        if verify is True:
            verify = _tls_context()
            next_kwargs["verify"] = verify
        if (
            _force_ipv4()
            and "transport" not in next_kwargs
            and "mounts" not in next_kwargs
        ):
            transport_cls = (
                httpx.AsyncHTTPTransport if async_client else httpx.HTTPTransport
            )
            next_kwargs["transport"] = transport_cls(
                verify=verify,
                retries=1,
                http1=True,
                http2=False,
                limits=limits,
                local_address="0.0.0.0",
            )
        return next_kwargs

    def sync_init(self, *args: Any, **kwargs: Any) -> None:
        orig_sync(self, *args, **_prepare(kwargs, async_client=False))

    def async_init(self, *args: Any, **kwargs: Any) -> None:
        orig_async(self, *args, **_prepare(kwargs, async_client=True))

    httpx.Client.__init__ = sync_init  # type: ignore[method-assign]
    httpx.AsyncClient.__init__ = async_init  # type: ignore[method-assign]
    _INSTALLED = True
