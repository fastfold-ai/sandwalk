"""Mixin: _manage_openai_profiles_settings, _prompt_yes_no, _resolve_boltz_cli_path, _boltz_cli_version."""

from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess


class _OpenaiProfilesSettingsMixin:
    def _manage_openai_profiles_settings(self, cfg) -> None:
        """Manage OpenAI-compatible profiles from /settings (add/edit/delete)."""
        import sys

        while True:
            profiles = cfg.openai_profiles(include_cloud=True)

            self.console.print("\n  [cyan]OpenAI Profile Manager[/cyan]")
            for profile_id, profile in sorted(
                profiles.items(),
                key=lambda item: str(item[1].get("label") or item[0]).strip().lower(),
            ):
                label = str(profile.get("label") or profile_id).strip()
                backend = str(profile.get("backend") or "other").strip().lower()
                endpoint = str(profile.get("base_url") or "—").strip()
                self.console.print(
                    f"  - [bold]{profile_id}[/bold] · {label} [dim]({backend}, {endpoint})[/dim]"
                )

            self.console.print("\n  [1] Add compatible profile")
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

    def _prompt_yes_no(self, prompt: str, *, default: bool = True) -> bool:
        """Prompt a yes/no question with a sensible default."""
        suffix = "[Y/n]" if default else "[y/N]"
        try:
            prompt_session = getattr(self, "_plain_prompt_session", None)
            if prompt_session is not None and hasattr(prompt_session, "prompt"):
                raw = prompt_session.prompt([("class:prompt", f"  {prompt} {suffix} ")]).strip().lower()
            else:
                raw = input(f"  {prompt} {suffix} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            self.console.print("  [dim]Cancelled.[/dim]")
            return False

        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        return default

    @staticmethod
    def _resolve_boltz_cli_path() -> Path | None:
        """Return the first available boltz-api executable path."""
        candidates: list[str] = []
        in_path = shutil.which("boltz-api")
        if in_path:
            candidates.append(in_path)
        candidates.extend(
            [
                str(Path.home() / ".local" / "bin" / "boltz-api"),
                str(Path.home() / ".boltz" / "bin" / "boltz-api"),
            ]
        )
        for candidate in candidates:
            p = Path(candidate).expanduser()
            if p.exists() and p.is_file() and os.access(str(p), os.X_OK):
                return p
        return None

    @staticmethod
    def _boltz_cli_version(executable: Path) -> str:
        """Return a compact boltz-api version string when callable."""
        try:
            proc = subprocess.run(
                [str(executable), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:  # noqa: BLE001
            return "unknown version"
        output = (proc.stdout or proc.stderr or "").strip()
        if not output:
            return "unknown version"
        return output.splitlines()[0].strip()
