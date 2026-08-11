"""Auto-save the merged multi-agent report to disk (and optionally publish HTML)."""

from datetime import UTC

from agent.orchestrator.models import OrchestratorResult


class AutoSaveMixin:
    """Owns writing the merged markdown report and its provenance metadata."""

    def _auto_save_report(self, query: str, result: OrchestratorResult):
        """Auto-save the multi-agent report to the output directory."""
        import re
        from datetime import datetime
        from pathlib import Path

        try:
            output_base = self.session.config.get("sandbox.output_dir")
            output_dir = (
                Path(output_base) / "reports"
                if output_base
                else Path.cwd() / "outputs" / "reports"
            )
            output_dir.mkdir(parents=True, exist_ok=True)

            query_slug = re.sub(r'[^\w\s-]', '', query.lower())
            query_slug = re.sub(r'[\s]+', '_', query_slug.strip())[:60]
            if not query_slug:
                query_slug = "multi_agent_report"
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{query_slug}_multi_{ts}.md"

            path = output_dir / filename
            counter = 2
            while path.exists():
                filename = f"{query_slug}_multi_{counter}.md"
                path = output_dir / filename
                counter += 1

            # Populate provenance metadata
            from _version import __version__

            cfg = self.session.config
            provider = cfg.get("llm.provider", "anthropic")
            model = cfg.get("llm.model", "unknown")
            profile = cfg.get("agent.profile", "research")
            success_str = f"{result.completed_steps}/{result.total_steps}"

            result.metadata = {
                "query": query,
                "timestamp": datetime.now(UTC).isoformat(),
                "model": f"{provider}/{model}",
                "execution_time_s": result.duration_s,
                "tool_success_rate": success_str,
                "profile": profile,
                "ct_version": __version__,
            }

            report = result.to_markdown()
            path.write_text(report)
            self.console.print(f"  [dim]Report saved → {path}[/dim]")

            mode = str(getattr(self.session, "mode", "batch") or "batch").lower()
            if mode == "interactive":
                publish_html = bool(
                    self.session.config.get("output.auto_publish_html_interactive", True)
                )
            else:
                publish_html = bool(
                    self.session.config.get("output.auto_publish_html_batch", False)
                )
            if publish_html:
                from reports.html import publish_report

                html_path = publish_report(path)
                self.console.print(f"  [dim]HTML report → {html_path}[/dim]")
        except Exception as exc:
            if self.session.verbose:
                self.console.print(
                    f"  [yellow]Could not auto-save report:[/yellow] {exc}"
                )
