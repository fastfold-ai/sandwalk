"""Static integration key aliases, provider metadata, and category rules."""

from __future__ import annotations

from agent.config import CONFIG_DIR

KEY_ALIASES = {
    "llm.anthropic_api_key": "anthropic",
    "llm.openai_api_key": "openai",
    "api.fastfold_cloud_key": "fastfold-cloud",
    "api.boltz_api_key": "boltz",
    "api.ibm_rxn_key": "ibm-rxn",
    "api.lens_key": "lens",
    "notification.sendgrid_api_key": "sendgrid",
    "compute.lambda_api_key": "lambda-labs",
    "compute.runpod_api_key": "runpod",
}

PROVIDER_METADATA = {
    "modal": {
        "name": "Modal",
        "category": "Agent Runtime",
        "description": "Modal runtime credentials and on-demand GPU compute.",
    },
    "langsmith": {
        "name": "LangSmith",
        "category": "Observability",
        "description": "LangChain tracing API keys and project overrides.",
    },
    "nvidia": {
        "name": "NVIDIA",
        "category": "AI Models",
        "description": "NVIDIA API key overrides for model inference.",
    },
    "opencode": {
        "name": "OpenCode Zen",
        "category": "AI Models",
        "description": "OpenCode Zen pay-as-you-go gateway for curated coding models.",
    },
    "moonshot": {
        "name": "Kimi",
        "category": "AI Models",
        "description": "Kimi API key for first-party Kimi models.",
    },
    "deepseek": {
        "name": "DeepSeek",
        "category": "AI Models",
        "description": "DeepSeek API key for first-party DeepSeek models.",
    },
    "minimax": {
        "name": "MiniMax",
        "category": "AI Models",
        "description": "MiniMax API key for first-party MiniMax models.",
    },
    "mistral": {
        "name": "Mistral",
        "category": "AI Models",
        "description": "Mistral API key for first-party Mistral models.",
    },
    "qwen": {
        "name": "Qwen",
        "category": "AI Models",
        "description": "Qwen (Alibaba DashScope) API key for first-party Qwen models.",
    },
    "together": {
        "name": "Together AI",
        "category": "AI Models",
        "description": (
            "Together AI OpenAI-compatible API — curated open models behind one key."
        ),
    },
    "tavily": {
        "name": "Tavily",
        "category": "Search",
        "description": "Tavily search API key used by research tools.",
    },
    "slack": {
        "name": "Slack",
        "category": "Communication",
        "description": "Slack reports and agent notifications.",
    },
    "skills-sh": {
        "name": "Vercel",
        "category": "Skills",
        "description": "Vercel OIDC token for skills.sh catalog search.",
    },
    "tamarind": {
        "name": "Tamarind Bio",
        "category": "MCP",
        "description": "Tamarind Bio MCP credentials for structure and design jobs.",
    },
    "neurosnap": {
        "name": "Neurosnap",
        "category": "MCP",
        "description": "Neurosnap MCP API key for computational biology jobs.",
    },
    "paperclip": {
        "name": "Paperclip",
        "category": "MCP",
        "description": "Paperclip MCP API key for biomedical literature search and synthesis.",
    },
    "linear": {
        "name": "Linear",
        "category": "MCP",
        "description": "Linear MCP API key for issues and projects.",
    },
    "huggingface": {
        "name": "Hugging Face",
        "category": "MCP",
        "description": (
            "Hugging Face Hub MCP — models, datasets, Spaces, papers, and docs."
        ),
    },
}
VERCEL_INTEGRATION_DIR = (CONFIG_DIR / "vercel-integration").expanduser()


def category_for(config_key: str) -> str:
    if config_key.startswith("llm."):
        return "AI Models"
    if config_key.startswith("compute."):
        return "Compute"
    if config_key.startswith("notification."):
        return "Notifications"
    if config_key.startswith("api."):
        return "API"
    if config_key.startswith("mcp."):
        return "MCP"
    return "Other"
