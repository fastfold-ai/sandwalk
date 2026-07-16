"""Mixin: _handle_sandbox_command, _handle_keys_command, _compatible_models_path_label."""

from __future__ import annotations

class _SandboxKeysCommandsMixin:
    def _handle_sandbox_command(self, query: str) -> None:
        """Handle /sandbox — toggle Local Sandbox vs Modal Sandbox."""
        from agent.sandbox_manage import handle_sandbox_argv

        parts = query.strip().split()
        handle_sandbox_argv(parts or ["status"], self.console)
        self._refresh_cli_sandbox_label()

    def _handle_keys_command(self, query: str) -> None:
        """Handle /keys with optional compatible-profile actions."""
        from agent.config import Config

        cfg = getattr(self.session, "config", None) or Config.load()
        parts = query.strip().split()
        if len(parts) <= 1:
            self.console.print(cfg.keys_table())
            return

        action = str(parts[1] or "").strip().lower()
        if action in {"profile", "use", "select"}:
            profile_id = self._prompt_select_compatible_profile_id(
                cfg=cfg,
                allow_create=False,
            )
            if not profile_id:
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            try:
                cfg.set_openai_active_profile(profile_id)
            except ValueError as exc:
                self.console.print(f"  [red]{exc}[/red]")
                return
            cfg.save()
            self.session.config = cfg
            self.console.print(f"  [green]Active compatible profile:[/green] {profile_id}")
            self.console.print(cfg.keys_table())
            return

        if action in {"set-compatible", "set", "update"}:
            profile_id_arg = str(parts[2] or "").strip() if len(parts) > 2 else ""
            if profile_id_arg:
                profile_id = profile_id_arg
            else:
                active_profile = cfg.get_openai_profile()
                active_backend = str((active_profile or {}).get("backend") or "").strip().lower()
                if active_backend and active_backend != "openai":
                    profile_id = str((active_profile or {}).get("id") or "").strip()
                else:
                    profile_id = self._prompt_select_compatible_profile_id(
                        cfg=cfg,
                        allow_create=False,
                    )
            if not profile_id:
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            profile = cfg.get_openai_profile(profile_id)
            if not profile or str(profile.get("backend") or "").strip().lower() == "openai":
                self.console.print("  [yellow]Select a compatible profile (not OpenAI Cloud).[/yellow]")
                return
            label = str(profile.get("label") or profile_id).strip()
            current_preview = str(profile.get("api_key") or "").strip()
            current_state = "configured" if current_preview else "not set"
            self.console.print(
                f"  [cyan]Update API key for {label}[/cyan] [dim](currently {current_state})[/dim]"
            )
            try:
                api_key_input = self._secret_prompt_session.prompt(
                    [("class:prompt", "  New API key [Enter clears key; :keep keeps existing]: ")],
                    is_password=True,
                ).strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            api_key = self._resolve_optional_api_key_input(
                api_key_input,
                existing_key=current_preview,
                default_key=current_preview,
            )
            cfg.upsert_openai_profile(
                profile_id=profile_id,
                api_key=api_key,
                set_active=True,
            )
            cfg.save()
            self.session.config = cfg
            if api_key:
                self.console.print(f"  [green]Updated key for profile:[/green] {label}")
            else:
                self.console.print(f"  [green]Cleared key for profile:[/green] {label}")
            self.console.print(cfg.keys_table())
            return

        if action in {"set-boltz", "boltz", "set-boltz-key"}:
            self._handle_set_boltz_key(cfg)
            return

        self.console.print(
            "  [dim]Usage:[/dim] /keys  |  /keys profile  |  /keys set-compatible [profile_id]  |  /keys set-boltz"
        )
        self.console.print(cfg.keys_table())

    @staticmethod
    def _compatible_models_path_label(backend: str) -> str:
        """Return discovery path(s) used for a compatible backend."""
        backend_type = str(backend or "").strip().lower()
        if backend_type in {"unsloth", "omlx", "ds4", "llama_cpp", "lm_studio"}:
            return "/v1/models"
        if backend_type == "ollama":
            return "/api/tags -> /v1/models"
        return "/v1/models -> /api/tags"
