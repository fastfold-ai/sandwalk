"""Mixin: _prompt_profile_template_backend."""

from __future__ import annotations

class _ProfileTemplateBackendMixin:
    def _prompt_profile_template_backend(self, default_backend: str = "ollama") -> str | None:
        """Prompt for compatible profile template backend."""
        normalized_default = str(default_backend or "").strip().lower()
        if normalized_default not in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}:
            normalized_default = "ollama"
        self.console.print("  [cyan]Profile template[/cyan]")
        self.console.print(
            f"    [1] Ollama - {self._compatible_install_url('ollama')}"
        )
        self.console.print(
            f"    [2] Unsloth - {self._compatible_install_url('unsloth')}"
        )
        self.console.print(
            f"    [3] oMLX - {self._compatible_install_url('omlx')}"
        )
        self.console.print(
            f"    [4] DS4 (DeepSeek v4) - {self._compatible_install_url('ds4')}"
        )
        self.console.print(
            f"    [5] llama.cpp - {self._compatible_install_url('llama_cpp')}"
        )
        self.console.print(
            f"    [6] LM Studio - {self._compatible_install_url('lm_studio')}"
        )
        self.console.print(
            "    [7] Other compatible endpoint"
        )
        default_num = {
            "ollama": "1",
            "unsloth": "2",
            "omlx": "3",
            "ds4": "4",
            "llama_cpp": "5",
            "lm_studio": "6",
            "other": "7",
        }[normalized_default]
        try:
            raw = self._plain_prompt_session.prompt(
                [("class:prompt", f"  Select template [{default_num}]: ")]
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        selected = raw or default_num
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
        self.console.print("  [dim]Invalid selection.[/dim]")
        return None
