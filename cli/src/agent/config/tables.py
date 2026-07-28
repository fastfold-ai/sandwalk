"""Rich table rendering for API keys and full config dumps."""

import os
from datetime import datetime

from rich.table import Table

from .api_keys import API_KEYS
from .defaults import DEFAULTS


def _format_updated_date(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "[dim]unknown[/dim]"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone().strftime(
            "%Y-%m-%d"
        )
    except ValueError:
        return "[dim]unknown[/dim]"


class TablesMixin:
    """``keys_table`` / ``to_table`` renderers exposed on ``Config``."""

    def keys_table(self) -> Table:
        """Render API key status as a rich table."""
        table = Table(title="API Keys", caption="Set: sandwalk config set <key> <value>  |  Or: export ENV_VAR=<value>")
        table.add_column("Service", style="bold")
        table.add_column("Status")
        table.add_column("Preview", style="magenta dim")
        table.add_column("Unlocks", style="dim")
        table.add_column("Config Key", style="cyan dim")
        table.add_column("Sign Up", style="dim")
        table.add_column("Updated", style="dim", no_wrap=True)

        profiles = self.openai_profiles(include_cloud=True)
        timestamps = self.get("integrations.updated_at")
        if not isinstance(timestamps, dict):
            timestamps = {}
        active_profile = self.get_openai_profile()
        active_profile_id = str((active_profile or {}).get("id") or "").strip()
        active_profile_label = str((active_profile or {}).get("label") or "").strip()
        active_profile_backend = str((active_profile or {}).get("backend") or "").strip().lower()
        compatible_profiles = {
            profile_id: profile
            for profile_id, profile in profiles.items()
            if str(profile.get("backend") or "").strip().lower() != "openai"
        }

        for config_key, info in API_KEYS.items():
            if config_key == "llm.anthropic_api_key":
                val = self.llm_api_key("anthropic")
                # Mark legacy-only usage clearly.
                if (
                    not self._normalized_secret(self.get("llm.anthropic_api_key"))
                    and self._normalized_secret(self.get("llm.api_key"))
                ):
                    status = "[yellow]configured (legacy llm.api_key)[/yellow]"
                else:
                    status = "[green]configured[/green]" if val else "[red]not set[/red]"
            elif config_key == "llm.openai_api_key":
                val = self._normalized_secret(
                    os.environ.get("OPENAI_API_KEY")
                    or self.get("llm.openai_api_key")
                    or (profiles.get("openai_cloud") or {}).get("api_key")
                )
                status = "[green]configured[/green]" if val else "[red]not set[/red]"
                if active_profile_backend == "openai":
                    status = f"{status} [dim](active: {active_profile_label or 'OpenAI Cloud'})[/dim]"
            else:
                val = self._normalized_secret(self.get(config_key))
                status = "[green]configured[/green]" if val else "[red]not set[/red]"

            free_tag = " (free)" if info["free"] else ""
            table.add_row(
                info["name"],
                status,
                self._secret_preview(val),
                info["description"],
                config_key,
                info["url"] + free_tag,
                _format_updated_date(timestamps.get(config_key)) if val else "—",
            )

            if config_key == "llm.openai_api_key":
                for profile_id, profile in sorted(
                    compatible_profiles.items(),
                    key=lambda item: str(item[1].get("label") or item[0]).strip().lower(),
                ):
                    profile_label = str(profile.get("label") or profile_id).strip()
                    profile_backend = str(profile.get("backend") or "other").strip().lower()
                    profile_endpoint = self._normalize_openai_base_url(profile.get("base_url")) or "—"
                    profile_key = self._normalized_secret(profile.get("api_key"))
                    profile_install_url = self.compatible_backend_install_url(profile_backend)
                    profile_status = (
                        "[green]configured[/green]"
                        if profile_key
                        else "[red]not set[/red]"
                    )
                    if profile_id == active_profile_id:
                        profile_status = f"{profile_status} [dim](active)[/dim]"
                    table.add_row(
                        f"Local LLM: {profile_label}",
                        profile_status,
                        self._secret_preview(profile_key),
                        f"{profile_backend} endpoint ({profile_endpoint})",
                        "llm.openai_profiles.<id>.api_key",
                        (profile_install_url + " (free)") if profile_install_url else "—",
                        (
                            _format_updated_date(
                                timestamps.get(f"llm.openai_profiles.{profile_id}.api_key")
                            )
                            if profile_key
                            else "—"
                        ),
                    )

        return table

    def to_table(self) -> Table:
        """Render config as a rich table."""
        table = Table(title="ct Configuration")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Source", style="dim")

        all_keys = sorted(set(list(DEFAULTS.keys()) + list(self._data.keys())))
        for key in all_keys:
            if key in self._data:
                val = self._data[key]
                source = "config"
            elif key in DEFAULTS:
                val = DEFAULTS[key]
                source = "default"
            else:
                continue

            # Mask sensitive values (API keys, secrets)
            display_val = str(val)
            is_sensitive = "api_key" in key or "secret" in key or key.startswith("api.")
            if is_sensitive and val and len(str(val)) > 8:
                display_val = str(val)[:4] + "..." + str(val)[-4:]

            table.add_row(key, display_val, source)

        return table
