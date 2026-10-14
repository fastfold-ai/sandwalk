"""LLM preflight readiness checks and human-readable selection summaries."""

import os
from urllib.parse import urlparse

from .constants import VALID_LLM_PROVIDERS
from .providers import OPENAI_COMPATIBLE_PROVIDERS, OPENAI_PROFILE_DEFAULTS

MODEL_SETUP_MESSAGE = (
    "No model is set up yet. Add a provider and API key in "
    "[Models](/dashboard/models)."
)


class SecretsPreflightMixin:
    """Base-URL classification, preflight issue detection, selection summary."""

    @staticmethod
    def _is_local_openai_base_url(base_url: str | None) -> bool:
        """Heuristic: localhost OpenAI-compatible endpoints can skip API keys."""
        if not base_url:
            return False
        try:
            parsed = urlparse(str(base_url).strip())
        except Exception:
            return False
        host = (parsed.hostname or "").strip().lower()
        return host in {"localhost", "127.0.0.1", "::1"}

    @staticmethod
    def _is_openai_managed_base_url(base_url: str | None) -> bool:
        """Return True when base URL points to OpenAI-managed API hosts."""
        if not base_url:
            return True
        try:
            parsed = urlparse(str(base_url).strip())
        except Exception:
            return False
        host = (parsed.hostname or "").strip().lower()
        if not host:
            return False
        return host == "api.openai.com" or host.endswith(".openai.com")

    @staticmethod
    def compatible_backend_install_url(backend: str | None) -> str:
        """Return install/reference URL for a compatible backend template."""
        backend_type = str(backend or "").strip().lower()
        if backend_type in {"other", "custom"}:
            return ""
        defaults = OPENAI_PROFILE_DEFAULTS.get(backend_type, {})
        return str(defaults.get("install_url") or "")

    def llm_preflight_issue(self) -> str | None:
        """Return a human-readable LLM config issue, or None when ready."""
        provider_raw = self.get("llm.provider", "anthropic")
        provider = str(provider_raw or "").strip().lower()
        if not provider:
            return "llm.provider is empty. Set it with: sandwalk config set llm.provider anthropic"

        if provider not in VALID_LLM_PROVIDERS:
            valid = ", ".join(sorted(VALID_LLM_PROVIDERS))
            return (
                f"Unsupported llm.provider '{provider}'. "
                f"Valid providers: {valid}. Set it with: sandwalk config set llm.provider <provider>"
            )

        if provider == "bedrock":
            return None

        if provider == "openai-chatgpt":
            from .chatgpt_auth import is_connected

            if is_connected():
                return None
            return (
                "Not signed in with ChatGPT. Open Dashboard → Models and choose "
                "Continue with ChatGPT, or run: sandwalk setup"
            )

        provider_key = self.llm_api_key(provider)
        if provider_key:
            if provider == "openai" and str(provider_key).startswith("sk-ant-"):
                return (
                    "Configured OpenAI key appears to be an Anthropic key (starts with 'sk-ant-'). "
                    "Set a valid OpenAI key with:\n"
                    "  sandwalk config set llm.openai_api_key <key>"
                )
            return None

        if provider in OPENAI_COMPATIBLE_PROVIDERS:
            meta = OPENAI_COMPATIBLE_PROVIDERS[provider]
            return (
                f"{meta['label']} API key not configured. Add it in Dashboard → "
                f"Models → API Keys, set {meta['env_var']}, or run:\n"
                f"  sandwalk config set {meta['config_key']} <key>"
            )

        # Azure AI Foundry: Foundry-specific env vars are valid Anthropic auth
        if provider == "anthropic" and (
            os.environ.get("ANTHROPIC_FOUNDRY_API_KEY")
            or os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE")
        ):
            return None

        if provider == "openai":
            base_url = self.llm_openai_base_url()
            profile = self.get_openai_profile()
            backend = str((profile or {}).get("backend") or "").strip().lower()
            if backend and backend != "openai":
                # Local / compatible endpoints: key optional at preflight;
                # chat uses the active profile key when present.
                return None
            if self._is_local_openai_base_url(base_url):
                return None
            return (
                "OpenAI API key not configured. Set OPENAI_API_KEY or run:\n"
                "  sandwalk config set llm.openai_api_key <key>"
            )

        return (
            "Anthropic API key not configured. Set ANTHROPIC_API_KEY or run:\n"
            "  sandwalk config set llm.anthropic_api_key <key>\n"
            "Legacy fallback (still supported): llm.api_key\n"
            "For Azure AI Foundry: set ANTHROPIC_FOUNDRY_API_KEY and "
            "ANTHROPIC_FOUNDRY_RESOURCE"
        )

    def model_setup_message(self) -> str | None:
        """User-facing prompt when chat cannot run because no model is ready.

        A default model id (for example ``gpt-5.6-sol``) is not enough: the
        active provider needs a key, and an Anthropic provider cannot run an
        OpenAI model id left over from onboarding.
        """
        if self.llm_preflight_issue():
            return MODEL_SETUP_MESSAGE
        provider = str(self.get("llm.provider") or "").strip().lower()
        model = str(self.get("llm.model") or "").strip()
        if provider == "anthropic" and model and not self._looks_like_anthropic_model(model):
            return MODEL_SETUP_MESSAGE
        return None

    def llm_selection_summary(self) -> str:
        """Human-readable selected LLM line for doctor / UI (not raw provider=)."""
        provider = str(self.get("llm.provider") or "anthropic").strip().lower()
        model = str(self.get("llm.model") or "").strip() or "(default)"

        if os.environ.get("ANTHROPIC_FOUNDRY_API_KEY") or os.environ.get(
            "ANTHROPIC_FOUNDRY_RESOURCE"
        ):
            if provider == "anthropic":
                return f"Anthropic (Azure Foundry) · {model}"

        if provider == "openai":
            profile = self.get_openai_profile() or {}
            backend = str(profile.get("backend") or "openai").strip().lower()
            label = str(profile.get("label") or "").strip()
            if backend and backend != "openai":
                return f"{label or backend} · {model}"
            return f"OpenAI · {model}"

        if provider == "openai-chatgpt":
            return f"ChatGPT plan · {model}"

        if provider in OPENAI_COMPATIBLE_PROVIDERS:
            label = OPENAI_COMPATIBLE_PROVIDERS[provider].get("label") or provider
            return f"{label} · {model}"

        labels = {
            "anthropic": "Anthropic",
            "openai": "OpenAI",
            "bedrock": "Amazon Bedrock",
        }
        return f"{labels.get(provider, provider)} · {model}"
