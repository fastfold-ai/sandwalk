"""Shared MCP list/manage helpers for `sandwalk mcp` and interactive `/mcp`.

Split into `resolve.py` (store/service/ref resolution), `status.py`
(print_mcp_status), `connect_actions.py` (catalog/connect/disconnect),
`toggle_actions.py` (enable/disable/validate), `crud_actions.py`
(add/remove), and `dispatch.py` (handle_mcp_argv) to stay under the
file-length cap; re-exported here so `from agent.mcp_manage import ...`
keeps working unchanged.
"""

from .dispatch import handle_mcp_argv
from .resolve import resolve_server_ref
from .status import print_mcp_status

__all__ = ["handle_mcp_argv", "print_mcp_status", "resolve_server_ref"]
