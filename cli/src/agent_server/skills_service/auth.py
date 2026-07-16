"""skills.sh Vercel OIDC token acquisition/refresh and authenticated fetch.

Looks up ``urlopen`` via a lazy self-import (not a direct
``from urllib.request import urlopen`` call site) so tests that monkeypatch
``agent_server.skills_service.urlopen`` are honored, matching this module's
behavior from before the split.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

from agent.config import Config

SKILLS_SH_BASE_URL = "https://skills.sh"


class AuthMixin:
    @staticmethod
    def _jwt_expired(token: str, *, skew_seconds: int = 120) -> bool:
        """Return True when a JWT looks past expiry (Vercel OIDC lasts ~12h)."""
        try:
            import base64
            import time

            parts = token.split(".")
            if len(parts) != 3:
                return False
            payload_b64 = parts[1]
            pad = "=" * ((4 - len(payload_b64) % 4) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
            exp = payload.get("exp")
            if not isinstance(exp, (int, float)):
                return False
            return time.time() >= float(exp) - skew_seconds
        except Exception:
            return False

    @classmethod
    def _refresh_vercel_oidc_token(cls) -> str:
        """Pull a fresh VERCEL_OIDC_TOKEN via the linked Vercel CLI project."""
        from agent.config import sync_process_env_from_config
        from agent_server.integrations_service import IntegrationsService

        workspace = IntegrationsService._vercel_workspace_dir()
        token, err = IntegrationsService._fetch_vercel_oidc_token_via_cli(workspace)
        token = str(token or "").strip()
        if not token:
            detail = f" {err}" if err else ""
            raise RuntimeError(
                "skills.sh authentication required. Open Integrations → Vercel "
                "and run setup (vercel login / link / env pull), or set "
                f"VERCEL_OIDC_TOKEN.{detail}"
            )
        config = Config.load()
        config.set("api.vercel_oidc_token", token)
        config.save()
        os.environ["VERCEL_OIDC_TOKEN"] = token
        sync_process_env_from_config(config)
        return token

    @classmethod
    def _skills_sh_token(cls, *, force_refresh: bool = False) -> str:
        if force_refresh:
            return cls._refresh_vercel_oidc_token()

        config = Config.load()
        config_token = str(config.get("api.vercel_oidc_token") or "").strip()
        token = str(
            os.environ.get("VERCEL_OIDC_TOKEN")
            or config_token
            or ""
        ).strip()
        if token and not cls._jwt_expired(token):
            return token
        # Missing or expired (~12h) — refresh via Vercel CLI when linked.
        try:
            return cls._refresh_vercel_oidc_token()
        except RuntimeError:
            if token:
                raise RuntimeError(
                    "Vercel OIDC token expired and could not be refreshed. "
                    "Open Integrations → Vercel and run setup again."
                ) from None
            raise RuntimeError(
                "Vercel integration is not configured. Open Integrations → Vercel "
                "and run setup, or set VERCEL_OIDC_TOKEN."
            ) from None

    def _skills_sh_request_json(
        self,
        endpoint: str,
        *,
        operation: str,
        _retried: bool = False,
    ) -> dict[str, Any]:
        from agent_server import skills_service as _skills_service

        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {self._skills_sh_token()}",
        }
        request = Request(endpoint, headers=headers, method="GET")
        try:
            with _skills_service.urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 401:
                if not _retried:
                    try:
                        self._skills_sh_token(force_refresh=True)
                    except RuntimeError as refresh_exc:
                        raise RuntimeError(str(refresh_exc)) from exc
                    return self._skills_sh_request_json(
                        endpoint, operation=operation, _retried=True
                    )
                raise RuntimeError(
                    "skills.sh authentication failed (token rejected). "
                    "Open Integrations → Vercel and refresh setup."
                ) from exc
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="ignore").strip()
            except Exception:
                detail = ""
            if exc.code == 404:
                raise LookupError(detail or "Not found.") from exc
            suffix = f" {detail}" if detail else ""
            raise RuntimeError(f"{operation} failed ({exc.code}).{suffix}") from exc
        except URLError as exc:
            raise RuntimeError(f"{operation} is unavailable.") from exc
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"{operation} returned an invalid response.") from exc

        if not isinstance(payload, dict):
            raise RuntimeError(f"{operation} returned an invalid response.")
        return payload
