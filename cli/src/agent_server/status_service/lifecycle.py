"""Server stop/restart lifecycle helpers for the Status page."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
import time

from agent_server.models import ServerLifecycleResult


def _lifecycle_allowed() -> bool:
    if os.environ.get("FASTFOLD_DISABLE_SERVER_LIFECYCLE") == "1":
        return False
    if "PYTEST_CURRENT_TEST" in os.environ:
        return False
    return True


def _build_restart_command() -> list[str] | None:
    host = os.environ.get("FASTFOLD_SERVE_HOST", "127.0.0.1")
    port = os.environ.get("FASTFOLD_SERVE_PORT", "8787")
    public = os.environ.get("FASTFOLD_SERVE_PUBLIC") == "1"
    api_key = (os.environ.get("FASTFOLD_SERVER_API_KEY") or "").strip()
    origins = [
        part.strip()
        for part in os.environ.get("FASTFOLD_SERVE_ORIGINS", "").split(",")
        if part.strip()
    ]
    hosts = [
        part.strip()
        for part in os.environ.get("FASTFOLD_SERVE_HOSTS", "").split(",")
        if part.strip()
    ]
    uds = (os.environ.get("FASTFOLD_SERVE_UDS") or "").strip()

    binary = shutil.which("sandwalk") or shutil.which("fastfold")
    if binary:
        cmd = [binary, "serve"]
    else:
        cmd = [sys.executable, "-m", "cli", "serve"]

    if uds:
        cmd.extend(["--uds", uds])
    else:
        cmd.extend(["--host", host, "--port", port])
    if public:
        cmd.append("--public")
        if api_key:
            cmd.extend(["--api-key", api_key])
        for origin in origins:
            cmd.extend(["--allowed-origin", origin])
        for allowed in hosts:
            cmd.extend(["--allowed-host", allowed])
    return cmd


def schedule_stop() -> ServerLifecycleResult:
    # Lazy self-lookup (not a direct module-global call) so tests that
    # monkeypatch `agent_server.status_service._lifecycle_allowed` are honored
    # even though this function lives in a submodule of that package.
    from agent_server import status_service

    if not status_service._lifecycle_allowed():
        return ServerLifecycleResult(
            ok=True,
            action="stop",
            message="Stop scheduled (dry-run; lifecycle disabled).",
        )

    def _stop() -> None:
        time.sleep(0.35)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=_stop, name="server-stop", daemon=True).start()
    return ServerLifecycleResult(
        ok=True,
        action="stop",
        message="Server is shutting down.",
    )


def schedule_restart() -> ServerLifecycleResult:
    cmd = _build_restart_command()
    if cmd is None:
        return ServerLifecycleResult(
            ok=False,
            action="restart",
            message="Unable to build restart command.",
        )

    from agent_server import status_service

    if not status_service._lifecycle_allowed():
        return ServerLifecycleResult(
            ok=True,
            action="restart",
            message="Restart scheduled (dry-run; lifecycle disabled).",
        )

    def _restart() -> None:
        time.sleep(0.4)
        try:
            subprocess.Popen(  # noqa: S603 — intentional self-relaunch
                cmd,
                start_new_session=True,
                env=os.environ.copy(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        finally:
            os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=_restart, name="server-restart", daemon=True).start()
    return ServerLifecycleResult(
        ok=True,
        action="restart",
        message="Server is restarting.",
    )
