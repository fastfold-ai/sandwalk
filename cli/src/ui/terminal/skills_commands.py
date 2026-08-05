"""Mixin: _show_skills, _add_skill, _find_skills."""

from __future__ import annotations


class _SkillsCommandsMixin:
    def _show_skills(self):
        """Open the searchable skills modal (Rich table as fallback)."""
        host = getattr(self, "_skills_modal_host", None)
        app = getattr(self, "_transcript_app", None)
        if host is not None and getattr(app, "is_running", False):
            host.open()
            return
        from ui.terminal.skills_modal import run_skills_modal

        if run_skills_modal(self):
            return
        self._print_skills_table()

    def _print_skills_table(self):
        """Legacy Rich table when the modal cannot open (tests / non-TTY)."""
        from rich.table import Table

        from agent.skills import display_author, display_updated, display_version, list_skills
        from agent.specialists_manage import get_active_specialist

        skills = list_skills()
        active = get_active_specialist()
        if active is not None:
            allowed = {
                str(name).strip().lower()
                for name in (active.skill_names or [])
                if str(name).strip()
            }
            skills = [
                info
                for info in skills
                if str(info.name).strip().lower() in allowed
            ]
            self.console.print(
                f"  [dim]Showing skills for specialist[/dim] "
                f"[bold]{active.name}[/bold] "
                f"[dim]({active.slug}) · {len(allowed)} configured[/dim]"
            )
        if not skills:
            if active is not None:
                self.console.print(
                    "  [yellow]No matching installed skills for this specialist.[/yellow]"
                )
                self.console.print(
                    "  [dim]Clear with[/dim] /specialist clear  "
                    "[dim]to list all skills, or install missing ones.[/dim]"
                )
            else:
                self.console.print("  [yellow]No skills loaded.[/yellow]")
                self.console.print(
                    "  [dim]Add one with[/dim] /skills-add <github url or owner/repo@path>"
                )
            return

        enabled_count = len([info for info in skills if getattr(info, "enabled", True)])
        title = (
            f"Specialist Skills — {active.name} "
            f"({len(skills)} installed, {enabled_count} enabled)"
            if active is not None
            else f"Loaded Skills ({len(skills)} total, {enabled_count} enabled)"
        )
        table = Table(title=title, show_lines=False)
        table.add_column("Skill", style="bold cyan", no_wrap=True)
        table.add_column("Enabled", style="dim", no_wrap=True)
        table.add_column("Source", style="dim")
        table.add_column("Author", style="dim")
        table.add_column("Updated", style="dim")
        table.add_column("Version", style="dim")
        table.add_column("Description", style="white")

        for info in skills:
            table.add_row(
                info.name,
                "yes" if getattr(info, "enabled", True) else "no",
                info.source,
                display_author(info),
                display_updated(info),
                display_version(info),
                info.description,
            )

        self.console.print(table)
        if active is not None:
            self.console.print(
                "  [dim]Only specialist skills are listed while one is active.[/dim]"
            )

    def _add_skill(self, source: str):
        """Install a skill from a GitHub URL / shorthand / local path / name."""
        from agent.skills import install_skill

        source = (source or "").strip()
        if not source:
            self.console.print(
                "  [yellow]Usage:[/yellow] /skills-add <github url | owner/repo@path | local path | name>"
            )
            return
        with self.console.status(
            f"[green]Installing skill from {source}...[/green]", spinner="dots"
        ):
            result = install_skill(source)
        if result.get("ok"):
            self.console.print(f"  [green]{result['summary']}[/green]")
            self.console.print(
                "  [dim]Available on your next message (the system prompt reloads each turn).[/dim]"
            )
        else:
            self.console.print(f"  [red]{result['summary']}[/red]")

    def _find_skills(self, query: str = ""):
        """Discover installable skills from the catalog."""
        from rich.table import Table

        from agent.skills import discover_skills

        with self.console.status("[green]Searching skill catalog...[/green]", spinner="dots"):
            results = discover_skills(query.strip() or None)
        if not results:
            self.console.print(
                "  [yellow]No matching skills found.[/yellow] "
                "[dim](Requires git; check network/catalog access.)[/dim]"
            )
            return
        table = Table(title=f"Available Skills ({len(results)})", show_lines=False)
        table.add_column("Skill", style="bold cyan", no_wrap=True)
        table.add_column("Install source", style="dim")
        table.add_column("Description", style="white")
        for r in results:
            table.add_row(r["name"], r["install_source"], r["description"])
        self.console.print(table)
        self.console.print("  [dim]Install with:[/dim] /skills-add <install source>")
