"""LangChain tools for inspecting and controlling the chat sandbox.

Mirrors cloud agents-api ``check_thread_sandbox_status_tool`` /
``start_thread_sandbox_tool`` so the local agent can answer user requests like
"is my Modal sandbox running?" or "start/stop the sandbox".

Split into `formatting.py` (status payload/summary helpers),
`context.py` (the session-bound status/start/stop coroutines), and
`factory.py` (``create_sandbox_control_tools``) to stay under the
file-length cap; re-exported here so
`from agent.sandbox_control_tools import ...` keeps working unchanged.
"""

from .factory import create_sandbox_control_tools
from .formatting import SANDBOX_CONTROL_TOOL_NAMES

__all__ = ["SANDBOX_CONTROL_TOOL_NAMES", "create_sandbox_control_tools"]
