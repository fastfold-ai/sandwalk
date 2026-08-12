"""Push saved auth settings into a running local sandwalk serve / menubar."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_server.auth_settings.paths import settings_dir


@dataclass(frozen=True)
class AuthApplyResult:
    ok: bool
    method: str
    message: str


def control_file_path() -> Path:
    return settings_dir() / "control.json"


def read_control_plane() -> dict[str, Any] | None:
    path = control_file_path()
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def _http_json(
    url: str,
    *,
    method: str = "POST",
    headers: dict[str, str] | None = None,
    timeout: float = 2.5,
) -> tuple[int, dict[str, Any] | None]:
    req = urllib.request.Request(
        url=url,
        method=method,
        headers=headers or {},
        data=b"" if method.upper() != "GET" else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            parsed = json.loads(body) if body.strip() else {}
            if not isinstance(parsed, dict):
                parsed = {}
            return int(resp.status), parsed
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
            parsed = json.loads(body) if body.strip() else {}
            if not isinstance(parsed, dict):
                parsed = {}
        except Exception:
            parsed = {}
        return int(exc.code), parsed
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return 0, None


def _serve_port_from_settings() -> int | None:
    path = settings_dir() / "settings.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    server = raw.get("server")
    if not isinstance(server, dict):
        return None
    port = server.get("port")
    if isinstance(port, int) and port > 0:
        return port
    if isinstance(port, str) and port.isdigit():
        return int(port)
    return None


def _candidate_api_bases(control: dict[str, Any] | None) -> list[str]:
    """Agent API bases only — never the menubar control-plane port (18787)."""
    bases: list[str] = []
    if control:
        api_base = str(control.get("api_base") or "").strip().rstrip("/")
        if api_base:
            # Force loopback host; reload rejects non-loopback clients.
            if "://" in api_base:
                try:
                    from urllib.parse import urlparse

                    parsed = urlparse(api_base)
                    if parsed.port:
                        bases.append(f"http://127.0.0.1:{parsed.port}")
                except Exception:
                    bases.append(api_base)
            else:
                bases.append(api_base)
    configured = _serve_port_from_settings()
    if configured:
        bases.append(f"http://127.0.0.1:{configured}")
    bases.append("http://127.0.0.1:8787")
    out: list[str] = []
    seen: set[str] = set()
    for base in bases:
        if base in seen:
            continue
        seen.add(base)
        out.append(base)
    return out


def try_hot_reload_auth(api_bases: list[str] | None = None) -> AuthApplyResult | None:
    """Ask a running agent server to reload auth from disk (loopback)."""
    for base in api_bases or _candidate_api_bases(read_control_plane()):
        status, payload = _http_json(f"{base}/v1/auth/reload", method="POST")
        if status == 200 and payload and payload.get("ok") is True:
            return AuthApplyResult(
                ok=True,
                method="hot-reload",
                message=f"Reloaded auth on running server ({base}).",
            )
        if status == 404:
            continue
        if status == 403:
            continue
    return None


def try_menubar_restart(control: dict[str, Any] | None = None) -> AuthApplyResult | None:
    """Restart services via the macOS menubar control plane (same as Security Save)."""
    plane = control if control is not None else read_control_plane()
    if not plane:
        return None
    token = str(plane.get("token") or "").strip()
    host = str(plane.get("host") or "127.0.0.1").strip() or "127.0.0.1"
    port = plane.get("port")
    if not token or not isinstance(port, int) or port <= 0:
        return None
    # Control plane is always loopback.
    url = f"http://127.0.0.1:{port}/v1/control/restart"
    status, payload = _http_json(
        url,
        method="POST",
        headers={
            "authorization": f"Bearer {token}",
            "x-sandwalk-token": token,
        },
        timeout=8.0,
    )
    if status == 200:
        return AuthApplyResult(
            ok=True,
            method="menubar-restart",
            message="Restarted Sandwalk Server via the menubar app (same as Security → Save).",
        )
    detail = ""
    if payload and isinstance(payload.get("error"), str):
        detail = f" ({payload['error']})"
    return AuthApplyResult(
        ok=False,
        method="menubar-restart",
        message=f"Menubar control plane returned HTTP {status or 'unreachable'}{detail}.",
    )


def apply_saved_auth_to_runtime() -> AuthApplyResult:
    """After CLI writes settings.json, refresh the live server if one is running.

    Order:
    1. Hot-reload ``POST /v1/auth/reload`` on loopback (fast; no process bounce).
    2. Menubar ``POST /v1/control/restart`` when ``control.json`` is present.
    3. Advise a manual restart.
    """
    control = read_control_plane()
    reloaded = try_hot_reload_auth(_candidate_api_bases(control))
    if reloaded and reloaded.ok:
        return reloaded

    restarted = try_menubar_restart(control)
    if restarted and restarted.ok:
        return restarted
    if restarted and not restarted.ok:
        return AuthApplyResult(
            ok=False,
            method=restarted.method,
            message=(
                f"{restarted.message} Settings were saved — restart Sandwalk "
                "from the menubar (or `sandwalk serve`) to apply the new key."
            ),
        )

    return AuthApplyResult(
        ok=False,
        method="none",
        message=(
            "Settings saved. No running Sandwalk Server detected — start it "
            "(menubar or `sandwalk serve`) to use the new auth settings."
        ),
    )
