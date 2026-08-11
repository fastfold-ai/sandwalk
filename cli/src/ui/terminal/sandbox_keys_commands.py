"""Mixin: _handle_sandbox_command, _handle_keys_command, _compatible_models_path_label."""

from __future__ import annotations


class _SandboxKeysCommandsMixin:
    def _handle_sandbox_command(self, query: str) -> None:
        """Handle /sandbox — picker (like /models) or explicit args."""
        from agent.sandbox_manage import handle_sandbox_argv

        parts = query.strip().split()
        # Bare `/sandbox` opens the same style of numbered picker as `/models`.
        if len(parts) <= 1:
            self._pick_sandbox()
            return
        handle_sandbox_argv(parts, self.console)
        self._refresh_cli_sandbox_label()

    def _pick_sandbox(self) -> None:
        """Interactive sandbox picker matching the web UI Local / Modal presets."""
        from agent.config import Config
        from agent.sandbox_presets import (
            apply_sandbox_pick,
            current_sandbox_pick_index,
            format_current_sandbox_summary,
            sandbox_pick_options,
        )
        from ui.terminal.sandbox_modal import run_sandbox_modal

        host = getattr(self, "_sandbox_modal_host", None)
        app = getattr(self, "_transcript_app", None)
        if host is not None and getattr(app, "is_running", False):
            host.open()
            return
        if run_sandbox_modal(self):
            return

        cfg = getattr(self.session, "config", None) or Config.load()
        options = sandbox_pick_options()
        current_idx = current_sandbox_pick_index(cfg, options)

        self.console.print(
            f"\n  [cyan]Current sandbox:[/cyan] {format_current_sandbox_summary(cfg)}\n"
        )
        for i, option in enumerate(options, 1):
            marker = " [green]*[/green]" if current_idx == i - 1 else "  "
            self.console.print(
                f"  {marker} [{i}] {option.label} [dim]— {option.detail}[/dim]"
            )
        self.console.print()

        try:
            choice = self._prompt_session.prompt(
                [("class:prompt", "  Select sandbox (number): ")],
            ).strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print("  [dim]Cancelled.[/dim]")
            return

        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(options):
            self.console.print("  [dim]Cancelled.[/dim]")
            return

        selected = options[int(choice) - 1]
        already = current_idx is not None and int(choice) - 1 == current_idx
        if already and selected.kind == "builtin":
            self.console.print(f"  [dim]Already using {selected.label}.[/dim]")
            return

        if not already:
            try:
                label = apply_sandbox_pick(selected, cfg)
            except RuntimeError as exc:
                self.console.print(f"  [red]{exc}[/red]")
                return
            self.session.config = cfg
            self._refresh_cli_sandbox_label()
            self.console.print(f"  [green]Sandbox → {label}[/green] — {selected.label}")
        else:
            self.console.print(f"  [dim]Already using {selected.label}.[/dim]")

        if selected.kind != "builtin":
            self._prompt_sandbox_base_image(
                cfg,
                compute_type="gpu" if selected.kind == "modal_gpu" else "cpu",
            )

    def _prompt_sandbox_base_image(self, cfg, *, compute_type: str) -> None:
        """Let the user edit the Modal base image inline (Enter keeps current)."""
        from agent.sandbox_backend.profile import (
            DEFAULT_CPU_IMAGE,
            DEFAULT_GPU_IMAGE,
            sandbox_image_ref,
        )

        is_gpu = str(compute_type).strip().lower() == "gpu"
        image_key = "sandbox.gpu_image" if is_gpu else "sandbox.cpu_image"
        default_ref = DEFAULT_GPU_IMAGE if is_gpu else DEFAULT_CPU_IMAGE
        current = sandbox_image_ref(cfg, compute_type=compute_type)
        try:
            edited = self._prompt_session.prompt(
                [("class:prompt", "  Base image (edit / Enter to keep): ")],
                default=current,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print(f"  [dim]Base image:[/dim] {current}")
            return

        next_image = edited or current or default_ref
        if next_image != current:
            cfg.set(image_key, next_image)
            cfg.save()
            self.session.config = cfg
            self.console.print(f"  [green]Base image →[/green] {next_image}")
        else:
            self.console.print(f"  [dim]Base image:[/dim] {next_image}")

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

        if action in {"set-moonshot", "moonshot", "set-moonshot-key", "kimi", "set-kimi"}:
            self._handle_set_moonshot_key(cfg)
            return

        self.console.print(
            "  [dim]Usage:[/dim] /keys  |  /keys profile  |  /keys set-compatible [profile_id]  "
            "|  /keys set-moonshot  |  /keys set-boltz"
        )
        self.console.print(cfg.keys_table())

    def _handle_set_moonshot_key(self, cfg) -> None:
        """Prompt/update MOONSHOT_API_KEY for Kimi."""
        import os

        existing_value = str(
            cfg.get("llm.moonshot_api_key")
            or os.environ.get("MOONSHOT_API_KEY")
            or ""
        ).strip()
        current_state = "configured" if existing_value else "not set"
        self.console.print(
            f"  [cyan]Update Kimi API key[/cyan] "
            f"[dim](currently {current_state})[/dim]"
        )
        self.console.print(
            "  [dim]Get a key at https://platform.moonshot.ai/console/api-keys[/dim]"
        )
        try:
            api_key_input = self._secret_prompt_session.prompt(
                [("class:prompt", "  New MOONSHOT_API_KEY [Enter clears; :keep keeps existing]: ")],
                is_password=True,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print("  [dim]Cancelled.[/dim]")
            return

        api_key = self._resolve_optional_api_key_input(
            api_key_input,
            existing_key=existing_value,
            default_key=existing_value,
        )
        if api_key:
            cfg.set("llm.moonshot_api_key", api_key)
            os.environ["MOONSHOT_API_KEY"] = api_key
            self.console.print("  [green]MOONSHOT_API_KEY updated.[/green]")
        else:
            cfg.unset("llm.moonshot_api_key")
            os.environ.pop("MOONSHOT_API_KEY", None)
            self.console.print("  [green]MOONSHOT_API_KEY cleared.[/green]")
        cfg.save()
        self.session.config = cfg
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
