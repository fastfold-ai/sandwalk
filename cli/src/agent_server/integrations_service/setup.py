"""Vercel setup-wizard mixin for ``IntegrationsService``.

See :mod:`agent_server.integrations_service.vercel` for the module-object
monkeypatch note on ``shutil``.
"""

from __future__ import annotations

import os
import shutil

from agent.config import Config, sync_process_env_from_config
from agent_server.models import IntegrationSetupResponse, IntegrationSetupStep


class SetupMixin:
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
            return self._setup_from_env_token(key, env_token, steps)

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
                ok=False, integration_key=key, summary="Vercel CLI is not installed.", steps=steps
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
                ok=False, integration_key=key, summary="Project is not linked to Vercel.", steps=steps
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
                    else pull_error or "Unable to pull environment or locate token."
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

        return self._setup_save_token(key, token, steps, summary="Vercel token imported successfully.")

    def _setup_from_env_token(
        self, key: str, env_token: str, steps: list[IntegrationSetupStep]
    ) -> IntegrationSetupResponse:
        steps.append(
            IntegrationSetupStep(
                id="env-token",
                label="Check environment token",
                ok=True,
                detail="VERCEL_OIDC_TOKEN found in current server environment.",
            )
        )
        return self._setup_save_token(
            key, env_token, steps, summary="Vercel token imported from environment."
        )

    def _setup_save_token(
        self,
        key: str,
        token: str,
        steps: list[IntegrationSetupStep],
        *,
        summary: str,
    ) -> IntegrationSetupResponse:
        with self._lock:
            config = Config.load()
            config.set("api.vercel_oidc_token", token)
            config.save()
            os.environ["VERCEL_OIDC_TOKEN"] = token
            sync_process_env_from_config(config)
        steps.append(
            IntegrationSetupStep(
                id="save-token",
                label="Save token to /keys",
                ok=True,
                detail="Imported token into local FastFold config.",
            )
        )
        return IntegrationSetupResponse(
            ok=True, integration_key=key, summary=summary, steps=steps
        )
