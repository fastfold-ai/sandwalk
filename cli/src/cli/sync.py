"""`sandwalk sync` — import legacy CLI JSONL sessions into the shared UI store."""

import typer

from cli.app import app, console


@app.command("sync")
def sync_cmd(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Re-import sessions even if they already exist in the shared database",
    ),
):
    """Import legacy CLI JSONL sessions into the shared SQLite store for the UI."""
    from agent_server.session_sync import sync_jsonl_sessions

    console.print(
        "  [cyan]Syncing legacy CLI sessions into the shared UI database…[/cyan]"
        + (" [dim](force)[/dim]" if force else "")
    )
    result = sync_jsonl_sessions(force=force)
    console.print(
        "  [green]Sync complete.[/green] "
        f"scanned={result.scanned} imported={result.imported} "
        f"updated={result.updated} skipped={result.skipped} failed={result.failed}"
    )
    if result.failed and result.details:
        for line in result.details:
            if "failed" in line:
                console.print(f"  [yellow]{line}[/yellow]")
    if result.imported or result.updated:
        console.print(
            "  [dim]Run `sandwalk serve` and open the local UI to continue these chats.[/dim]"
        )
