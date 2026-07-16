"""Mixin: _ensure_llm_ready_for_query."""

from __future__ import annotations

from ui.terminal.model_ids import _is_openai_managed_base_url


class _LlmReadyCheckMixin:
    def _ensure_llm_ready_for_query(self) -> bool:
        """Ensure required provider API key is present; prompt interactively if missing."""
        issue = self.session.config.llm_preflight_issue()
        if not issue:
            return True

        provider = str(self.session.config.get("llm.provider", "anthropic") or "anthropic").strip().lower()

        from agent.config import OPENAI_COMPATIBLE_PROVIDERS

        if provider in OPENAI_COMPATIBLE_PROVIDERS:
            meta = OPENAI_COMPATIBLE_PROVIDERS[provider]
            label = meta["label"]
            self.console.print(f"  [yellow]{issue}[/yellow]")
            self.console.print(
                f"  [dim]Set {meta['env_var']} or enter it now to continue.[/dim]"
            )
            try:
                api_key = self._secret_prompt_session.prompt(
                    [("class:prompt", f"  Enter {label} API key (or press Enter to cancel): ")],
                    is_password=True,
                ).strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print("  [dim]Cancelled.[/dim]")
                return False
            if not api_key:
                self.console.print("  [dim]Cancelled.[/dim]")
                return False
            self.session.config.set(meta["config_key"], api_key)
            self.session.config.save()
            return self.session.config.llm_preflight_issue() is None

        if provider not in {"anthropic", "openai"}:
            self.console.print(f"  [red]{issue}[/red]")
            return False

        self.console.print(f"  [yellow]{issue}[/yellow]")
        if provider == "openai":
            profile = None
            if hasattr(self.session.config, "get_openai_profile"):
                try:
                    profile = self.session.config.get_openai_profile()
                except Exception:
                    profile = None
            if not isinstance(profile, dict):
                profile = None
            profile_id = str((profile or {}).get("id") or "").strip() or None
            profile_label = str((profile or {}).get("label") or "").strip() or "Compatible endpoint"
            profile_backend = str((profile or {}).get("backend") or "").strip().lower()
            openai_base_url = ""
            if hasattr(self.session.config, "llm_openai_base_url"):
                try:
                    base_url_candidate = self.session.config.llm_openai_base_url()
                    if isinstance(base_url_candidate, str):
                        openai_base_url = base_url_candidate.strip()
                except Exception:
                    openai_base_url = ""
            if not openai_base_url:
                openai_base_url = str(self.session.config.get("llm.openai_base_url") or "").strip()
            if not profile_backend and openai_base_url and not _is_openai_managed_base_url(openai_base_url):
                profile_backend = str(
                    self.session.config.get("llm.openai_compatible_backend", "other") or "other"
                ).strip().lower()
            is_compat = bool(openai_base_url) and profile_backend not in {"", "openai"}
            self.console.print(
                "  [dim]Set the API key on this Local LLM profile (Models → Local LLM) or enter it now.[/dim]"
                if is_compat
                else "  [dim]Set OPENAI_API_KEY or enter it now to continue.[/dim]"
            )
            prompt = (
                f"  Enter OpenAI-compatible API key for '{profile_label}' (or press Enter to cancel): "
                if is_compat
                else "  Enter OpenAI API key (or press Enter to cancel): "
            )
            cfg_key = None if is_compat else "llm.openai_api_key"
        else:
            self.console.print(
                "  [dim]Set ANTHROPIC_API_KEY or enter it now to continue.[/dim]"
            )
            prompt = "  Enter Anthropic API key (or press Enter to cancel): "
            cfg_key = "llm.anthropic_api_key"

        try:
            api_key = self._secret_prompt_session.prompt(
                [("class:prompt", prompt)],
                is_password=True,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print("  [dim]Cancelled.[/dim]")
            return False

        if not api_key:
            self.console.print("  [dim]Cancelled.[/dim]")
            return False

        try:
            from agent.config import Config
            if (
                provider == "openai"
                and cfg_key is None
                and isinstance(self.session.config, Config)
            ):
                self.session.config.upsert_openai_profile(
                    profile_id=profile_id,
                    label=profile_label,
                    backend=profile_backend or "other",
                    base_url=openai_base_url or "http://localhost:11434/v1",
                    api_key=api_key,
                    set_active=True,
                )
            else:
                # Cloud OpenAI key (or first-party provider key).
                target_key = cfg_key or "llm.openai_api_key"
                self.session.config.set(target_key, api_key)
        except ValueError as exc:
            self.console.print(f"  [red]{exc}[/red]")
            return False
        self.session.config.save()
        return self.session.config.llm_preflight_issue() is None
