"""Mixin: _install_boltz_skill, _ensure_boltz_cli_ready, _handle_set_boltz_key, _handle_mcp_command, _handle_specialist_command."""

from __future__ import annotations

import os
import shutil
import subprocess
from ui.terminal.model_ids import _BOLTZ_INSTALL_SCRIPT
from ui.terminal.model_ids import _BOLTZ_SKILL_SOURCE


class _BoltzSetupMixin:
    def _install_boltz_skill(self) -> bool:
        """Install the official Fastfold boltz skill if missing."""
        from agent.skills import install_skill, installed_skill_names

        installed = set(installed_skill_names())
        if "boltz" in installed:
            self.console.print("  [green]Boltz skill already installed.[/green]")
            return True

        with self.console.status("[green]Installing Fastfold Boltz skill...[/green]", spinner="dots"):
            result = install_skill(_BOLTZ_SKILL_SOURCE, prefer_npx=True)
        if result.get("ok"):
            self.console.print(f"  [green]{result.get('summary', 'Installed boltz skill.')}[/green]")
            self.console.print("  [dim]Skill will be available on your next message.[/dim]")
            return True

        self.console.print(
            "  [yellow]Could not auto-install Boltz skill.[/yellow] "
            f"[dim]{result.get('summary', '')}[/dim]"
        )
        self.console.print(
            f"  [dim]Install manually with:[/dim] /skills-add {_BOLTZ_SKILL_SOURCE}"
        )
        return False

    def _ensure_boltz_cli_ready(self) -> bool:
        """Ensure boltz-api CLI is installed locally."""
        existing = self._resolve_boltz_cli_path()
        if existing:
            version = self._boltz_cli_version(existing)
            self.console.print(f"  [green]boltz-api ready:[/green] {existing} [dim]({version})[/dim]")
            if shutil.which("boltz-api") is None:
                self.console.print(
                    "  [dim]Tip: add ~/.local/bin to PATH if you want `boltz-api` by name in shell.[/dim]"
                )
            return True

        if not shutil.which("curl") or not shutil.which("sh"):
            self.console.print(
                "  [yellow]Could not install boltz-api automatically (missing curl/sh).[/yellow]"
            )
            self.console.print(
                "  [dim]Install manually:[/dim] curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"
            )
            return False

        with self.console.status("[green]Installing boltz-api CLI...[/green]", spinner="dots"):
            proc = subprocess.run(
                ["sh", "-lc", _BOLTZ_INSTALL_SCRIPT],
                capture_output=True,
                text=True,
                timeout=180,
            )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            detail = detail.splitlines()[-1] if detail else "installer exited with a non-zero code"
            self.console.print(f"  [yellow]boltz-api install failed:[/yellow] {detail}")
            self.console.print(
                "  [dim]Retry manually:[/dim] curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"
            )
            return False

        installed_path = self._resolve_boltz_cli_path()
        if not installed_path:
            self.console.print(
                "  [yellow]boltz-api installer completed, but executable was not found on disk.[/yellow]"
            )
            return False

        version = self._boltz_cli_version(installed_path)
        self.console.print(f"  [green]Installed boltz-api:[/green] {installed_path} [dim]({version})[/dim]")
        if shutil.which("boltz-api") is None:
            self.console.print(
                "  [dim]Tip: add ~/.local/bin to PATH if you want `boltz-api` by name in shell.[/dim]"
            )
        return True

    def _handle_set_boltz_key(self, cfg) -> None:
        """Prompt/update BOLTZ_API_KEY and offer skill/CLI setup."""
        existing_value = str(cfg.get("api.boltz_api_key") or os.environ.get("BOLTZ_API_KEY") or "").strip()
        current_state = "configured" if existing_value else "not set"
        self.console.print(
            f"  [cyan]Update BOLTZ_API_KEY[/cyan] [dim](currently {current_state})[/dim]"
        )
        try:
            api_key_input = self._secret_prompt_session.prompt(
                [("class:prompt", "  New BOLTZ_API_KEY [Enter clears key; :keep keeps existing]: ")],
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
            cfg.set("api.boltz_api_key", api_key)
            os.environ["BOLTZ_API_KEY"] = api_key
            self.console.print("  [green]BOLTZ_API_KEY updated.[/green]")
        else:
            cfg.unset("api.boltz_api_key")
            os.environ.pop("BOLTZ_API_KEY", None)
            self.console.print("  [green]BOLTZ_API_KEY cleared.[/green]")

        cfg.save()
        self.session.config = cfg
        self.console.print(cfg.keys_table())

        if not api_key:
            return

        if self._prompt_yes_no("Install Fastfold Boltz skill now?", default=True):
            self._install_boltz_skill()
        else:
            self.console.print("  [dim]Skipped Boltz skill install.[/dim]")

        if self._prompt_yes_no("Install boltz-api CLI now?", default=True):
            self._ensure_boltz_cli_ready()
        else:
            self.console.print("  [dim]Skipped boltz-api install.[/dim]")

    def _show_mcp(self) -> None:
        """Open the searchable MCP modal (Rich table as fallback)."""
        host = getattr(self, "_mcp_modal_host", None)
        app = getattr(self, "_transcript_app", None)
        if host is not None and getattr(app, "is_running", False):
            host.open()
            return
        from ui.terminal.mcp_modal import run_mcp_modal

        if run_mcp_modal(self):
            return
        from agent.mcp_manage import handle_mcp_argv

        handle_mcp_argv(["list"], self.console)

    def _handle_mcp_command(self, query: str) -> None:
        """Handle /mcps — modal for list; subcommands keep the CLI path."""
        from agent.mcp_manage import handle_mcp_argv

        parts = query.strip().split()
        # Drop leading /mcps or mcps
        if parts and parts[0].lstrip("/").lower() == "mcps":
            parts = parts[1:]
        if not parts or parts[0].lower() in {"list", "status", "ls"}:
            self._show_mcp()
            return
        handle_mcp_argv(parts, self.console)

    def _handle_specialist_command(self, query: str) -> None:
        """Handle /specialist — list and activate run profiles."""
        from agent.specialists_manage import handle_specialist_argv

        parts = query.strip().split()
        if parts and parts[0].lstrip("/").lower() == "specialist":
            parts = parts[1:]
        handle_specialist_argv(parts or ["list"], self.console)
        self._refresh_cli_specialist_label()
