"""OpenAI cloud vs. compatible-endpoint normalization/display helpers."""

from urllib.parse import urlparse


def _is_openai_managed_base_url(base_url: str | None) -> bool:
    """Return True for OpenAI-managed hosts, False for compatible gateways."""
    value = str(base_url or "").strip()
    if not value:
        return True
    try:
        host = (urlparse(value).hostname or "").strip().lower()
    except Exception:
        return False
    if not host:
        return False
    return host == "api.openai.com" or host.endswith(".openai.com")


def _normalize_openai_base_url(base_url: str | None) -> str | None:
    value = str(base_url or "").strip().rstrip("/")
    return value or None


def _normalize_compatible_backend_name(backend: str | None) -> str:
    """Normalize backend aliases to canonical compatible backend ids."""
    value = str(backend or "").strip().lower()
    aliases = {
        "ollama": "ollama",
        "unsloth": "unsloth",
        "omlx": "omlx",
        "ds4": "ds4",
        "deepseek": "ds4",
        "deepseek-v4": "ds4",
        "deepseek_4": "ds4",
        "llama.cpp": "llama_cpp",
        "llama_cpp": "llama_cpp",
        "llama-cpp": "llama_cpp",
        "llamacpp": "llama_cpp",
        "lmstudio": "lm_studio",
        "lm_studio": "lm_studio",
        "lm-studio": "lm_studio",
        "lm studio": "lm_studio",
        "custom": "other",
        "generic": "other",
        "other": "other",
    }
    return aliases.get(value, value)


def _compatible_backend_display_name(backend: str | None) -> str:
    """Return user-facing backend label."""
    backend_type = _normalize_compatible_backend_name(backend)
    if backend_type == "omlx":
        return "oMLX"
    if backend_type == "ollama":
        return "Ollama"
    if backend_type == "unsloth":
        return "Unsloth"
    if backend_type == "ds4":
        return "DS4"
    if backend_type == "llama_cpp":
        return "llama.cpp"
    if backend_type == "lm_studio":
        return "LM Studio"
    return "Custom"


def _compatible_default_endpoint(backend: str, fallback: str = "http://localhost:11434/v1") -> str:
    """Return the default endpoint URL for a compatible backend."""
    defaults = {
        "unsloth": "http://localhost:8888/v1",
        "omlx": "http://localhost:8000/v1",
        "ds4": "http://localhost:8000/v1",
        "llama_cpp": "http://localhost:8080/v1",
        "lm_studio": "http://localhost:1234/v1",
        "ollama": "http://localhost:11434/v1",
    }
    return defaults.get(_normalize_compatible_backend_name(backend), fallback)


def _compatible_install_url(backend: str) -> str:
    """Return install/reference URL for a compatible backend template."""
    backend_type = _normalize_compatible_backend_name(backend)
    urls = {
        "ollama": "https://github.com/ollama/ollama",
        "unsloth": "https://github.com/unslothai/unsloth",
        "omlx": "https://github.com/jundot/omlx",
        "ds4": "https://github.com/antirez/ds4",
        "llama_cpp": "https://github.com/ggml-org/llama.cpp",
        "lm_studio": "https://lmstudio.ai/docs/developer/openai-compat",
        "other": "",
    }
    return urls.get(backend_type, urls["other"])
