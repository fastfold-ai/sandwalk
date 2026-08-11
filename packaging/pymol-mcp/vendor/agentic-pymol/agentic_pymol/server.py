"""MCP server entry point.

Importing this module triggers tool registration. `main()` runs the
FastMCP server over stdio.
"""

from __future__ import annotations
import logging

import agentic_pymol.tools as tools
from agentic_pymol.app import _mcp_log_level, mcp

__all__ = ["tools"]


def main() -> None:
    # FastMCP already configured logging at import; re-apply so PYMOL_MCP_LOG
    # wins even if the process was started with a noisier default.
    level_name = _mcp_log_level()
    from mcp.server.fastmcp.utilities.logging import configure_logging

    configure_logging(level_name)
    logging.getLogger().setLevel(level_name)
    logging.getLogger("pymol-mcp").setLevel(level_name)
    logging.getLogger("mcp").setLevel(max(getattr(logging, level_name), logging.WARNING))
    mcp.run()


if __name__ == "__main__":
    main()
