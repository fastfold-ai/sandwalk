"""Provider metadata: first-party OpenAI-compatible providers and local profile defaults."""

# Qwen Cloud plan endpoints (OpenAI-compatible). Keys are not interchangeable
# across plans — Token Plan / Coding Plan / pay-as-you-go each need their own
# base URL. Subscription keys often share the ``sk-sp-`` prefix, so Sandwalk
# discovers the working endpoint on live Test and persists ``llm.qwen_base_url``.
# Docs:
#   https://docs.qwencloud.com/token-plan/faq
#   https://docs.qwencloud.com/coding-plan/faq
#   https://docs.qwencloud.com/developer-guides/getting-started/first-api-call
QWEN_PAYGO_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
QWEN_CODING_BASE_URL = "https://coding-intl.dashscope.aliyuncs.com/v1"
QWEN_TOKEN_PLAN_BASE_URL = (
    "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
)
QWEN_SUBSCRIPTION_KEY_PREFIX = "sk-sp-"


def qwen_base_url_candidates(api_key: str | None = None) -> list[str]:
    """Ordered OpenAI-compatible base URLs to try for a Qwen Cloud API key."""
    key = (api_key or "").strip()
    if key.startswith(QWEN_SUBSCRIPTION_KEY_PREFIX):
        # Token Plan and Coding Plan both use sk-sp-; Token Plan first because
        # Coding Plan rejects non-coding-agent clients and returns a generic 401.
        return [
            QWEN_TOKEN_PLAN_BASE_URL,
            QWEN_CODING_BASE_URL,
            QWEN_PAYGO_BASE_URL,
        ]
    return [QWEN_PAYGO_BASE_URL, QWEN_TOKEN_PLAN_BASE_URL, QWEN_CODING_BASE_URL]


def normalize_qwen_base_url(url: str | None) -> str:
    """Normalize a user-pasted Qwen OpenAI-compatible base URL.

    Users often paste the host without ``/compatible-mode/v1`` (Token Plan and
    pay-as-you-go). Coding Plan uses bare ``/v1``.
    """
    text = (url or "").strip().rstrip("/")
    if not text:
        return ""
    lower = text.lower()
    if "compatible-mode" in lower or lower.endswith("/apps/anthropic"):
        return text
    if "coding-intl.dashscope.aliyuncs.com" in lower:
        return text if lower.endswith("/v1") else f"{text}/v1"
    if (
        "token-plan." in lower
        or "dashscope-intl.aliyuncs.com" in lower
        or "dashscope.aliyuncs.com" in lower
    ):
        if lower.endswith("/v1"):
            return f"{text[:-3]}/compatible-mode/v1"
        return f"{text}/compatible-mode/v1"
    return text


def resolve_qwen_base_url(
    api_key: str | None = None,
    *,
    configured: str | None = None,
) -> str:
    """Pick a Qwen Cloud base URL (persisted override wins, else first candidate)."""
    override = normalize_qwen_base_url(configured)
    if override:
        return override
    return qwen_base_url_candidates(api_key)[0]


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
        "base_url": QWEN_PAYGO_BASE_URL,
        "config_key": "llm.qwen_api_key",
        "env_var": "QWEN_API_KEY",
        # QwenCloud docs still document DASHSCOPE_API_KEY; accept either.
        "env_var_aliases": "DASHSCOPE_API_KEY",
        "label": "Qwen Cloud",
        "signup_url": "https://home.qwencloud.com/api-keys",
        "default_model": "qwen3.7-plus",
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
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "config_key": "llm.cerebras_api_key",
        "env_var": "CEREBRAS_API_KEY",
        "label": "Cerebras",
        "signup_url": "https://cloud.cerebras.ai",
        "default_model": "gpt-oss-120b",
        "discover_models": "true",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "config_key": "llm.groq_api_key",
        "env_var": "GROQ_API_KEY",
        "label": "Groq",
        "signup_url": "https://console.groq.com/keys",
        "default_model": "llama-3.3-70b-versatile",
        "discover_models": "true",
    },
    "fireworks": {
        "base_url": "https://api.fireworks.ai/inference/v1",
        "config_key": "llm.fireworks_api_key",
        "env_var": "FIREWORKS_API_KEY",
        "label": "Fireworks AI",
        "signup_url": "https://fireworks.ai/account/api-keys",
        "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
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
