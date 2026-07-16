"""`sandwalk fork` / `sandwalk agent fork` — import a shared cloud chat locally."""

import os
from urllib.parse import quote

import typer

from _version import __version__
from cli.agents_api import _agents_api_get_json, _normalize_share_id, _resolve_agents_api_base_url
from cli.app import app, console, spinner
from cli.fork_import import _fork_build_trajectory, _fork_restore_files, _fork_track_analytics

agent_app = typer.Typer(help="Fork and import shared cloud sessions")
app.add_typer(agent_app, name="agent")


@app.command("fork")
@agent_app.command("fork")
def fork_cmd(
    share_id: str = typer.Argument(
        ...,
        help="Cloud share / session ID, or full /agents/share/<id> URL",
    ),
    agents_api_url: str | None = typer.Option(
        None,
        "--agents-api-url",
        envvar="FASTFOLD_AGENTS_API_URL",
        help="Agents API base URL (defaults to FASTFOLD_AGENTS_API_URL or https://agents-api.fastfold.ai/v1)",
    ),
    fastfold_api_key: str | None = typer.Option(
        None,
        "--fastfold-api-key",
        envvar="FASTFOLD_API_KEY",
        help="Optional Fastfold Cloud API key (required for restricted-email shared chats)",
    ),
    include_files: bool = typer.Option(
        True,
        "--include-files/--no-files",
        help="Download shared files into local sandbox.output_dir/shared_forks/<share_id>",
    ),
):
    """Fork a shared cloud chat into a local CLI + Web UI session."""
    from agent.config import Config
    from agent_server.session_sync import import_trajectory
    from agent_server.store import AgentStore

    try:
        cfg = Config.load()
        resolved_share_id = _normalize_share_id(share_id)
        base_url = _resolve_agents_api_base_url(agents_api_url)
        resolved_key = (
            str(fastfold_api_key or "").strip()
            or str(os.environ.get("FASTFOLD_API_KEY") or "").strip()
            or str(cfg.get("api.fastfold_cloud_key") or "").strip()
        )

        headers = {
            "Accept": "application/json",
            "User-Agent": f"sandwalk/{__version__}",
        }
        if resolved_key:
            headers["X-Fastfold-Api-Key"] = resolved_key

        encoded_share_id = quote(resolved_share_id, safe="")
        with spinner("Fetching shared session metadata..."):
            bootstrap = _agents_api_get_json(base_url, f"/shares/{encoded_share_id}", headers=headers)
            history = _agents_api_get_json(base_url, f"/shares/{encoded_share_id}/history", headers=headers)
        thread = bootstrap.get("thread") if isinstance(bootstrap.get("thread"), dict) else {}
        title = str(thread.get("title") or "Imported shared session").strip()
        messages = history.get("messages") if isinstance(history.get("messages"), list) else []

        with spinner("Reconstructing local session trajectory..."):
            trajectory, session_id = _fork_build_trajectory(messages, thread, resolved_share_id, title)

        share_files_count = share_folders_count = restored_files = 0
        restored_root = None
        if include_files:
            share_files_count, share_folders_count, restored_files, restored_root = _fork_restore_files(
                base_url, encoded_share_id, headers, cfg, resolved_share_id, session_id, console
            )

        # Import into the shared SQLite store so the Web UI lists this chat
        # immediately (same path as `sandwalk sync`).
        with spinner("Syncing forked session into the Web UI database..."):
            ui_sync_action = import_trajectory(
                AgentStore(),
                trajectory,
                force=True,
                mark_recent=True,
            )

        fork_count = _fork_track_analytics(base_url, encoded_share_id, headers)

        console.print("[green]Imported shared session locally.[/green]")
        console.print(f"  [dim]Share ID:[/dim] {resolved_share_id}")
        console.print(f"  [dim]Session ID:[/dim] {session_id}")
        console.print(f"  [dim]Session file:[/dim] {trajectory.session_path(session_id)}")
        console.print(f"  [dim]Web UI sync:[/dim] {ui_sync_action}")
        console.print(f"  [dim]Messages imported:[/dim] {len(messages)}")
        if include_files and restored_root is not None:
            console.print(f"  [dim]Shared files:[/dim] {share_files_count}")
            console.print(f"  [dim]Shared folders:[/dim] {share_folders_count}")
            console.print(f"  [dim]Files restored:[/dim] {restored_files}")
            console.print(f"  [dim]Restore location:[/dim] {restored_root}")
        else:
            console.print("  [dim]File import:[/dim] skipped (--no-files)")
        if fork_count is not None:
            console.print(f"  [dim]Fork count:[/dim] {fork_count}")
        console.print(f"  [cyan]Resume in CLI:[/cyan] sandwalk --resume {session_id}")
        console.print(
            "  [cyan]Open in Web UI:[/cyan] sandwalk serve (or sandwalk.app) → Agents"
        )
    except RuntimeError as exc:
        message = str(exc)
        if " 404 " in f" {message} " and "/shares/" in message:
            console.print(
                "[red]Shared session not found.[/red]\n"
                "  Check the share ID or URL, and ensure the link still exists."
            )
            raise typer.Exit(code=2)
        if " 401 " in f" {message} " or " 403 " in f" {message} ":
            console.print(
                "[red]Access denied for this shared session.[/red]\n"
                "  This share may be restricted by email. Set FASTFOLD_API_KEY "
                "from an allowed account and retry."
            )
            raise typer.Exit(code=2)
        console.print(f"[red]Could not fork shared session.[/red]\n  {message}")
        raise typer.Exit(code=2)
    except ValueError as exc:
        console.print(f"[red]Invalid input:[/red] {exc}")
        raise typer.Exit(code=2)
