"""`sandwalk serve` — start the local or explicitly exposed agent server."""

from pathlib import Path

import typer

from cli.app import app, console


@app.command("serve")
def serve_cmd(
    host: str = typer.Option("127.0.0.1", "--host", help="HTTP bind address"),
    port: int = typer.Option(8787, "--port", min=1, max=65535, help="HTTP bind port"),
    public: bool = typer.Option(
        False,
        "--public",
        help=(
            "Expose on the LAN (non-loopback). Implied by --host 0.0.0.0. "
            "Requires an API key (`sandwalk auth enable`); defaults allow "
            "desktop origins and any Host header."
        ),
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        envvar="FASTFOLD_SERVER_API_KEY",
        help="Backend bearer token (or FASTFOLD_SERVER_API_KEY)",
        hide_input=True,
    ),
    allowed_origin: list[str] = typer.Option(
        None,
        "--allowed-origin",
        help="Allowed browser origin; repeat for multiple origins",
    ),
    allowed_host: list[str] = typer.Option(
        None,
        "--allowed-host",
        help="Allowed Host header; repeat for multiple hosts",
    ),
    uds: Path | None = typer.Option(
        None,
        "--uds",
        help="Serve over a user-scoped Unix domain socket instead of TCP",
    ),
    tls_cert: Path | None = typer.Option(
        None,
        "--tls-cert",
        envvar="SANDWALK_TLS_CERT",
        help="PEM cert for HTTPS/HTTP/2 (requires hypercorn + --tls-key)",
    ),
    tls_key: Path | None = typer.Option(
        None,
        "--tls-key",
        envvar="SANDWALK_TLS_KEY",
        help="PEM private key for HTTPS/HTTP/2",
    ),
):
    """Start the local or explicitly exposed FastFold agent server."""
    from agent_server.main import run_server

    try:
        run_server(
            host=host,
            port=port,
            public=public,
            api_key=api_key,
            allowed_origins=allowed_origin,
            allowed_hosts=allowed_host,
            uds=uds,
            tls_cert=tls_cert,
            tls_key=tls_key,
        )
    except ValueError as exc:
        console.print(f"[red]Server configuration error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
