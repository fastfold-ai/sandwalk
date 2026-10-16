"""Live proof that the agent can use packages installed into its sandbox.

Runs against a Sandwalk server that is already up (``scripts/dev-api.sh`` or
the packaged app), drives it over HTTP, and asks a real model to call
``run_python``. Two paths are covered:

1. The user installs a catalog package from the Dashboard (here: the same API
   call the UI makes) and the agent imports it.
2. The agent installs a package on its own with ``environment.install_package``
   and then uses it.

Gated by ``RUN_LIVE_MODELS=1``. Costs a few tokens. Env:

- ``SANDWALK_API``      base URL, default ``http://127.0.0.1:8787``
- ``SANDWALK_API_KEY``  bearer key when the server has auth on
- ``SANDWALK_LIVE_PROVIDER`` / ``SANDWALK_LIVE_MODEL``  default
  ``openrouter`` / ``deepseek/deepseek-v4-flash-0731``
- ``SANDWALK_E2E_EVIDENCE``  directory that receives one JSON per test with
  the full transcript, so the run leaves a record

The test never prints or stores API keys.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

_RUN = os.environ.get("RUN_LIVE_MODELS", "").strip().lower() in {"1", "true", "yes"}
API = os.environ.get("SANDWALK_API", "http://127.0.0.1:8787").rstrip("/")
PROVIDER = os.environ.get("SANDWALK_LIVE_PROVIDER", "openrouter")
MODEL = os.environ.get("SANDWALK_LIVE_MODEL", "deepseek/deepseek-v4-flash-0731")
EVIDENCE_DIR = Path(
    os.environ.get("SANDWALK_E2E_EVIDENCE") or "/tmp/sandwalk-evidence"
)

# Catalog package the Dashboard offers; small and pure Python.
CATALOG_PACKAGE = "biopython"
CATALOG_MARKER = "BIO_OK"
# Not in the catalog, tiny, and almost never preinstalled, so the agent has
# to install it rather than find it already there.
AGENT_PACKAGE = "pyfiglet"
AGENT_MARKER = "FIGLET_OK"

pytestmark = pytest.mark.skipif(
    not _RUN, reason="Set RUN_LIVE_MODELS=1 and run a Sandwalk server first"
)


def _client() -> httpx.Client:
    headers = {"X-Sandwalk-Client": "ui"}
    key = (os.environ.get("SANDWALK_API_KEY") or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return httpx.Client(base_url=API, headers=headers, timeout=60.0)


def _wait_idle(client: httpx.Client, session_id: str, limit_s: float = 240.0) -> str:
    deadline = time.monotonic() + limit_s
    status = "unknown"
    while time.monotonic() < deadline:
        status = client.get(f"/v1/sessions/{session_id}").json().get("status", "")
        if status in {"idle", "error", "failed"}:
            return status
        time.sleep(2)
    return status


def _transcript(client: httpx.Client, session_id: str) -> list[dict]:
    return client.get(f"/v1/sessions/{session_id}/messages").json()["data"]


def _assistant_text(messages: list[dict]) -> str:
    return "\n".join(
        str(m.get("content") or "") for m in messages if m.get("role") == "assistant"
    )


def _record(name: str, payload: dict) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / f"{name}.json"
    payload = {"recorded_at": datetime.now(UTC).isoformat(), "api": API, **payload}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _importable_in_sandbox(report: dict, module: str) -> tuple[bool, str]:
    """Import ``module`` with the server's interpreter and its user site.

    ``run_python`` executes inside the server process, so the interpreter in
    the Environment report plus the user-site folder is what the agent sees.
    This runs that interpreter directly rather than trusting the chat text.
    """
    import subprocess

    python = report.get("pythonPath") or ""
    if not python or not Path(python).exists():
        return False, f"server interpreter not reachable from this machine: {python!r}"
    env = dict(os.environ)
    site = report.get("userSitePath")
    if site:
        env["PYTHONPATH"] = os.pathsep.join([site, env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    code = f"import {module}; print(getattr({module}, '__file__', '?'))"
    proc = subprocess.run(
        [python, "-c", code], capture_output=True, text=True, timeout=60, env=env
    )
    return proc.returncode == 0, (proc.stdout or proc.stderr).strip()


def _new_session(client: httpx.Client, title: str) -> str:
    response = client.post(
        "/v1/sessions",
        json={
            "title": title,
            "workspacePath": None,
            "projectId": None,
            "clientSurface": "ui",
            "provider": PROVIDER,
            "model": MODEL,
        },
    )
    response.raise_for_status()
    return response.json()["id"]


def _ask(client: httpx.Client, session_id: str, prompt: str) -> None:
    response = client.post(f"/v1/sessions/{session_id}/messages", json={"content": prompt})
    assert response.status_code in {200, 202}, response.text


@pytest.fixture(scope="module")
def api() -> httpx.Client:
    with _client() as client:
        health = client.get("/v1/health")
        assert health.status_code == 200, f"No Sandwalk server at {API}"
        yield client


def test_agent_uses_package_the_user_installed(api: httpx.Client) -> None:
    """Dashboard install → run_python import, in one server process."""
    env_before = api.get("/v1/environment").json()
    installed = api.post(
        "/v1/environment/packages/install", json={"name": CATALOG_PACKAGE}
    )
    assert installed.status_code == 200, installed.text
    result = installed.json()
    assert result["installed"] is True
    assert result.get("importModule"), "server could not import the package it installed"

    session_id = _new_session(api, "[live] user-installed package")
    prompt = (
        "Use the run_python tool to execute exactly this code and reply with only "
        "the printed lines:\n\n"
        "import Bio\n"
        "from Bio.Seq import Seq\n"
        f'print("{CATALOG_MARKER}", Bio.__version__, Bio.__file__)\n'
        'print("RC", Seq("ATGC").reverse_complement())'
    )
    _ask(api, session_id, prompt)
    status = _wait_idle(api, session_id)
    messages = _transcript(api, session_id)
    text = _assistant_text(messages)

    evidence = _record(
        "user_installed_package",
        {
            "provider": PROVIDER,
            "model": MODEL,
            "session_id": session_id,
            "install_result": result,
            "user_site_path": env_before.get("userSitePath"),
            "python_path": env_before.get("pythonPath"),
            "final_status": status,
            "transcript": messages,
        },
    )
    assert status == "idle", f"agent did not finish cleanly ({status}); see {evidence}"
    assert CATALOG_MARKER in text, f"agent output lacks {CATALOG_MARKER}; see {evidence}"
    assert "RC GCAT" in text, f"agent did not run the code; see {evidence}"


def test_agent_installs_a_package_on_its_own(api: httpx.Client) -> None:
    """ModuleNotFoundError → environment.install_package → run_python works."""
    # Start from a clean slate so the agent really has to install it.
    api.post("/v1/environment/packages/uninstall", json={"name": AGENT_PACKAGE})
    report = api.get("/v1/environment").json()
    present, _ = _importable_in_sandbox(report, AGENT_PACKAGE)
    assert not present, f"{AGENT_PACKAGE} was still importable before the test"

    session_id = _new_session(api, "[live] agent installs a package")
    prompt = (
        f"The Python package `{AGENT_PACKAGE}` is not installed in your sandbox. "
        "Install it yourself with the environment.install_package tool, then use "
        "run_python to execute exactly this code and reply with only the printed lines:\n\n"
        "import pyfiglet\n"
        f'print("{AGENT_MARKER}", pyfiglet.__version__)\n'
        'print(pyfiglet.figlet_format("hi", font="mini"))'
    )
    _ask(api, session_id, prompt)
    status = _wait_idle(api, session_id)
    messages = _transcript(api, session_id)
    text = _assistant_text(messages)
    env_after = api.get("/v1/environment").json()
    # The real check: is it importable by the interpreter run_python uses?
    # A model that works around the tool (its own venv under the workspace)
    # can still print the marker, so the chat text alone is not proof.
    now_importable, where = _importable_in_sandbox(env_after, AGENT_PACKAGE)

    evidence = _record(
        "agent_installed_package",
        {
            "provider": PROVIDER,
            "model": MODEL,
            "session_id": session_id,
            "package": AGENT_PACKAGE,
            "importable_in_sandbox_after": now_importable,
            "import_location": where,
            "python_path": env_after.get("pythonPath"),
            "user_site_path": env_after.get("userSitePath"),
            "final_status": status,
            "transcript": messages,
        },
    )
    assert status == "idle", f"agent did not finish cleanly ({status}); see {evidence}"
    assert AGENT_MARKER in text, f"agent never ran the code after installing; see {evidence}"
    assert now_importable, (
        f"{AGENT_PACKAGE} is not importable by the sandbox interpreter; the agent "
        f"did not use environment.install_package ({where}); see {evidence}"
    )
