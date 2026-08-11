"""Mixin: per-model Effort / Fast (thinking) prompts for /effort."""

from __future__ import annotations


class _EffortCommandMixin:
    def _compatible_backend_for_effort(self, cfg, provider: str | None) -> str | None:
        provider_norm = str(provider or "").strip().lower()
        if provider_norm not in {"local", "openai", "compatible", "openai-compatible", ""}:
            return None
        try:
            profile = cfg.get_openai_profile()
        except Exception:  # noqa: BLE001
            return None
        if not isinstance(profile, dict):
            return None
        backend = str(profile.get("backend") or "").strip().lower() or None
        if backend in {None, "", "openai"}:
            return None
        return backend

    def _model_supports_effort_ui(
        self,
        cfg,
        provider: str | None,
        model_id: str | None,
    ) -> bool:
        from agent.model_catalog import model_supports_reasoning_effort

        backend = self._compatible_backend_for_effort(cfg, provider)
        return model_supports_reasoning_effort(
            provider, model_id, compatible_backend=backend
        )

    def _prompt_and_save_model_effort(
        self,
        cfg,
        *,
        provider: str | None,
        model_id: str | None,
        display: str | None = None,
    ) -> None:
        """Prompt Low/Medium/High/Fast and persist to ``llm.model_reasoning``."""
        from agent.model_catalog import (
            format_reasoning_effort_label,
            get_model_reasoning,
            normalize_reasoning_effort,
            upsert_model_reasoning,
        )

        if not self._model_supports_effort_ui(cfg, provider, model_id):
            return

        store_provider = str(provider or "").strip().lower() or "openai"
        # Runtime OpenAI path for Unsloth still keys the store as local.
        if store_provider == "openai":
            backend = self._compatible_backend_for_effort(cfg, "local")
            if backend == "unsloth":
                store_provider = "local"

        current_effort, current_fast = get_model_reasoning(
            cfg.get("llm.model_reasoning"),
            store_provider,
            model_id,
            default_effort=str(cfg.get("llm.reasoning_effort") or "medium"),
            default_fast=bool(cfg.get("llm.reasoning_fast", False)),
        )
        label = str(display or model_id or "model").strip()
        current_label = format_reasoning_effort_label(
            effort=current_effort, fast=current_fast
        )
        self.console.print(
            f"  [cyan]Effort for {label}[/cyan] [dim](current: {current_label})[/dim]"
        )
        self.console.print("  [1] Low")
        self.console.print("  [2] Medium")
        self.console.print("  [3] High")
        self.console.print("  [4] Fast (thinking off where supported)")
        self.console.print("  [0] Keep current")
        try:
            choice = self._prompt_session.prompt(
                [("class:prompt", "  Select effort (number): ")],
            ).strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print("  [dim]Cancelled.[/dim]")
            return

        if choice in {"", "0"}:
            self.console.print(f"  [dim]Keeping {current_label}.[/dim]")
            return
        mapping = {
            "1": ("low", False),
            "2": ("medium", False),
            "3": ("high", False),
            "4": ("low", True),
        }
        selected = mapping.get(choice)
        if not selected:
            self.console.print("  [dim]Cancelled.[/dim]")
            return
        effort, fast = selected
        next_store = upsert_model_reasoning(
            cfg.get("llm.model_reasoning"),
            store_provider,
            model_id,
            effort=normalize_reasoning_effort(effort, allow_none=False),
            fast=fast,
        )
        cfg.set("llm.model_reasoning", next_store)
        cfg.save()
        self.session.config = cfg
        shown = format_reasoning_effort_label(effort=effort, fast=fast)
        self.console.print(f"  [green]Effort →[/green] {shown}")

    def _handle_effort_command(self, query: str = "") -> None:
        """`/effort` — set Effort / Fast for the active model."""
        from agent.config import Config
        from ui.terminal.effort_modal import run_effort_modal

        _ = query
        host = getattr(self, "_effort_modal_host", None)
        app = getattr(self, "_transcript_app", None)
        if host is not None and getattr(app, "is_running", False):
            host.open()
            return
        if run_effort_modal(self):
            return

        cfg = getattr(self.session, "config", None) or Config.load()
        provider = str(
            getattr(self.session, "current_provider", None)
            or cfg.get("llm.provider")
            or "openai"
        ).strip().lower()
        model_id = str(
            getattr(self.session, "current_model", None) or cfg.get("llm.model") or ""
        ).strip()
        # Unsloth / local profiles are stored as openai at runtime.
        if provider == "openai":
            backend = self._compatible_backend_for_effort(cfg, "local")
            check_provider = "local" if backend == "unsloth" else "openai"
        else:
            check_provider = provider
            backend = None

        if not model_id or not self._model_supports_effort_ui(
            cfg, check_provider, model_id
        ):
            self.console.print(
                "  [dim]Active model does not support Effort / thinking controls.[/dim]"
            )
            return

        self._prompt_and_save_model_effort(
            cfg,
            provider=check_provider,
            model_id=model_id,
            display=model_id,
        )
