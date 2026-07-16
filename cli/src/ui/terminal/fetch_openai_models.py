"""Mixin: _fetch_openai_models."""

from __future__ import annotations

import json
import urllib.error
import urllib.request


class _FetchOpenaiModelsMixin:
    def _fetch_openai_models(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        quiet: bool = False,
        return_error: bool = False,
    ) -> list[str] | tuple[list[str], str | None]:
        """Fetch model ids from OpenAI-compatible /v1/models."""
        auth_headers = {"Accept": "application/json"}
        if api_key:
            auth_headers["Authorization"] = f"Bearer {api_key}"
        models_url = self._openai_models_url_from_base(base_url)
        req_models = urllib.request.Request(
            url=models_url,
            headers=auth_headers,
            method="GET",
        )
        error_message: str | None = None
        try:
            if quiet:
                with urllib.request.urlopen(req_models, timeout=5.0) as resp:
                    payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
            else:
                with self.console.status("[green]Discovering models from /v1/models...[/green]", spinner="dots"):
                    with urllib.request.urlopen(req_models, timeout=5.0) as resp:
                        payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
            data = payload.get("data") if isinstance(payload, dict) else None
        except urllib.error.HTTPError as exc:
            if not quiet:
                self._report_discovery_http_error("/v1/models", models_url, exc)
                if exc.code in {401, 403}:
                    self.console.print(
                        "  [yellow]/v1/models requires endpoint auth.[/yellow] "
                        "[dim]Check API key if model list is empty.[/dim]"
                    )
            body_raw = self._read_http_error_body(exc)
            body_msg = self._extract_discovery_error_message(body_raw) if body_raw else ""
            reason = str(getattr(exc, "reason", "") or getattr(exc, "msg", "")).strip()
            parts = [f"status={int(getattr(exc, 'code', 0) or 0)}", f"url={models_url}"]
            if reason:
                parts.append(reason)
            if body_msg:
                parts.append(body_msg)
            error_message = " | ".join(parts)
            if return_error:
                return [], error_message
            return []
        except (urllib.error.URLError, TimeoutError) as exc:
            if not quiet:
                self._report_discovery_exception("/v1/models", models_url, exc)
            error_message = str(exc)
            if return_error:
                return [], error_message
            return []
        except Exception as exc:
            if not quiet:
                self._report_discovery_exception("/v1/models", models_url, exc)
            error_message = str(exc)
            if return_error:
                return [], error_message
            return []

        names: list[str] = []
        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or "").strip()
            if model_id and model_id not in names:
                names.append(model_id)
        if names and not quiet:
            self.console.print(f"  [green]Found {len(names)} model(s) from /v1/models.[/green]")
        if return_error:
            return names, error_message
        return names
