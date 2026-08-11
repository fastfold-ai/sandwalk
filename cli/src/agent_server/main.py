"""Server launcher with fail-closed local and public modes."""

from __future__ import annotations

import os
from pathlib import Path

# Long enough for in-flight requests to finish, short enough that a restart
# never looks stuck to whoever is waiting on it.
SHUTDOWN_GRACE_SECONDS = 5


def _signal_shutdown(app) -> None:
    """Ask long-lived streams to close before Uvicorn starts draining tasks."""
    app.state.shutdown_event.set()
    from agent_server.store.event_notifier import EVENT_NOTIFIER

    EVENT_NOTIFIER.wake_all()


def _serve(app, **kwargs) -> None:
    """Run Uvicorn with an early cooperative-shutdown hook."""
    import uvicorn

    class ShutdownAwareServer(uvicorn.Server):
        def handle_exit(self, sig, frame) -> None:
            _signal_shutdown(app)
            super().handle_exit(sig, frame)

    ShutdownAwareServer(uvicorn.Config(app, **kwargs)).run()


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
    # Non-loopback bind (Mac Network → Allow Remote, or `serve --host 0.0.0.0`)
    # implies public mode; callers may omit --public.
    if not is_loopback and not public:
        public = True

    # Load persisted auth; public mode can use settings key when CLI key omitted.
    from agent_server.auth_settings import load_settings, resolve_effective_api_key

    persisted = load_settings()
    effective = resolve_effective_api_key(cli_api_key=key, settings=persisted)
    if public and not effective:
        raise ValueError(
            "Public / LAN mode requires --api-key, FASTFOLD_SERVER_API_KEY, "
            "or `sandwalk auth enable` with a configured key "
            "(`sandwalk auth generate` then `sandwalk auth enable`)."
        )

    if not origins:
        if public:
            # Desktop + common local UI origins. Host header for LAN IPs is
            # covered by allowed_hosts=["*"] below.
            origins = [
                "tauri://localhost",
                "http://tauri.localhost",
                "http://127.0.0.1:1420",
                "http://localhost:1420",
                "http://127.0.0.1:8969",
                "http://localhost:8969",
                "http://127.0.0.1:5173",
                "http://localhost:5173",
            ]
        else:
            origins = [
                "http://127.0.0.1:8969",
                "http://localhost:8969",
                "http://127.0.0.1:5173",
                "http://localhost:5173",
            ]
    if not hosts:
        hosts = ["*"] if public else ["127.0.0.1", "localhost"]

    from agent_server.app import create_app
    from agent_server.store import AgentStoreCorruptedError, AgentStoreLockError

    # Match CLI Session: expose ~/.sandwalk config credentials to process env
    # so shell/skill subprocesses and PTYs see the same keys as interactive CLI.
    try:
        from agent.config import sync_process_env_from_config

        applied = sync_process_env_from_config()
        if applied:
            import logging

            logging.getLogger("agent_server").info(
                "Synced %d credential(s) from config into process env",
                len(applied),
            )
    except Exception:
        pass

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

    try:
        app = create_app(
            api_key=key,
            allowed_origins=origins,
            allowed_hosts=hosts,
        )
    except AgentStoreLockError as exc:
        raise SystemExit(f"Error: {exc}") from exc
    except AgentStoreCorruptedError as exc:
        raise SystemExit(f"Error: {exc}") from exc

    from agent_server.banner import print_server_banner

    print_server_banner(
        host=host,
        port=port,
        public=public,
        auth_enabled=bool(app.state.runtime_api_key),
        uds=uds,
        ui_available=bool(getattr(app.state, "ui_dist", None)),
    )

    run_kwargs = {
        "log_level": "info",
        # The desktop UI holds event streams open for as long as it is running,
        # and uvicorn's graceful shutdown waits for open connections forever.
        # Without a bound, SIGTERM leaves the server sitting in "Waiting for
        # connections to close" whenever the UI is up, and a restart looks hung
        # — which invites a hard kill on a database mid-write.
        "timeout_graceful_shutdown": SHUTDOWN_GRACE_SECONDS,
    }
    if log_config is not None:
        run_kwargs["log_config"] = log_config

    if uds is not None:
        socket_path = uds.expanduser().resolve()
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        socket_path.unlink(missing_ok=True)
        previous_umask = os.umask(0o077)
        try:
            _serve(app, uds=str(socket_path), **run_kwargs)
        finally:
            os.umask(previous_umask)
            socket_path.unlink(missing_ok=True)
        return

    _serve(app, host=host, port=port, **run_kwargs)
