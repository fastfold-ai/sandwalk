"""Mixin: _upgrade_skills, _remove_skill."""

from __future__ import annotations


class _SkillsUpgradeRemoveMixin:
    def _upgrade_skills(self):
        """Sync the Fastfold catalog and update installed skills."""
        from agent.skills import GLOBAL_SKILLS_DIR, upgrade_skills

        with self.console.status("[green]Syncing agent skills...[/green]", spinner="dots") as status:
            result = upgrade_skills(
                progress=lambda msg: status.update(f"[green]{msg}[/green]")
            )
        if result.get("added"):
            self.console.print(f"  [green]Added:[/green] {', '.join(result['added'])}")
        if result.get("updated"):
            self.console.print(f"  [green]Updated:[/green] {', '.join(result['updated'])}")
        if result.get("npx_synced"):
            self.console.print(
                f"  [green]npx-synced:[/green] {result['npx_synced']} project-local source(s)"
            )
        for source, reason in result.get("failed", []):
            self.console.print(f"  [yellow]Failed:[/yellow] {source} — {reason}")
        self.console.print(f"  [dim]{result['summary']}[/dim]")
        self.console.print(f"  [dim]Location: {GLOBAL_SKILLS_DIR}[/dim]")
        self.console.print(
            "  [dim]Available on your next message (the system prompt reloads each turn).[/dim]"
        )

    def _remove_skill(self, name: str):
        """Remove a globally-installed skill by name."""
        from agent.skills import remove_skill

        name = (name or "").strip()
        if not name:
            self.console.print("  [yellow]Usage:[/yellow] /skills-remove <name>")
            return
        result = remove_skill(name)
        style = "green" if result.get("ok") else "yellow"
        self.console.print(f"  [{style}]{result['summary']}[/{style}]")
