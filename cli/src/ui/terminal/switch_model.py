"""Mixin: _switch_model — interactive model/provider switcher."""

from __future__ import annotations

from .model_ids import AVAILABLE_MODELS


class _SwitchModelMixin:
    def _switch_model(self):
        """Interactive model switcher."""
        from agent.config import Config

        provider, provider_label, provider_endpoint = self._current_provider_status()
        cfg = self.session.config
        # Match the web UI: only show models enabled in Dashboard → Models
        # (hidden ones are managed there and re-enabled from the same place).
        hidden_models: set[str] = set()
        if isinstance(cfg, Config):
            try:
                hidden_models = set(cfg.hidden_models())
            except Exception:
                hidden_models = set()

        models_with_provider: list[dict[str, str | None]] = []
        profile_discovery_warnings: list[str] = []
        for prov, models in AVAILABLE_MODELS.items():
            for model_id, display, desc in models:
                if model_id == "__custom_openai_compatible__":
                    # Profile management moved to /model-manager.
                    continue
                # Provider-scoped hide: moonshot:kimi-k3 must not hide opencode.
                if isinstance(cfg, Config):
                    if cfg.is_model_hidden(model_id, prov):
                        continue
                elif model_id in hidden_models:
                    continue
                models_with_provider.append(
                    {
                    "provider": prov,
                    "model_id": model_id,
                    "display": display,
                    "desc": desc,
                    "profile_id": None,
                    }
                )

        # Discover live catalogs for first-party proxy providers (OpenCode Go)
        # when an API key is configured — same behavior as the Models dashboard.
        if isinstance(cfg, Config):
            from agent.config import OPENAI_COMPATIBLE_PROVIDERS
            from agent.model_catalog import (
                format_discovered_model_label,
                opencode_model_is_supported,
            )
            from agent.model_discovery import probe_compatible_profile

            # Same bare id may appear under multiple providers (Zen + Moonshot).
            existing_keys = {
                (
                    str(item.get("provider") or ""),
                    str(item.get("model_id") or ""),
                )
                for item in models_with_provider
            }
            for prov, meta in OPENAI_COMPATIBLE_PROVIDERS.items():
                if str(meta.get("discover_models") or "").strip().lower() not in {
                    "1",
                    "true",
                    "yes",
                }:
                    continue
                api_key = cfg.llm_api_key(prov)
                if not api_key:
                    continue
                base_url = str(meta.get("base_url") or "").strip()
                if not base_url:
                    continue
                label = str(meta.get("label") or prov)
                probe = probe_compatible_profile(
                    base_url=base_url,
                    backend="other",
                    api_key=api_key,
                )
                discovered_models = list(probe.get("models") or [])
                if not discovered_models:
                    fallback = str(meta.get("default_model") or "").strip()
                    if fallback:
                        discovered_models = [fallback]
                for model_id in discovered_models:
                    if prov == "opencode" and not opencode_model_is_supported(model_id):
                        continue
                    key = (prov, model_id)
                    if key in existing_keys or cfg.is_model_hidden(model_id, prov):
                        continue
                    existing_keys.add(key)
                    models_with_provider.append(
                        {
                            "provider": prov,
                            "model_id": model_id,
                            "display": format_discovered_model_label(model_id),
                            "desc": f"{label} (discovered)",
                            "profile_id": None,
                        }
                    )

        if isinstance(cfg, Config):
            compatible_profiles = cfg.openai_profiles(include_cloud=False)
            for profile_id, profile in sorted(
                compatible_profiles.items(),
                key=lambda item: str(item[1].get("label") or item[0]).strip().lower(),
            ):
                backend = str(profile.get("backend") or "other").strip().lower()
                base_url = str(profile.get("base_url") or "").strip()
                if not base_url:
                    continue
                profile_label = str(profile.get("label") or profile_id).strip()
                api_key = str(profile.get("api_key") or "").strip() or None
                discovered_models = self._fetch_compatible_models(
                    base_url,
                    backend=backend,
                    api_key=api_key,
                    quiet=True,
                )
                if not discovered_models:
                    backend_label = self._compatible_backend_display_name(backend)
                    issue = ""
                    probe = self._probe_compatible_profile(
                        base_url=base_url,
                        backend=backend,
                        api_key=api_key,
                    )
                    if isinstance(probe, dict):
                        issue = str(probe.get("error") or "").strip()
                    if issue:
                        profile_discovery_warnings.append(
                            f"{profile_label} ({backend_label}): {issue}"
                        )
                    else:
                        profile_discovery_warnings.append(
                            f"{profile_label} ({backend_label}): no models discovered"
                        )
                if not discovered_models and profile_id == cfg.active_openai_profile_id():
                    fallback_model = str(profile.get("default_model") or "").strip()
                    if fallback_model:
                        discovered_models = [fallback_model]
                for discovered_model in discovered_models:
                    models_with_provider.append(
                        {
                            "provider": "local",
                            "model_id": discovered_model,
                            "display": f"{profile_label}: {discovered_model}",
                            "desc": f"{backend} profile model",
                            "profile_id": profile_id,
                            "backend": backend,
                        }
                    )

        current = self.session.current_model
        active_profile_id = None
        active_openai_profile = None
        if isinstance(cfg, Config):
            active_profile_id = cfg.active_openai_profile_id()
            active_openai_profile = cfg.get_openai_profile(active_profile_id)
        active_backend = str((active_openai_profile or {}).get("backend") or "").strip().lower()

        compat_backend = self._current_compatible_backend_label()
        backend_suffix = f" ({compat_backend})" if compat_backend else ""
        self.console.print(
            f"\n  [cyan]Current model:[/cyan] {self._model_display_name()}{backend_suffix} ({current})"
        )
        self.console.print(f"  [cyan]Provider:[/cyan] {provider_label}{backend_suffix}\n")
        if provider_endpoint:
            self.console.print(f"  [cyan]Endpoint:[/cyan] {provider_endpoint}\n")

        if not models_with_provider:
            self.console.print("  [yellow]No model options configured[/yellow]")
            return

        for i, option in enumerate(models_with_provider, 1):
            prov = str(option.get("provider") or "")
            model_id = str(option.get("model_id") or "")
            display = str(option.get("display") or model_id)
            desc = str(option.get("desc") or "")
            profile_id = str(option.get("profile_id") or "").strip() or None
            backend = str(option.get("backend") or "").strip().lower()
            is_current = False
            if model_id == current and str(provider).strip().lower() == prov:
                if profile_id:
                    is_current = profile_id == (active_profile_id or "")
                elif prov == "openai":
                    is_current = active_backend in {"", "openai"}
                else:
                    is_current = True
            marker = " [green]*[/green]" if is_current else "  "
            if profile_id:
                provider_hint = self._compatible_backend_display_name(backend)
            else:
                provider_hint = prov
            self.console.print(
                f"  {marker} [{i}] {display} [dim]({provider_hint})[/dim] — [dim]{desc}[/dim]"
            )

        if profile_discovery_warnings:
            self.console.print(
                "  Warning: some compatible providers are unhealthy or returned no models.",
                style="yellow",
            )
            for warning in profile_discovery_warnings[:3]:
                self.console.print(
                    f"    - {self._truncate_discovery_detail(warning, max_chars=160)}",
                    style="dim",
                    markup=False,
                )
            remaining = len(profile_discovery_warnings) - 3
            if remaining > 0:
                self.console.print(
                    f"    - (+{remaining} more profiles)",
                    style="dim",
                    markup=False,
                )
            self.console.print(
                "    Run /model-manager to inspect health and provider config.",
                style="dim",
                markup=False,
            )

        self.console.print()

        try:
            choice = self._prompt_session.prompt(
                [("class:prompt", "  Select model (number): ")],
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return

        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(models_with_provider):
            self.console.print("  [dim]Cancelled.[/dim]")
            return

        idx = int(choice) - 1
        selected = models_with_provider[idx]
        selected_provider = str(selected.get("provider") or "")
        model_id = str(selected.get("model_id") or "")
        display = str(selected.get("display") or model_id)
        selected_profile_id = str(selected.get("profile_id") or "").strip() or None
        # Catalog labels local profile models as "local"; runtime still uses openai.
        runtime_provider = "openai" if selected_provider == "local" else selected_provider

        same_model = model_id == current and str(provider).strip().lower() == runtime_provider
        same_profile = True
        if selected_profile_id and isinstance(cfg, Config):
            same_profile = selected_profile_id == (active_profile_id or "")
        if same_model and same_profile:
            self.console.print(f"  [dim]Already using {display}.[/dim]")
            return

        self.session.set_model(model_id, provider=runtime_provider)
        if runtime_provider == "openai":
            # Built-in OpenAI models should use the cloud profile by default.
            if isinstance(cfg, Config):
                if selected_profile_id:
                    cfg.set_openai_active_profile(selected_profile_id)
                    cfg.upsert_openai_profile(
                        profile_id=selected_profile_id,
                        default_model=model_id,
                    )
                else:
                    cfg.set_openai_active_profile("openai_cloud")
            else:
                self.session.config.unset("llm.openai_base_url")
                self.session.config.unset("llm.openai_compatible_backend")
        self.session.config.save()  # Persist to ~/.sandwalk/config.json
        self.console.print(
            f"  [green]Switched to {display}[/green] ({model_id}) [dim]provider={selected_provider}[/dim]"
        )
        # Prompt Effort / Fast when the model supports thinking controls.
        if isinstance(cfg, Config):
            self._prompt_and_save_model_effort(
                cfg,
                provider=selected_provider,
                model_id=model_id,
                display=display,
            )
