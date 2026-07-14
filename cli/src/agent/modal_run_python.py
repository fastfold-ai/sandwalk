"""Run ``run_python`` code inside an attached Modal sandbox when appropriate.

Host CT sandbox (``agent.sandbox.Sandbox``) cannot see Modal's ``/workspace``.
When a Modal session is active, general Python should execute remotely; only
PTC ``tools.*`` calls must stay on the host.
"""

from __future__ import annotations

import base64
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_HOST_PTC_RE = re.compile(r"\btools\s*\.")
_WORKSPACE_ROOT = "/workspace"


def code_requires_host_runtime(code: str) -> bool:
    """True when code needs the host PTC ``tools`` namespace / CT sandbox."""
    return bool(_HOST_PTC_RE.search(code or ""))


def rewrite_modal_workspace_paths(code: str, host_workspace: str) -> str:
    """Rewrite ``/workspace`` literals to the host session path for host exec."""
    host = str(host_workspace or "").rstrip("/")
    if not host or not code:
        return code
    out = code
    for quote in ("'", '"'):
        out = out.replace(f"{quote}{_WORKSPACE_ROOT}{quote}", f"{quote}{host}{quote}")
        out = out.replace(f"{quote}{_WORKSPACE_ROOT}/", f"{quote}{host}/")
    # Bare Path(/workspace/...) already covered by quoted forms above.
    return out


def execute_python_on_modal(
    handle: Any,
    code: str,
    *,
    timeout: int = 300,
) -> dict[str, Any]:
    """Execute Python source inside Modal; return a CT-sandbox-shaped dict."""
    payload = base64.b64encode((code or "").encode("utf-8")).decode("ascii")
    # Bootstrap: write script under /workspace, run with cwd=/workspace.
    # Avoid shell-quoting the user code by using base64 only.
    command = (
        "mkdir -p /workspace/artifacts /workspace/.sandwalk && "
        "python -c "
        "\"import base64,pathlib; "
        "pathlib.Path('/workspace/.sandwalk/_run_python.py')"
        f".write_bytes(base64.b64decode('{payload}'))\" && "
        "cd /workspace && python /workspace/.sandwalk/_run_python.py"
    )
    target = getattr(handle.backend, "default", handle.backend)
    try:
        response = target.execute(command, timeout=timeout)
    except TypeError:
        response = target.execute(command)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Modal run_python execute failed: %s", exc)
        return {
            "stdout": "",
            "error": f"Modal run_python failed: {exc}",
            "plots": [],
            "exports": [],
            "runtime": "modal",
        }

    output = ""
    exit_code = 0
    if response is None:
        output = ""
    elif isinstance(response, dict):
        output = str(response.get("output") or response.get("stdout") or "")
        exit_code = int(response.get("exit_code") or 0)
    else:
        output = str(getattr(response, "output", None) or "")
        exit_code = int(getattr(response, "exit_code", 0) or 0)

    error = None
    if exit_code != 0:
        error = output.strip() or f"Modal python exited with code {exit_code}"
        # Keep stdout empty-ish when the whole payload is the traceback.
        stdout = output
    else:
        stdout = output

    prefix = (
        "[run_python → Modal /workspace]\n"
        if stdout or error
        else "[run_python → Modal /workspace] (no output)\n"
    )
    return {
        "stdout": (prefix + stdout) if stdout else prefix.rstrip("\n"),
        "error": error,
        "plots": [],
        "exports": [],
        "runtime": "modal",
    }


def try_modal_run_python(
    *,
    session_id: str | None,
    code: str,
    timeout: int = 300,
) -> dict[str, Any] | None:
    """Return a Modal execution result, or None to fall back to the host sandbox."""
    if not session_id or code_requires_host_runtime(code):
        return None
    try:
        from agent.sandbox_backend import get_active_handle
    except Exception:  # noqa: BLE001
        return None
    handle = get_active_handle(session_id)
    if handle is None or getattr(handle, "kind", None) != "modal":
        return None
    return execute_python_on_modal(handle, code, timeout=timeout)
