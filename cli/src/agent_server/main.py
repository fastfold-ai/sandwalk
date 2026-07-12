"""Server launcher with fail-closed local and public modes."""

from __future__ import annotations

import os
from pathlib import Path


def run_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    public: bool = False,
    api_key: str | None = None,
    allowed_origins: list[str] | None = None,
    allowed_hosts: list[str] | None = None,
    uds: Path | None = None,
) -> None:
    import uvicorn

    log_config = None
    try:
        from agent.diagnostics import ensure_logging_configured, uvicorn_log_config

        log_path = ensure_logging_configured()
        # Drop prior httpx-probe spam from early diagnostics logging.
        try:
            log_path.write_text("", encoding="utf-8")
        except OSError:
            pass
        log_config = uvicorn_log_config(log_path)
    except Exception:
        pass

    origins = [value.strip().rstrip("/") for value in (allowed_origins or []) if value.strip()]
    hosts = [value.strip() for value in (allowed_hosts or []) if value.strip()]
    key = (api_key or "").strip() or None
    is_loopback = host in {"127.0.0.1", "localhost", "::1"}

    if uds is not None and public:
        raise ValueError("Unix-socket mode cannot be combined with --public.")
    if not is_loopback and not public:
        raise ValueError("Non-loopback binding requires --public.")
    if public and not key:
        raise ValueError("Public mode requires --api-key or FASTFOLD_SERVER_API_KEY.")
    if public and not origins:
        raise ValueError("Public mode requires at least one --allowed-origin.")
    if public and not hosts:
        raise ValueError("Public mode requires at least one --allowed-host.")

    if not origins:
        origins = [
            "http://127.0.0.1:8969",
            "http://localhost:8969",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]
    if not hosts:
        hosts = ["127.0.0.1", "localhost"]

    from agent_server.app import create_app

    # Persist bind options so Status → Restart can re-launch the same server.
    os.environ["FASTFOLD_SERVE_HOST"] = host
    os.environ["FASTFOLD_SERVE_PORT"] = str(port)
    os.environ["FASTFOLD_SERVE_PUBLIC"] = "1" if public else "0"
    os.environ["FASTFOLD_SERVE_ORIGINS"] = ",".join(origins)
    os.environ["FASTFOLD_SERVE_HOSTS"] = ",".join(hosts)
    if uds is not None:
        os.environ["FASTFOLD_SERVE_UDS"] = str(uds.expanduser().resolve())
    else:
        os.environ.pop("FASTFOLD_SERVE_UDS", None)
    if key:
        os.environ.setdefault("FASTFOLD_SERVER_API_KEY", key)

    app = create_app(
        api_key=key,
        allowed_origins=origins,
        allowed_hosts=hosts,
    )

    run_kwargs = {"log_level": "info"}
    if log_config is not None:
        run_kwargs["log_config"] = log_config

    if uds is not None:
        socket_path = uds.expanduser().resolve()
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        socket_path.unlink(missing_ok=True)
        previous_umask = os.umask(0o077)
        try:
            uvicorn.run(app, uds=str(socket_path), **run_kwargs)
        finally:
            os.umask(previous_umask)
            socket_path.unlink(missing_ok=True)
        return

    uvicorn.run(app, host=host, port=port, **run_kwargs)
