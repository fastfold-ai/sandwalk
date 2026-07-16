"""Provider metadata: first-party OpenAI-compatible providers and local profile defaults."""

# First-party providers that speak the OpenAI-compatible protocol. Each routes
# through the OpenAI SDK / LangChain "openai:" path with a fixed base URL and its
# own API key. Set discover_models=true to fetch the live catalog from /v1/models
# when an API key is configured (used by OpenCode Go).
OPENAI_COMPATIBLE_PROVIDERS: dict[str, dict[str, str]] = {
    "xai": {
        "base_url": "https://api.x.ai/v1",
        "config_key": "llm.xai_api_key",
        "env_var": "XAI_API_KEY",
        "label": "xAI",
        "signup_url": "https://console.x.ai",
        "default_model": "grok-4.5",
    },
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "config_key": "llm.google_api_key",
        "env_var": "GEMINI_API_KEY",
        "label": "Google Gemini",
        "signup_url": "https://aistudio.google.com/apikey",
        "default_model": "gemini-3.5-flash",
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "config_key": "api.nvidia_api_key",
        "env_var": "NVIDIA_API_KEY",
        "label": "NVIDIA",
        "signup_url": "https://build.nvidia.com/settings/api-keys",
        "default_model": "nvidia/nemotron-3-ultra-550b-a55b",
    },
    "opencode": {
        "base_url": "https://opencode.ai/zen/v1",
        "config_key": "llm.opencode_api_key",
        "env_var": "OPENCODE_API_KEY",
        "label": "OpenCode Zen",
        "signup_url": "https://opencode.ai/zen",
        "default_model": "kimi-k2.7-code",
        "discover_models": "true",
    },
}

OPENAI_PROFILE_DEFAULTS = {
    "openai": {
        "label": "OpenAI Cloud",
        "base_url": "https://api.openai.com/v1",
        "discovery": ["v1_models"],
        "default_model": "gpt-5.6-sol",
        "install_url": "https://platform.openai.com/api-keys",
    },
    "ollama": {
        "label": "Ollama Local",
        "base_url": "http://localhost:11434/v1",
        "discovery": ["ollama_tags", "v1_models"],
        "default_model": "llama3.1",
        "install_url": "https://github.com/ollama/ollama",
    },
    "unsloth": {
        "label": "Unsloth Local",
        "base_url": "http://localhost:8888/v1",
        "discovery": ["v1_models"],
        "default_model": "gpt-oss",
        "install_url": "https://github.com/unslothai/unsloth",
    },
    "omlx": {
        "label": "oMLX Local",
        "base_url": "http://localhost:8000/v1",
        "discovery": ["v1_models"],
        "default_model": "diffusiongemma-26B-A4B-it-4bit",
        "install_url": "https://github.com/jundot/omlx",
    },
    "ds4": {
        "label": "DS4 Local",
        "base_url": "http://localhost:8000/v1",
        "discovery": ["v1_models"],
        "default_model": "deepseek-v4-flash",
        "install_url": "https://github.com/antirez/ds4",
    },
    "llama_cpp": {
        "label": "llama.cpp Local",
        "base_url": "http://localhost:8080/v1",
        "discovery": ["v1_models"],
        "default_model": "llama3.1",
        "install_url": "https://github.com/ggml-org/llama.cpp",
    },
    "lm_studio": {
        "label": "LM Studio Local",
        "base_url": "http://localhost:1234/v1",
        "discovery": ["v1_models"],
        "default_model": "llama3.1",
        "install_url": "https://lmstudio.ai/docs/developer/openai-compat",
    },
    "other": {
        "label": "Custom Compatible Endpoint",
        "base_url": "http://localhost:11434/v1",
        "discovery": ["v1_models", "ollama_tags"],
        "default_model": "llama3.1",
        "install_url": "",
    },
}
