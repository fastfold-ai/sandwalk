"""
Programmatic Tool Calling (PTC) support for the deepagents runtime.

Instead of exposing every domain tool as its own LangChain tool schema (which
adds a large, fixed input-token cost for ~190 tools on every model call), PTC
injects the domain tools as plain Python callables inside the persistent
``run_python`` sandbox. The model invokes them in code:

    res = tools.chemistry.descriptors(smiles="CCO")
    df = pd.DataFrame(res["table"])
    print(df.describe())          # only this returns to the model

This is the "code execution with MCP" / Programmatic Tool Calling pattern
(Anthropic; open-ptc-agent; CodeAct). The model only ever sees:

- a compact catalog (category counts + names-only listing) in the system prompt
  (built by :func:`build_tool_catalog`), and
- an on-demand ``search_tools`` tool (text from :func:`search_tools_text`) that
  returns exact signatures when asked.

The tools namespace itself is built by :func:`build_tools_namespace` and bound
into the sandbox via :meth:`agent.sandbox.Sandbox.inject_tools`.

Split into `common.py` (registry iteration + signature helpers),
`namespace.py` (build_tools_namespace), `catalog.py` (build_tool_catalog),
and `search.py` (search_tools_text) to stay under the file-length cap;
re-exported here so `from agent.ptc_tools import ...` keeps working
unchanged.
"""

from .catalog import build_tool_catalog
from .namespace import build_tools_namespace
from .search import search_tools_text

__all__ = ["build_tool_catalog", "build_tools_namespace", "search_tools_text"]
