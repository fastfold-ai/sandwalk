"""Shared implementation behind CLI keys and web integrations."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from agent.config import API_KEYS, CONFIG_DIR, Config
from agent_server.models import (
    IntegrationField,
    IntegrationProvider,
    IntegrationSetupResponse,
    IntegrationSetupStep,
    ValidateIntegrationResponse,
)

KEY_ALIASES = {
    "llm.anthropic_api_key": "anthropic",
    "llm.openai_api_key": "openai",
    "llm.openai_compatible_api_key": "openai-compatible",
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
    "custom-webhook": {
        "name": "Custom Webhook",
        "category": "Automation",
        "description": "Completion event webhook URL and signing secret.",
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
    "linear": {
        "name": "Linear",
        "category": "MCP",
        "description": "Linear MCP API key for issues and projects.",
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
        return "Scientific Services"
    if config_key.startswith("mcp."):
        return "MCP"
    return "Other"


class IntegrationsService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._providers: dict[str, list[tuple[str, dict]]] = {}
        for config_key, info in API_KEYS.items():
            key = str(
                info.get("provider_key")
                or KEY_ALIASES.get(config_key)
                or info["env_var"].lower().replace("_", "-")
            )
            self._providers.setdefault(key, []).append((config_key, info))

    @staticmethod
    def _masked(value: str, *, is_secret: bool = True) -> str | None:
        normalized = value.strip()
        if not normalized:
            return None
        if not is_secret:
            return normalized
        if len(normalized) <= 8:
            return "••••••••"
        return f"{normalized[:4]}…{normalized[-4:]}"

    def _provider(self, key: str, entries: list[tuple[str, dict]]) -> IntegrationProvider:
        config = Config.load()
        fields: list[IntegrationField] = []
        for config_key, info in entries:
            env_value = str(os.environ.get(info["env_var"]) or "").strip()
            config_value = str(config.get(config_key) or "").strip()
            value = env_value or config_value
            source = "environment" if env_value else "config" if config_value else "none"
            fields.append(
                IntegrationField(
                    env_var=str(info["env_var"]),
                    label=str(info["name"]),
                    is_secret=bool(info.get("secret", True)),
                    configured=bool(value),
                    source=source,
                    masked_preview=self._masked(
                        value,
                        is_secret=bool(info.get("secret", True)),
                    ),
                )
            )

        first_config_key, first_info = entries[0]
        metadata = PROVIDER_METADATA.get(key, {})
        configured_fields = [field for field in fields if field.configured]
        primary = configured_fields[0] if configured_fields else fields[0]
        return IntegrationProvider(
            key=key,
            name=str(metadata.get("name") or first_info["name"]),
            category=str(metadata.get("category") or category_for(first_config_key)),
            description=str(metadata.get("description") or first_info["description"]),
            env_var=fields[0].env_var,
            configured=bool(configured_fields),
            source=primary.source,
            masked_preview=primary.masked_preview,
            setup_url=str(first_info.get("url") or "") or None,
            free=all(bool(info.get("free")) for _, info in entries),
            fields=fields,
        )

    def list(self) -> list[IntegrationProvider]:
        return sorted(
            (
                self._provider(key, entries)
                for key, entries in self._providers.items()
            ),
            key=lambda provider: (provider.category, provider.name.lower()),
        )

    def get(self, key: str) -> IntegrationProvider | None:
        entries = self._providers.get(key)
        return self._provider(key, entries) if entries else None

    def update(self, key: str, values: dict[str, str]) -> IntegrationProvider:
        entries = self._providers.get(key)
        if entries is None:
            raise KeyError(key)
        by_env = {str(info["env_var"]): config_key for config_key, info in entries}
        normalized = {
            env_name: str(value).strip()
            for env_name, value in values.items()
            if env_name in by_env and str(value).strip()
        }
        if not normalized:
            raise ValueError("At least one integration value is required.")
        with self._lock:
            config = Config.load()
            for env_name, value in normalized.items():
                config.set(by_env[env_name], value)
            config.save()
        return self._provider(key, entries)

    def remove(self, key: str) -> IntegrationProvider:
        entries = self._providers.get(key)
        if entries is None:
            raise KeyError(key)
        with self._lock:
            config = Config.load()
            for config_key, _ in entries:
                config.unset(config_key)
            config.save()
        return self._provider(key, entries)

    def validate(self, key: str) -> ValidateIntegrationResponse:
        provider = self.get(key)
        if provider is None:
            raise KeyError(key)
        return ValidateIntegrationResponse(
            ok=provider.configured,
            configured=provider.configured,
            source=provider.source,
            message=(
                f"{provider.name} is configured."
                if provider.configured
                else f"{provider.name} is not configured."
            ),
        )

    @staticmethod
    def _extract_env_value(text: str, env_name: str) -> str:
        for line in text.splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            if key.strip() != env_name:
                continue
            return value.strip().strip('"').strip("'")
        return ""

    @staticmethod
    def _fetch_vercel_oidc_token_via_cli(cwd: Path) -> tuple[str, str]:
        vercel_path = shutil.which("vercel")
        if not vercel_path:
            return "", "Vercel CLI is not installed."
        with tempfile.TemporaryDirectory(prefix="fastfold-vercel-token-") as tmp:
            env_file = Path(tmp) / ".env.local"
            result = subprocess.run(
                [
                    vercel_path,
                    "env",
                    "pull",
                    str(env_file),
                    "--yes",
                    "--environment=development",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=45,
                cwd=str(cwd),
            )
            if result.returncode != 0:
                stderr = str(result.stderr or "").strip()
                stdout = str(result.stdout or "").strip()
                detail = stderr or stdout or "vercel env pull failed."
                return "", detail
            try:
                content = env_file.read_text(encoding="utf-8")
            except OSError:
                return "", "Unable to read pulled .env file."
            token = IntegrationsService._extract_env_value(content, "VERCEL_OIDC_TOKEN")
            if not token:
                return "", "VERCEL_OIDC_TOKEN was not found in pulled env."
            return token, ""

    @staticmethod
    def _vercel_workspace_dir() -> Path:
        path = VERCEL_INTEGRATION_DIR.resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def autofill(self, key: str) -> IntegrationProvider:
        entries = self._providers.get(key)
        if entries is None:
            raise KeyError(key)
        if key != "skills-sh":
            raise ValueError("Auto-import is currently available only for Skills.sh.")
        workspace_dir = self._vercel_workspace_dir()

        token = str(os.environ.get("VERCEL_OIDC_TOKEN") or "").strip()
        if not token:
            token, _ = self._fetch_vercel_oidc_token_via_cli(workspace_dir)
            token = token.strip()
        if not token:
            raise ValueError(
                "Unable to auto-import Vercel OIDC token. Run:\n"
                f'cd "{workspace_dir}"\n'
                "vercel login\n"
                "vercel link\n"
                "vercel env pull .env.local --environment=development\n"
                "(or set VERCEL_OIDC_TOKEN), then retry."
            )

        with self._lock:
            config = Config.load()
            config.set("api.vercel_oidc_token", token)
            config.save()
        return self._provider(key, entries)

    def setup(self, key: str, _working_directory: str | None = None) -> IntegrationSetupResponse:
        entries = self._providers.get(key)
        if entries is None:
            raise KeyError(key)
        if key != "skills-sh":
            raise ValueError("Setup wizard is currently available only for Vercel.")
        project_dir = self._vercel_workspace_dir()
        steps: list[IntegrationSetupStep] = []
        steps.append(
            IntegrationSetupStep(
                id="workspace",
                label="Prepare integration workspace",
                ok=True,
                detail=f"Using {project_dir} for Vercel linking and env pull.",
            )
        )

        env_token = str(os.environ.get("VERCEL_OIDC_TOKEN") or "").strip()
        if env_token:
            steps.append(
                IntegrationSetupStep(
                    id="env-token",
                    label="Check environment token",
                    ok=True,
                    detail="VERCEL_OIDC_TOKEN found in current server environment.",
                )
            )
            with self._lock:
                config = Config.load()
                config.set("api.vercel_oidc_token", env_token)
                config.save()
            steps.append(
                IntegrationSetupStep(
                    id="save-token",
                    label="Save token to /keys",
                    ok=True,
                    detail="Imported token into local FastFold config.",
                )
            )
            return IntegrationSetupResponse(
                ok=True,
                integration_key=key,
                summary="Vercel token imported from environment.",
                steps=steps,
            )

        vercel_path = shutil.which("vercel")
        cli_ok = bool(vercel_path)
        steps.append(
            IntegrationSetupStep(
                id="cli",
                label="Check Vercel CLI",
                ok=cli_ok,
                detail=(
                    "Vercel CLI detected."
                    if cli_ok
                    else "Install Vercel CLI (`npm i -g vercel`)."
                ),
            )
        )
        if not cli_ok:
            return IntegrationSetupResponse(
                ok=False,
                integration_key=key,
                summary="Vercel CLI is not installed.",
                steps=steps,
            )

        linked = (project_dir / ".vercel" / "project.json").is_file()
        steps.append(
            IntegrationSetupStep(
                id="linked-project",
                label="Check linked project",
                ok=linked,
                detail=(
                    f"Linked Vercel project detected in {project_dir}."
                    if linked
                    else (
                        f"No linked Vercel project in {project_dir}. Run:\n"
                        f'cd "{project_dir}"\n'
                        "vercel login\n"
                        "vercel link"
                    )
                ),
            )
        )
        if not linked:
            return IntegrationSetupResponse(
                ok=False,
                integration_key=key,
                summary="Project is not linked to Vercel.",
                steps=steps,
            )

        token, pull_error = self._fetch_vercel_oidc_token_via_cli(project_dir)
        pull_ok = bool(token)
        steps.append(
            IntegrationSetupStep(
                id="env-pull",
                label="Pull Vercel environment",
                ok=pull_ok,
                detail=(
                    "Pulled Vercel environment and found VERCEL_OIDC_TOKEN."
                    if pull_ok
                    else pull_error
                    or "Unable to pull environment or locate token."
                ),
            )
        )
        if not pull_ok:
            return IntegrationSetupResponse(
                ok=False,
                integration_key=key,
                summary="Could not fetch Vercel OIDC token.",
                steps=steps,
            )

        with self._lock:
            config = Config.load()
            config.set("api.vercel_oidc_token", token)
            config.save()
        steps.append(
            IntegrationSetupStep(
                id="save-token",
                label="Save token to /keys",
                ok=True,
                detail="Imported token into local FastFold config.",
            )
        )
        return IntegrationSetupResponse(
            ok=True,
            integration_key=key,
            summary="Vercel token imported successfully.",
            steps=steps,
        )
