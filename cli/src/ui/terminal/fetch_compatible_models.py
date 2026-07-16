"""Mixin: _fetch_ollama_tags, _fetch_compatible_models, _prompt_discovery_followup_action."""

from __future__ import annotations

import json
import urllib.error
import urllib.request


class _FetchCompatibleModelsMixin:
    def _fetch_ollama_tags(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        quiet: bool = False,
        return_error: bool = False,
    ) -> list[str] | tuple[list[str], str | None]:
        """Fetch model names from Ollama /api/tags."""
        auth_headers = {"Accept": "application/json"}
        if api_key:
            auth_headers["Authorization"] = f"Bearer {api_key}"
        tags_url = self._ollama_tags_url_from_base(base_url)
        req_tags = urllib.request.Request(
            url=tags_url,
            headers=auth_headers,
            method="GET",
        )
        error_message: str | None = None
        try:
            if quiet:
                with urllib.request.urlopen(req_tags, timeout=5.0) as resp:
                    payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
            else:
                with self.console.status("[green]Discovering models from /api/tags...[/green]", spinner="dots"):
                    with urllib.request.urlopen(req_tags, timeout=5.0) as resp:
                        payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
        except urllib.error.HTTPError as exc:
            if not quiet:
                self._report_discovery_http_error("/api/tags", tags_url, exc)
            body_raw = self._read_http_error_body(exc)
            body_msg = self._extract_discovery_error_message(body_raw) if body_raw else ""
            reason = str(getattr(exc, "reason", "") or getattr(exc, "msg", "")).strip()
            parts = [f"status={int(getattr(exc, 'code', 0) or 0)}", f"url={tags_url}"]
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
                self._report_discovery_exception("/api/tags", tags_url, exc)
            error_message = str(exc)
            if return_error:
                return [], error_message
            return []
        except Exception as exc:
            if not quiet:
                self._report_discovery_exception("/api/tags", tags_url, exc)
            error_message = str(exc)
            if return_error:
                return [], error_message
            return []

        models = payload.get("models") if isinstance(payload, dict) else None
        names: list[str] = []
        for item in models if isinstance(models, list) else []:
            if not isinstance(item, dict):
                continue
            raw = item.get("name") or item.get("model")
            name = str(raw or "").strip()
            if name and name not in names:
                names.append(name)
        if names and not quiet:
            self.console.print(f"  [green]Found {len(names)} model(s) from /api/tags.[/green]")
        if return_error:
            return names, error_message
        return names

    def _fetch_compatible_models(
        self,
        base_url: str,
        backend: str,
        api_key: str | None = None,
        *,
        quiet: bool = False,
    ) -> list[str]:
        """Discover models based on selected endpoint type."""
        backend_type = str(backend or "").strip().lower()
        if backend_type in {"unsloth", "omlx", "ds4", "llama_cpp", "lm_studio"}:
            names = self._fetch_openai_models(base_url, api_key=api_key, quiet=quiet)
        elif backend_type == "ollama":
            names = self._fetch_ollama_tags(base_url, api_key=api_key, quiet=quiet)
            if not names:
                names = self._fetch_openai_models(base_url, api_key=api_key, quiet=quiet)
        else:
            names = self._fetch_openai_models(base_url, api_key=api_key, quiet=quiet)
            if not names:
                names = self._fetch_ollama_tags(base_url, api_key=api_key, quiet=quiet)

        if names:
            return names
        if not quiet:
            self.console.print(
                "  [yellow]No models found from discovery endpoint(s).[/yellow] "
                "[dim]You can still enter a model manually.[/dim]"
            )
        return []

    def _prompt_discovery_followup_action(self) -> str | None:
        """Prompt next step after model discovery returns no results."""
        self.console.print("  [cyan]Model discovery options[/cyan]")
        self.console.print("    [1] Retry discovery with a new API key")
        self.console.print("    [2] Enter model ID manually")
        self.console.print("    [3] Cancel")
        try:
            raw = self._plain_prompt_session.prompt(
                [("class:prompt", "  Select option [2]: ")],
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        if raw in {"1", "retry", "r"}:
            return "retry"
        if raw in {"3", "cancel", "c", "q"}:
            return "cancel"
        if raw in {"", "2", "manual", "m"}:
            return "manual"
        self.console.print("  [dim]Invalid selection; switching to manual model entry.[/dim]")
        return "manual"
