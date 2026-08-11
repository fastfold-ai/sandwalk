"""Mixin: _configure_openai_compatible_model_legacy."""

from __future__ import annotations


class _CompatibleModelLegacyMixin:
    def _configure_openai_compatible_model_legacy(self) -> None:
        """Legacy single-endpoint OpenAI-compatible setup for backward compatibility."""
        existing_base_url = (
            str(self.session.config.get("llm.openai_base_url") or "").strip()
            or "http://localhost:11434/v1"
        )
        default_base_url = existing_base_url
        default_model = str(self.session.current_model or "").strip()
        if default_model in {"", "__custom_openai_compatible__"}:
            default_model = "llama3.1"
        current_key = str(
            (self.session.config.get_openai_profile() or {}).get("api_key") or ""
        ).strip()

        self.console.print("\n  [cyan]OpenAI-compatible endpoint setup[/cyan]")
        self.console.print(
            "  [dim]Examples: Ollama, Unsloth, oMLX, DS4, llama.cpp, LM Studio, vLLM, gateway proxies[/dim]"
        )

        backend = self._prompt_openai_compatible_backend(default_base_url)
        if not backend:
            self.console.print("  [dim]Cancelled.[/dim]")
            return
        if backend == "other":
            default_base_url = existing_base_url
        else:
            default_base_url = self._compatible_default_base_url(
                backend,
                fallback=existing_base_url,
            )

        try:
            endpoint_input = self._plain_prompt_session.prompt(
                [("class:prompt", f"  Endpoint base URL [{default_base_url}]: ")],
            ).strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print("  [dim]Cancelled.[/dim]")
            return
        base_url = (endpoint_input or default_base_url).rstrip("/")
        if not base_url:
            self.console.print("  [dim]Cancelled.[/dim]")
            return

        if backend == "ollama":
            default_key = "ollama"
            key_hint = (
                "  API key [(optional) Enter leaves blank; :default uses ollama; :keep keeps existing]: "
            )
        elif backend == "unsloth":
            default_key = current_key or ""
            key_hint = "  API key [Unsloth sk-unsloth-...; Enter leaves blank; :keep keeps existing]: "
        elif backend == "omlx":
            default_key = current_key or ""
            key_hint = "  API key [oMLX; Enter leaves blank; :keep keeps existing]: "
        elif backend == "ds4":
            default_key = current_key or ""
            key_hint = "  API key [DS4 token (optional); Enter leaves blank; :keep keeps existing]: "
        elif backend == "llama_cpp":
            default_key = current_key or ""
            key_hint = "  API key [llama.cpp key (optional); Enter leaves blank; :keep keeps existing]: "
        elif backend == "lm_studio":
            default_key = current_key or ""
            key_hint = "  API key [LM Studio key (optional); Enter leaves blank; :keep keeps existing]: "
        else:
            default_key = current_key or ""
            key_hint = "  API key [optional; Enter leaves blank; :keep keeps existing]: "
        try:
            api_key_input = self._secret_prompt_session.prompt(
                [("class:prompt", key_hint)],
                is_password=True,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print("  [dim]Cancelled.[/dim]")
            return

        effective_key = self._resolve_optional_api_key_input(
            api_key_input,
            existing_key=current_key,
            default_key=default_key,
        )
        discovered_models = self._fetch_compatible_models(
            base_url,
            backend=backend,
            api_key=effective_key or None,
        )
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

        self.session.set_model(model_id, provider="openai")
        profile_id = self.session.config.upsert_openai_profile(
            label=f"{backend} Local" if backend != "other" else "Compatible Endpoint",
            backend=backend,
            base_url=base_url,
            api_key=effective_key or None,
            default_model=model_id,
            set_active=True,
        )
        self.session.config.save()

        key_state = "configured" if effective_key else "not set"
        self.console.print(
            "  [green]Switched to OpenAI-compatible endpoint[/green] "
            f"[dim]profile={profile_id} model={model_id} endpoint={base_url} api_key={key_state}[/dim]"
        )
