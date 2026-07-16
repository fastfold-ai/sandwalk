"""Mixin: _change_settings."""

from __future__ import annotations

from prompt_toolkit.formatted_text import HTML


class _SettingsMenuMixin:
    def _change_settings(self):
        """Interactive settings configuration menu."""
        from agent.config import AGENT_PROFILE_PRESETS, Config
        from ui.status import SPINNERS

        cfg = Config.load()
        self.session.config = cfg

        while True:
            self.console.print("\n  [cyan]Settings Menu[/cyan]")
            self.console.print("  [1] UI Loading Spinner")
            self.console.print("  [2] Agent Profile (Research/Pharma/Enterprise)")
            self.console.print("  [3] Auto-publish HTML Reports")
            self.console.print("  [4] OpenAI-compatible Profiles")
            self.console.print("  [0] Done")
            self.console.print("\n  Select option: ", end="")

            import sys
            sys.stdout.flush()

            try:
                choice = self._getch()
            except KeyboardInterrupt:
                self.console.print()
                return

            self.console.print(choice)

            if choice == "0":
                break
            elif choice == "1":
                spinners = list(SPINNERS.keys())
                current_spinner = cfg.get("ui.spinner", "dna_helix")
                self.console.print("\n  [cyan]UI Loading Spinner[/cyan]")
                for i, spinner_id in enumerate(spinners, 1):
                    marker = " [green]*[/green]" if spinner_id == current_spinner else "  "
                    self.console.print(f"  {marker} [{i}] {spinner_id}")
                self.console.print("\n  Select spinner: ", end="")
                sys.stdout.flush()

                try:
                    s_choice = self._getch()
                except KeyboardInterrupt:
                    self.console.print()
                    return

                self.console.print(s_choice)

                if s_choice.isdigit() and 1 <= int(s_choice) <= len(spinners):
                    new_spinner = spinners[int(s_choice) - 1]
                    if new_spinner != current_spinner:
                        cfg.set("ui.spinner", new_spinner)
                        cfg.save()
                        self.console.print(f"  [green]Spinner updated to:[/green] {new_spinner}")
                else:
                    self.console.print("  [dim]Cancelled.[/dim]")

            elif choice == "2":
                profiles = list(AGENT_PROFILE_PRESETS.keys())
                current_profile = cfg.get("agent.profile", "research")
                self.console.print("\n  [cyan]Agent Profile[/cyan]")
                for i, profile_id in enumerate(profiles, 1):
                    marker = " [green]*[/green]" if profile_id == current_profile else "  "
                    self.console.print(f"  {marker} [{i}] {profile_id}")
                self.console.print("\n  Select profile: ", end="")
                sys.stdout.flush()

                try:
                    p_choice = self._getch()
                except KeyboardInterrupt:
                    self.console.print()
                    return

                self.console.print(p_choice)

                if p_choice.isdigit() and 1 <= int(p_choice) <= len(profiles):
                    new_profile = profiles[int(p_choice) - 1]
                    if new_profile != current_profile:
                        cfg.set("agent.profile", new_profile)
                        cfg.save()
                        self.console.print(f"  [green]Profile updated to:[/green] {new_profile}")
                else:
                    self.console.print("  [dim]Cancelled.[/dim]")

            elif choice == "3":
                current_html = cfg.get("output.auto_publish_html_interactive", True)
                self.console.print("\n  [cyan]Auto-publish HTML Reports[/cyan]")
                self.console.print(f"  Current: [bold]{'Yes' if current_html else 'No'}[/bold]")
                self.console.print("\n  Enable? (y/n): ", end="")
                sys.stdout.flush()

                try:
                    h_choice = self._getch().lower()
                except KeyboardInterrupt:
                    self.console.print()
                    return

                self.console.print(h_choice)

                if h_choice == "y":
                    cfg.set("output.auto_publish_html_interactive", True)
                    cfg.save()
                    self.console.print("  [green]Auto-publish HTML enabled.[/green]")
                elif h_choice == "n":
                    cfg.set("output.auto_publish_html_interactive", False)
                    cfg.save()
                    self.console.print("  [green]Auto-publish HTML disabled.[/green]")
                else:
                    self.console.print("  [dim]Cancelled.[/dim]")
            elif choice == "4":
                self._manage_openai_profiles_settings(cfg)
            else:
                self.console.print("  [dim]Invalid choice.[/dim]")
