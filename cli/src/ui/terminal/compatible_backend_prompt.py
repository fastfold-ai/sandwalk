"""Mixin: _prompt_openai_compatible_backend, _ollama_tags_url_from_base."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse


class _CompatibleBackendPromptMixin:
    def _prompt_openai_compatible_backend(self, base_url: str) -> str | None:
        """Prompt for compatible backend type to avoid endpoint guessing."""
        default_choice = "other"
        current_profile = None
        if hasattr(self.session.config, "get_openai_profile"):
            try:
                current_profile = self.session.config.get_openai_profile()
            except Exception:
                current_profile = None
        if not isinstance(current_profile, dict):
            current_profile = None
        current_key = str(
            (current_profile or {}).get("api_key")
            or ""
        ).strip()
        current_backend = str(
            (current_profile or {}).get("backend")
            or self.session.config.get("llm.openai_compatible_backend")
            or ""
        ).strip().lower()
        if current_backend in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}:
            default_choice = current_backend
        if current_key.startswith("sk-unsloth-"):
            default_choice = "unsloth"
        elif (
            current_key.lower().startswith("dsv4-")
            or current_key.lower().startswith("sk-ds4-")
            or "ds4" in str(base_url).lower()
            or "deepseek-v4" in str(base_url).lower()
        ):
            default_choice = "ds4"
        elif "1234" in str(base_url) or "lmstudio" in str(base_url).lower() or "lm-studio" in str(base_url).lower():
            default_choice = "lm_studio"
        elif (
            "8080" in str(base_url)
            or "llama.cpp" in str(base_url).lower()
            or "llama-cpp" in str(base_url).lower()
            or "llamacpp" in str(base_url).lower()
        ):
            default_choice = "llama_cpp"
        elif "8000" in str(base_url) or "omlx" in str(base_url).lower():
            default_choice = "omlx"
        elif "11434" in str(base_url):
            default_choice = "ollama"

        self.console.print("  [cyan]Endpoint type[/cyan]")
        self.console.print(
            f"    [1] Ollama (/api/tags) - {self._compatible_install_url('ollama')}"
        )
        self.console.print(
            f"    [2] Unsloth (/v1/models, auth) - {self._compatible_install_url('unsloth')}"
        )
        self.console.print(
            f"    [3] oMLX (/v1/models, auth) - {self._compatible_install_url('omlx')}"
        )
        self.console.print(
            f"    [4] DS4 (DeepSeek v4, /v1/models) - {self._compatible_install_url('ds4')}"
        )
        self.console.print(
            f"    [5] llama.cpp (/v1/models) - {self._compatible_install_url('llama_cpp')}"
        )
        self.console.print(
            f"    [6] LM Studio (/v1/models) - {self._compatible_install_url('lm_studio')}"
        )
        self.console.print("    [7] Other OpenAI-compatible (/v1/models then /api/tags)")
        default_num = {
            "ollama": "1",
            "unsloth": "2",
            "omlx": "3",
            "ds4": "4",
            "llama_cpp": "5",
            "lm_studio": "6",
            "other": "7",
        }[default_choice]
        try:
            raw = self._plain_prompt_session.prompt(
                [("class:prompt", f"  Select endpoint type [{default_num}]: ")],
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        selected = (raw or default_num).strip().lower()
        if selected in {"1", "ollama", "o"}:
            return "ollama"
        if selected in {"2", "unsloth", "u"}:
            return "unsloth"
        if selected in {"3", "omlx", "m"}:
            return "omlx"
        if selected in {"4", "ds4", "deepseek", "deepseek-v4"}:
            return "ds4"
        if selected in {"5", "llama.cpp", "llama_cpp", "llamacpp", "llama-cpp"}:
            return "llama_cpp"
        if selected in {"6", "lmstudio", "lm_studio", "lm-studio", "lm studio"}:
            return "lm_studio"
        if selected in {"7", "other", "custom", "k"}:
            return "other"
        self.console.print("  [dim]Invalid selection; using generic compatible mode.[/dim]")
        return "other"

    @staticmethod
    def _ollama_tags_url_from_base(base_url: str) -> str:
        """Build an Ollama /api/tags URL from an OpenAI-compatible base URL."""
        parsed = urlparse(str(base_url or "").strip())
        path = (parsed.path or "").rstrip("/")
        if path.endswith("/v1"):
            path = path[:-3]
        tags_path = f"{path}/api/tags" if path else "/api/tags"
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                tags_path,
                "",
                "",
                "",
            )
        )
