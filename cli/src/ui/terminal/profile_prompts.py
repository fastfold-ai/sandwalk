"""Mixin: _model_display_name, _prompt_select_compatible_profile_id, _prompt_profile_label."""

from __future__ import annotations

class _ProfilePromptsMixin:
    def _model_display_name(self, model_id: str = None) -> str:
        """Get a short display name for a model ID."""
        model_id = model_id or self.session.current_model
        value = str(model_id or "").strip()
        names = {
            "claude-sonnet-4-5-20250929": "Sonnet 4.5",
            "claude-haiku-4-5-20251001": "Haiku 4.5",
            "claude-opus-4-6": "Opus 4.6",
            "gpt-5.5": "GPT-5.5",
            "gpt-5.5-pro": "GPT-5.5 Pro",
            "gpt-5.4": "GPT-5.4",
            "gpt-5.4-pro": "GPT-5.4 Pro",
            "gpt-5.4-mini": "GPT-5.4 Mini",
            "gpt-5.4-nano": "GPT-5.4 Nano",
            "gpt-5-mini": "GPT-5 Mini",
            "gpt-5-nano": "GPT-5 Nano",
            "gpt-4o": "GPT-4o",
            "gpt-4o-mini": "GPT-4o Mini",
        }
        if value in names:
            return names[value]
        # Prefer the active provider's catalog row when the same id is shared
        # across gateways (e.g. kimi-k3 on Moonshot vs OpenCode Zen).
        provider = None
        try:
            cfg = getattr(self.session, "config", None)
            if cfg is not None:
                provider = str(cfg.get("llm.provider") or "").strip().lower() or None
        except Exception:  # noqa: BLE001
            provider = None
        try:
            from agent.model_catalog import catalog_label_for_model

            labeled = catalog_label_for_model(value, provider=provider)
            if labeled:
                return labeled
        except Exception:  # noqa: BLE001
            pass
        # Discovered / gateway ids: kimi-k3 → Kimi K3, gpt-5.4 → GPT 5.4.
        try:
            from agent.model_catalog import format_discovered_model_label

            return format_discovered_model_label(value)
        except Exception:  # noqa: BLE001
            return value or str(model_id or "")

    def _prompt_select_compatible_profile_id(
        self,
        *,
        cfg=None,
        allow_create: bool = False,
        create_label: str = "Create new profile",
    ) -> str | None:
        """Prompt user to pick a compatible profile id."""
        profile_cfg = cfg or self.session.config
        profiles = profile_cfg.openai_profiles(include_cloud=False)
        if not profiles:
            self.console.print("  [dim]No compatible profiles configured yet.[/dim]")
            return "__create__" if allow_create else None

        rows = sorted(
            profiles.items(),
            key=lambda item: str(item[1].get("label") or item[0]).strip().lower(),
        )
        active_profile_id = profile_cfg.active_openai_profile_id()
        self.console.print("  [cyan]Compatible profiles[/cyan]")
        for idx, (profile_id, profile) in enumerate(rows, 1):
            marker = " [green]*[/green]" if profile_id == active_profile_id else "  "
            label = str(profile.get("label") or profile_id).strip()
            backend = str(profile.get("backend") or "other").strip().lower()
            endpoint = str(profile.get("base_url") or "—").strip()
            self.console.print(
                f"{marker} [{idx}] {label} [dim]({backend}, {endpoint})[/dim]"
            )
        create_idx = len(rows) + 1
        if allow_create:
            self.console.print(f"   [{create_idx}] {create_label}")

        default_idx = 1
        for idx, (profile_id, _) in enumerate(rows, 1):
            if profile_id == active_profile_id:
                default_idx = idx
                break
        if allow_create and not rows:
            default_idx = create_idx

        try:
            raw_choice = self._plain_prompt_session.prompt(
                [("class:prompt", f"  Select profile [{default_idx}]: ")]
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        selected = raw_choice or str(default_idx)
        if allow_create and selected in {str(create_idx), "new", "n", "create"}:
            return "__create__"
        if selected.isdigit():
            selected_idx = int(selected)
            if 1 <= selected_idx <= len(rows):
                return rows[selected_idx - 1][0]
        selected_lower = selected.lower()
        for profile_id, profile in rows:
            profile_label = str(profile.get("label") or "").strip().lower()
            if selected_lower in {profile_id.lower(), profile_label}:
                return profile_id
        self.console.print("  [dim]Invalid selection.[/dim]")
        return None

    def _prompt_profile_label(self, default_label: str) -> str | None:
        """Prompt for a profile label with a default value."""
        try:
            entered = self._plain_prompt_session.prompt(
                [("class:prompt", f"  Profile label [{default_label}]: ")]
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        label = entered or default_label
        return label.strip() or None
