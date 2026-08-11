"""Mixin: _activate_compatible_profile."""

from __future__ import annotations

class _CompatibleProfileActivateMixin:
    def _activate_compatible_profile(self, profile_id: str) -> None:
        """Activate a compatible profile and select a model for it."""
        profile = self.session.config.get_openai_profile(profile_id)
        if not profile:
            self.console.print("  [dim]Profile not found.[/dim]")
            return

        backend = str(profile.get("backend") or "").strip().lower() or "other"
        base_url = str(profile.get("base_url") or "").strip()
        current_key = str(profile.get("api_key") or "").strip()
        default_model = str(profile.get("default_model") or "").strip() or "llama3.1"
        profile_label = str(profile.get("label") or profile_id).strip()

        discovered_models = self._fetch_compatible_models(
            base_url,
            backend=backend,
            api_key=current_key or None,
        )
        effective_key = current_key
        while not discovered_models:
            action = self._prompt_discovery_followup_action()
            if action is None or action == "cancel":
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            if action == "manual":
                break
            try:
                retry_key = self._secret_prompt_session.prompt(
                    [("class:prompt", "  New API key [Enter to skip retry]: ")],
                    is_password=True,
                ).strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            if not retry_key:
                self.console.print("  [dim]Retry skipped; keeping current key.[/dim]")
                continue
            effective_key = retry_key
            discovered_models = self._fetch_compatible_models(
                base_url,
                backend=backend,
                api_key=effective_key or None,
            )

        model_id = self._choose_model_from_discovered_tags(discovered_models, default_model)
        if not model_id:
            self.console.print("  [dim]Cancelled.[/dim]")
            return

        self.session.config.upsert_openai_profile(
            profile_id=profile_id,
            api_key=effective_key or None,
            default_model=model_id,
            set_active=True,
        )
        self.session.set_model(model_id, provider="openai")
        self.session.config.set("llm.provider", "openai")
        self.session.config.save()
        key_state = "configured" if (effective_key or "").strip() else "not set"
        self.console.print(
            f"  [green]Switched to {profile_label}[/green] "
            f"[dim]model={model_id} endpoint={base_url} api_key={key_state}[/dim]"
        )
