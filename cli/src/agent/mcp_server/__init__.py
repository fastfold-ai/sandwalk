"""
Shared tool handlers for the deepagents runtime.

Wraps the ct ToolRegistry so each registered tool can be invoked as a handler,
and provides the persistent ``run_python`` / ``run_r`` sandbox handlers used by
the deepagents LangChain tool layer.

Split into `formatting.py` (result formatting + JSON Schema conversion),
`tool_handler.py` (registry tool handler factory), `run_python_handler.py`
(the run_python sandbox handler), and `run_r_handler.py` (the run_r handler)
to stay under the file-length cap; re-exported here so
`from agent.mcp_server import ...` keeps working unchanged.
"""

from .formatting import _format_tool_result, _params_to_json_schema
from .run_python_handler import _make_run_python_handler
from .run_r_handler import _make_run_r_handler
from .tool_handler import _make_tool_handler

__all__ = [
    "_format_tool_result",
    "_make_run_python_handler",
    "_make_run_r_handler",
    "_make_tool_handler",
    "_params_to_json_schema",
]
