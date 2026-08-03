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
    "moonshot": {
        "base_url": "https://api.moonshot.ai/v1",
        "config_key": "llm.moonshot_api_key",
        "env_var": "MOONSHOT_API_KEY",
        "label": "Kimi",
        "signup_url": "https://platform.moonshot.ai/console/api-keys",
        "default_model": "kimi-k3",
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
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "config_key": "llm.deepseek_api_key",
        "env_var": "DEEPSEEK_API_KEY",
        "label": "DeepSeek",
        "signup_url": "https://platform.deepseek.com/api_keys",
        "default_model": "deepseek-v4-flash",
    },
    "minimax": {
        "base_url": "https://api.minimax.io/v1",
        "config_key": "llm.minimax_api_key",
        "env_var": "MINIMAX_API_KEY",
        "label": "MiniMax",
        "signup_url": "https://platform.minimax.io",
        "default_model": "MiniMax-M2.5",
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "config_key": "llm.mistral_api_key",
        "env_var": "MISTRAL_API_KEY",
        "label": "Mistral",
        "signup_url": "https://console.mistral.ai/api-keys",
        "default_model": "mistral-large-latest",
    },
    "qwen": {
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "config_key": "llm.qwen_api_key",
        "env_var": "DASHSCOPE_API_KEY",
        "label": "Qwen",
        "signup_url": "https://modelstudio.console.alibabacloud.com",
        "default_model": "qwen3-max",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "config_key": "llm.together_api_key",
        "env_var": "TOGETHER_API_KEY",
        "label": "Together AI",
        "signup_url": "https://api.together.xyz/settings/api-keys",
        "default_model": "zai-org/GLM-5.2",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "config_key": "llm.openrouter_api_key",
        "env_var": "OPENROUTER_API_KEY",
        "label": "OpenRouter",
        "signup_url": "https://openrouter.ai/keys",
        "default_model": "anthropic/claude-sonnet-5",
        # Discover live tool-capable models; new discoveries start disabled
        # (see catalog_discovery._seed_openrouter_discovered_hidden).
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
        "label": "Ollama",
        "base_url": "http://localhost:11434/v1",
        "discovery": ["ollama_tags", "v1_models"],
        "default_model": "llama3.1",
        "install_url": "https://github.com/ollama/ollama",
    },
    "unsloth": {
        "label": "Unsloth",
        "base_url": "http://localhost:8888/v1",
        "discovery": ["v1_models"],
        "default_model": "gpt-oss",
        "install_url": "https://github.com/unslothai/unsloth",
    },
    "omlx": {
        "label": "oMLX",
        "base_url": "http://localhost:8000/v1",
        "discovery": ["v1_models"],
        "default_model": "diffusiongemma-26B-A4B-it-4bit",
        "install_url": "https://github.com/jundot/omlx",
    },
    "ds4": {
        "label": "DS4",
        "base_url": "http://localhost:8000/v1",
        "discovery": ["v1_models"],
        "default_model": "deepseek-v4-flash",
        "install_url": "https://github.com/antirez/ds4",
    },
    "llama_cpp": {
        "label": "llama.cpp",
        "base_url": "http://localhost:8080/v1",
        "discovery": ["v1_models"],
        "default_model": "llama3.1",
        "install_url": "https://github.com/ggml-org/llama.cpp",
    },
    "lm_studio": {
        "label": "LM Studio",
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
