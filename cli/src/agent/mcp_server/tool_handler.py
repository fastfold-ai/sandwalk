"""Async handler factory for registry (ct) domain tools."""

from __future__ import annotations

import asyncio
import logging
from contextvars import ContextVar
from typing import Any

from .formatting import _format_tool_result

logger = logging.getLogger("mcp_server")

# Per-run session for cached LangChain tools (set in run_existing_agent).
tool_session_var: ContextVar[Any] = ContextVar("sandwalk_tool_session", default=None)


def _make_tool_handler(tool_obj, session):
    """Create an async handler for a registry tool.

    The handler runs the synchronous tool function in a thread to avoid
    blocking the event loop. Session is read from ``tool_session_var`` at
    call time so the StructuredTool list can be reused across concurrent chats.
    """

    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        bound = tool_session_var.get()
        call_session = bound if bound is not None else session
        # Inject session and prior results (empty for SDK mode)
        call_args = dict(args)
        call_args["_session"] = call_session
        call_args["_prior_results"] = {}

        # Coerce string values to numeric types when they look like numbers.
        # MCP sends all parameters as strings, but tools often expect int/float.
        for key, val in list(call_args.items()):
            if key.startswith("_"):
                continue
            if isinstance(val, str):
                # Try int first, then float
                try:
                    call_args[key] = int(val)
                    continue
                except ValueError:
                    pass
                try:
                    call_args[key] = float(val)
                    continue
                except ValueError:
                    pass
                # Boolean coercion
                if val.lower() in ("true", "false"):
                    call_args[key] = val.lower() == "true"

        try:
            result = await asyncio.to_thread(tool_obj.run, **call_args)
            text = _format_tool_result(result)
        except Exception as e:
            logger.warning("Tool %s raised: %s", tool_obj.name, e)
            text = f"Error: {e}"
            return {
                "content": [{"type": "text", "text": text}],
                "is_error": True,
            }

        return {"content": [{"type": "text", "text": text}]}

    return handler
