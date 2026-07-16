"""Vercel OIDC auto-import mixin for ``IntegrationsService``.

Uses plain ``import shutil``/``import subprocess`` (not ``from x import y``) so
tests that monkeypatch ``agent_server.integrations_service.shutil.which`` /
``...subprocess.run`` patch the shared module objects these calls resolve
through, matching this module's behavior from before the split.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from agent.config import Config, sync_process_env_from_config
from agent_server.integrations_service.metadata import VERCEL_INTEGRATION_DIR
from agent_server.models import IntegrationProvider


class VercelMixin:
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
            token = VercelMixin._extract_env_value(content, "VERCEL_OIDC_TOKEN")
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
            os.environ["VERCEL_OIDC_TOKEN"] = token
            sync_process_env_from_config(config)
        return self._provider(key, entries)
