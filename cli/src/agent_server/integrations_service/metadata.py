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


def _tool(
    tool_id: str,
    label: str,
    description: str,
    *,
    requirement: str = "built_in",
) -> dict[str, str]:
    return {
        "kind": "tool",
        "id": tool_id,
        "label": label,
        "description": description,
        "requirement": requirement,
    }


def _skill(name: str, label: str, description: str) -> dict[str, str]:
    return {
        "kind": "skill",
        "id": name,
        "label": label,
        "description": description,
        "source": f"fastfold-ai/skills@skills/{name}",
        "requirement": "install",
    }


def _capability(
    capability_id: str,
    label: str,
    description: str,
    *,
    requirement: str = "built_in",
    installable: bool = False,
) -> dict[str, str | bool]:
    return {
        "kind": "capability",
        "id": capability_id,
        "label": label,
        "description": description,
        "requirement": requirement,
        "installable": installable,
    }


def _notice(notice_id: str, label: str, description: str) -> dict[str, str]:
    return {
        "kind": "notice",
        "id": notice_id,
        "label": label,
        "description": description,
        "requirement": "not_wired",
    }


_GPU_COMPUTE_UNLOCKS = [
    _tool(
        "compute.submit_job",
        "Submit GPU jobs",
        "Submit real cloud GPU jobs after the tool's default dry-run preview.",
    ),
    _tool(
        "compute.job_status",
        "Check GPU job status",
        "Check a previously submitted provider job.",
    ),
    _tool(
        "structure.dock",
        "Molecular docking",
        "Run docking workloads on the configured GPU provider.",
    ),
    _tool(
        "structure.md_simulate",
        "Molecular dynamics",
        "Run OpenMM or GROMACS molecular dynamics workloads.",
    ),
    _tool(
        "structure.fep",
        "Free energy perturbation",
        "Run relative binding free-energy calculations.",
    ),
]


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
        "unlocks": [
            _notice(
                "langsmith-not-wired",
                "No direct Sandwalk integration",
                "The credentials are exported for compatible libraries, but no "
                "Sandwalk tool currently enables LangSmith tracing explicitly.",
            )
        ],
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
        "name": "Qwen Cloud",
        "category": "AI Models",
        "description": "Qwen Cloud API key for first-party Qwen models (OpenAI-compatible).",
    },
    "together": {
        "name": "Together AI",
        "category": "AI Models",
        "description": (
            "Together AI OpenAI-compatible API — curated open models behind one key."
        ),
    },
    "openrouter": {
        "name": "OpenRouter",
        "category": "AI Models",
        "description": (
            "OpenRouter multi-provider gateway — attributed to sandwalk.sh rankings."
        ),
    },
    "cerebras": {
        "name": "Cerebras",
        "category": "AI Models",
        "description": "Cerebras Cloud wafer-scale inference (LangChain ChatCerebras).",
    },
    "groq": {
        "name": "Groq",
        "category": "AI Models",
        "description": "Groq LPU inference for open models (LangChain ChatGroq).",
    },
    "fireworks": {
        "name": "Fireworks AI",
        "category": "AI Models",
        "description": "Fireworks AI hosted models (LangChain ChatFireworks).",
    },
    "meta": {
        "name": "Meta (Muse)",
        "category": "AI Models",
        "description": "Meta Model API for Muse Wonder and Muse Spark.",
    },
    "bedrock": {
        "name": "Amazon Bedrock",
        "category": "AI Models",
        "description": (
            "Amazon Bedrock via IAM / AWS CLI profile (LangChain Converse). "
            "Optional access keys for CI machines without the AWS CLI."
        ),
    },
    "tavily": {
        "name": "Tavily",
        "category": "MCP",
        "description": "Tavily MCP credentials for real-time web search and extraction.",
    },
    "exa": {
        "name": "Exa",
        "category": "MCP",
        "description": (
            "Exa MCP credentials for web search, page fetch, and research "
            "(papers, patents, molecules)."
        ),
    },
    "slack": {
        "name": "Slack",
        "category": "Communication",
        "description": "Use your agents from a Slack workspace — complete Relay Agent and Socket Mode support.",
        "unlocks": [
            _tool(
                "slack.send_message",
                "Send Slack messages",
                "Reply in a Slack channel or thread through a connected workspace.",
                requirement="connector",
            ),
        ],
    },
    "skills-sh": {
        "name": "Vercel",
        "category": "Skills",
        "description": "Vercel OIDC token for skills.sh catalog search.",
        "unlocks": [
            _capability(
                "skills-sh-catalog",
                "skills.sh catalog",
                "Search, inspect, and audit skills from the authenticated desktop catalog.",
                requirement="ambient",
            ),
            _capability(
                "npx-skills-cli",
                "npx skills CLI",
                "Required for Skills.sh-compatible installs (`npx skills add` / find).",
                requirement="install",
                installable=True,
            ),
        ],
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
        "category": "Data",
        "description": (
            "Hub access token for gated datasets (BixBench) and optional Hub MCP "
            "tools — models, Spaces, papers, and docs. MCP install is optional."
        ),
        "unlocks": [
            _capability(
                "hf-hub-token",
                "Hub downloads",
                "Unlock gated Hugging Face datasets used by Benchmarking "
                "(BixBench-Verified-50) and capsule downloads.",
                requirement="ambient",
            ),
            _notice(
                "hf-mcp-optional",
                "Optional Hub MCP",
                "Want Hub search tools in chat? Install the Hugging Face MCP "
                "from the MCP catalog — it reuses this same token.",
            ),
        ],
    },
    "ibm-rxn": {
        "unlocks": [
            _tool(
                "chemistry.retrosynthesis",
                "IBM RXN retrosynthesis",
                "Use IBM RXN for retrosynthetic route planning before the built-in "
                "heuristic fallback.",
            )
        ],
    },
    "lens": {
        "unlocks": [
            _tool(
                "literature.patent_search",
                "Lens patent search",
                "Use Lens.org as the preferred patent source before EPO and PubMed "
                "fallbacks.",
            )
        ],
    },
    "fastfold-cloud": {
        "unlocks": [
            _skill(
                "fold",
                "Protein folding",
                "Submit and retrieve FastFold structure predictions.",
            ),
            _skill(
                "protein_design_boltzgen",
                "BoltzGen protein design",
                "Run FastFold BoltzGen design workflows.",
            ),
            _skill(
                "md_openmm_calvados",
                "CALVADOS + OpenMM",
                "Run coarse-grained molecular dynamics workflows.",
            ),
            _skill(
                "md_openmmdl",
                "OpenMMDL",
                "Run atomistic molecular dynamics workflows.",
            ),
            _skill(
                "slack_report",
                "Slack reports",
                "Publish research reports through FastFold Cloud.",
            ),
            _capability(
                "slack-relay-agent",
                "Slack Relay Agent",
                "Connect paid Slack workspaces through FastFold Cloud’s Agent "
                "relay — no Socket Mode tokens needed.",
                requirement="ambient",
            ),
        ],
    },
    "boltz": {
        "unlocks": [
            _skill(
                "boltz",
                "Boltz API workflows",
                "Run structure, binding, design, screening, and ADME workflows.",
            ),
            _capability(
                "boltz-api-cli",
                "boltz-api CLI",
                "The Boltz skill invokes the official CLI, which must also be installed.",
                requirement="install",
                installable=True,
            ),
        ],
    },
    "sendgrid": {
        "unlocks": [
            _tool(
                "notification.send_email",
                "Send email",
                "Send non-dry-run email notifications through SendGrid.",
            ),
            _tool(
                "cro.send_inquiry",
                "Send CRO inquiries",
                "Deliver drafted CRO inquiry emails through notification.send_email.",
            ),
        ],
    },
    "lambda-labs": {
        "unlocks": _GPU_COMPUTE_UNLOCKS,
    },
    "runpod": {
        "unlocks": _GPU_COMPUTE_UNLOCKS,
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
