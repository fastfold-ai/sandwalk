"""Mixin: /models — interactive model/provider switcher."""

from __future__ import annotations

from ui.terminal.model_options import collect_model_options, is_current_option


class _SwitchModelMixin:
    def _apply_model_selection(self, selected: dict) -> None:
        """Persist a picker selection (modal or numbered list)."""
        from agent.config import Config

        cfg = self.session.config
        provider, _, _ = self._current_provider_status()
        current = self.session.current_model
        active_profile_id = None
        if isinstance(cfg, Config):
            active_profile_id = cfg.active_openai_profile_id()

        selected_provider = str(selected.get("provider") or "")
        model_id = str(selected.get("model_id") or "")
        display = str(selected.get("display") or model_id)
        selected_profile_id = str(selected.get("profile_id") or "").strip() or None
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

        if isinstance(cfg, Config):
            cfg.push_recent_model(
                model_id,
                selected_provider,
                profile_id=selected_profile_id,
            )

        self.session.config.save()
        self.console.print(
            f"  [green]Switched to {display}[/green] ({model_id}) "
            f"[dim]provider={selected_provider}[/dim]"
        )

    def _switch_model(self):
        """Interactive model switcher (in-app modal, else numbered list)."""
        from agent.config import Config

        # Prefer in-app / nested modal.
        host = getattr(self, "_models_modal_host", None)
        app = getattr(self, "_transcript_app", None)
        if host is not None and getattr(app, "is_running", False):
            host.open()
            return
        try:
            from ui.terminal.models_modal import run_models_modal

            if run_models_modal(self):
                return
        except Exception:  # noqa: BLE001
            pass

        provider, provider_label, provider_endpoint = self._current_provider_status()
        cfg = self.session.config
        models_with_provider, profile_discovery_warnings = collect_model_options(self)

        current = self.session.current_model
        active_profile_id = None
        active_backend = ""
        if isinstance(cfg, Config):
            active_profile_id = cfg.active_openai_profile_id()
            profile = cfg.get_openai_profile(active_profile_id)
            active_backend = str((profile or {}).get("backend") or "").strip().lower()

        compat_backend = self._current_compatible_backend_label()
        backend_suffix = f" ({compat_backend})" if compat_backend else ""
        self.console.print(
            f"\n  [cyan]Current model:[/cyan] {self._model_display_name()}{backend_suffix} ({current})"
        )
        self.console.print(f"  [cyan]Provider:[/cyan] {provider_label}{backend_suffix}")
        if provider_endpoint:
            self.console.print(f"  [cyan]Endpoint:[/cyan] {provider_endpoint}")
        self.console.print()

        if not models_with_provider:
            self.console.print("  [yellow]No model options configured[/yellow]")
            return

        from ui.terminal.models_modal import (
            _context_label_for_option,
            _effort_label_for_option,
        )

        for i, option in enumerate(models_with_provider, 1):
            model_id = str(option.get("model_id") or "")
            display = str(option.get("display") or model_id)
            profile_id = str(option.get("profile_id") or "").strip() or None
            backend = str(option.get("backend") or "").strip().lower()
            is_current = is_current_option(
                option,
                current_model=current,
                current_provider=str(provider or ""),
                active_profile_id=active_profile_id,
                active_backend=active_backend,
            )
            marker = " [green]*[/green]" if is_current else "  "
            if profile_id:
                provider_hint = self._compatible_backend_display_name(backend)
            else:
                provider_hint = str(
                    option.get("provider_label") or option.get("provider") or ""
                )
            fav = ""
            if isinstance(cfg, Config) and cfg.is_model_favorite(
                model_id,
                str(option.get("provider") or ""),
                profile_id=profile_id,
            ):
                fav = "★ "
            ctx = _context_label_for_option(option)
            effort = _effort_label_for_option(
                option, cfg if isinstance(cfg, Config) else None
            )
            ctx_bit = f" [dim]{ctx}[/dim]" if ctx else ""
            right = effort or provider_hint
            self.console.print(
                f"  {marker} [{i}] {fav}{display}{ctx_bit} [dim]{right}[/dim]"
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

        self._apply_model_selection(models_with_provider[int(choice) - 1])
