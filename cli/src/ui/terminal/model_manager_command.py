"""Mixin: _handle_model_manager_command, _handle_compatible_profiles_command, _toggle_plan_mode."""

from __future__ import annotations

from pathlib import Path


class _ModelManagerCommandMixin:
    def _handle_model_manager_command(self, query: str) -> None:
        """Show and manage OpenAI-compatible profiles (add/edit/delete)."""
        import sys

        from rich.table import Table

        from agent.config import Config

        cfg = Config.load()
        self.session.config = cfg

        while True:
            profiles = cfg.openai_profiles(include_cloud=False)
            if not profiles:
                self.console.print("  [yellow]No OpenAI-compatible profiles configured yet.[/yellow]")
                self.console.print("  [dim]Use [1] below to add your first profile.[/dim]")
            else:
                table = Table(title="OpenAI-compatible Profiles")
                table.add_column("Profile", style="bold")
                table.add_column("Backend")
                table.add_column("Endpoint", style="dim")
                table.add_column("Models Path", style="dim")
                table.add_column("Health")
                table.add_column("API Key", style="magenta dim")
                table.add_column("Models", style="dim")

                for profile_id, profile in sorted(
                    profiles.items(),
                    key=lambda item: str(item[1].get("label") or item[0]).strip().lower(),
                ):
                    backend = str(profile.get("backend") or "other").strip().lower() or "other"
                    endpoint = str(profile.get("base_url") or "").strip() or "—"
                    profile_label = str(profile.get("label") or profile_id).strip()
                    api_key = str(profile.get("api_key") or "").strip() or None

                    probe = self._probe_compatible_profile(
                        base_url=endpoint,
                        backend=backend,
                        api_key=api_key,
                    )
                    model_names = list(probe.get("models") or [])
                    models_display = "—"
                    if model_names:
                        shown = model_names[:4]
                        models_display = ", ".join(shown)
                        if len(model_names) > 4:
                            models_display += f" (+{len(model_names) - 4})"
                    elif probe.get("error"):
                        models_display = f"[dim]{probe.get('error')}[/dim]"

                    backend_label = self._compatible_backend_display_name(backend)
                    key_preview = Config._secret_preview(api_key)
                    table.add_row(
                        profile_label,
                        backend_label,
                        endpoint,
                        str(probe.get("models_path") or "—"),
                        str(probe.get("health") or "—"),
                        key_preview,
                        models_display,
                    )

                self.console.print(table)

            self.console.print("  [cyan]Model Manager options[/cyan]")
            self.console.print("  [1] Add compatible profile")
            self.console.print("  [2] Edit compatible profile")
            self.console.print("  [3] Delete compatible profile")
            self.console.print("  [0] Back")
            self.console.print("\n  Select option: ", end="")
            sys.stdout.flush()

            try:
                choice = self._getch()
            except KeyboardInterrupt:
                self.console.print()
                return
            self.console.print(choice)

            if choice == "0":
                return
            if choice == "1":
                profile_id = self._create_or_edit_compatible_profile()
                if profile_id:
                    self.session.config = cfg
                    self.console.print(f"  [green]Profile saved:[/green] {profile_id}")
                else:
                    self.console.print("  [dim]Cancelled.[/dim]")
                continue
            if choice == "2":
                profile_id = self._prompt_select_compatible_profile_id(
                    cfg=cfg,
                    allow_create=False,
                )
                if not profile_id:
                    self.console.print("  [dim]Cancelled.[/dim]")
                    continue
                updated_profile_id = self._create_or_edit_compatible_profile(profile_id=profile_id)
                if updated_profile_id:
                    self.session.config = cfg
                    self.console.print(f"  [green]Profile updated:[/green] {updated_profile_id}")
                else:
                    self.console.print("  [dim]Cancelled.[/dim]")
                continue
            if choice == "3":
                profile_id = self._prompt_select_compatible_profile_id(
                    cfg=cfg,
                    allow_create=False,
                )
                if not profile_id:
                    self.console.print("  [dim]Cancelled.[/dim]")
                    continue
                if not cfg.remove_openai_profile(profile_id):
                    self.console.print("  [yellow]Profile could not be deleted.[/yellow]")
                    continue
                cfg.save()
                self.session.config = cfg
                self.console.print(f"  [green]Deleted profile:[/green] {profile_id}")
                continue
            self.console.print("  [dim]Invalid choice.[/dim]")

    def _handle_compatible_profiles_command(self, query: str) -> None:
        self._handle_model_manager_command(query)

    def _toggle_plan_mode(self):
        """Toggle Plan mode vs Agent mode (writes plans/*.md; no approval gate)."""
        cfg = self.session.config
        current = bool(cfg.get("agent.plan_preview", False))
        cfg.set("agent.plan_preview", not current)
        if not current:
            self.console.print(
                "  [#ff79c6]Plan mode ON[/] — write plans under workspace/plans/; "
                "no execution until you switch to agent mode"
            )
        else:
            self.console.print(
                "  [green]Agent mode ON[/green] — will execute "
                "(use plans/*.md if present)"
            )
            self._print_pending_plans()

    def _print_pending_plans(self) -> None:
        """List newest plan markdown files in the active session workspace."""
        workspace = ""
        try:
            ensure = getattr(getattr(self, "agent", None), "ensure_workspace_path", None)
            if callable(ensure):
                workspace = str(ensure() or "").strip()
        except Exception:
            workspace = ""
        if not workspace:
            return
        try:
            from agent.system_prompt.mode_section import list_recent_plan_files

            plans = list_recent_plan_files(workspace)
        except Exception:
            plans = []
        if not plans:
            return
        self.console.print("  [dim]Pending plans:[/dim]")
        for rel in plans:
            self.console.print(f"    [cyan]{rel}[/cyan]")
