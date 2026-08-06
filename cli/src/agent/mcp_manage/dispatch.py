"""`handle_mcp_argv`: top-level dispatcher for `sandwalk mcp` / `/mcp`."""

from __future__ import annotations

from rich.console import Console

from .connect_actions import handle_catalog, handle_connect, handle_disconnect
from .crud_actions import handle_add, handle_remove
from .install_actions import handle_doctor, handle_install
from .resolve import _service, _store
from .status import print_mcp_status
from .toggle_actions import handle_enable_disable, handle_validate

_HELP_TEXT = """
[bold]mcp[/bold] — list and manage MCP servers

  mcp / mcp list              Status (catalog + registered)
  mcp catalog                 Suggested cloud defaults
  mcp install pymol           Managed local PyMOL MCP launcher + enable
  mcp doctor [pymol]          Check launcher / token / probe
  mcp connect <id> [--api-key KEY]
  mcp disconnect <id>
  mcp enable|disable <id>
  mcp validate|tools <id>     Probe tools/list
  mcp add <name> --url URL
  mcp add <name> --command CMD [--arg ...]
  mcp remove <id|name>

Uses langchain-mcp-adapters MultiServerMCPClient (stdio / sse / streamable_http + headers).
Suggested servers: pymol, tamarind, latch, neurosnap, paperclip, linear
"""


def handle_mcp_argv(args: list[str], console: Console) -> int:
    """
    Execute mcp subcommand args (without leading 'mcp').

    Returns process-style exit code (0 ok, 1 error, 2 usage).
    """
    if not args or args[0] in {"list", "status", "ls"}:
        print_mcp_status(console)
        return 0

    action = args[0].lower()
    store = _store()
    service = _service(store)

    if action == "catalog":
        return handle_catalog(args, console, service=service)
    if action == "install":
        return handle_install(args, console, store=store, service=service)
    if action == "doctor":
        return handle_doctor(args, console, store=store, service=service)
    if action == "connect":
        return handle_connect(args, console, service=service)
    if action == "disconnect":
        return handle_disconnect(args, console, service=service)
    if action in {"enable", "disable"}:
        return handle_enable_disable(action, args, console, store=store, service=service)
    if action in {"validate", "tools", "probe"}:
        return handle_validate(action, args, console, store=store, service=service)
    if action == "add":
        return handle_add(args, console, store=store)
    if action in {"remove", "rm", "delete"}:
        return handle_remove(args, console, store=store, service=service)
    if action in {"help", "-h", "--help"}:
        console.print(_HELP_TEXT)
        return 0

    console.print(f"  [red]Unknown mcp action:[/red] {action}")
    console.print("  [dim]Try:[/dim] mcp help")
    return 2
