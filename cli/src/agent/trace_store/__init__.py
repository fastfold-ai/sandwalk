"""
Trace store: full-fidelity capture of agent message streams.

Captures the complete sequence of text blocks, tool calls, and tool results
from each query execution. Used by the notebook exporter and other
downstream consumers that need richer data than the compact Trajectory.

Operates independently of Trajectory — Trajectory stores compact turn
summaries for LLM context injection; TraceStore captures the full stream
for export/replay.

Split into `helpers.py` (session paths, meta parsing, plot embedding) and
`store.py` (the TraceStore class) to stay under the file-length cap;
re-exported here so `from agent.trace_store import ...` keeps working
unchanged.
"""

from .helpers import TRACE_META_MARKER, parse_trace_meta
from .helpers import sessions_dir as _sessions_dir
from .store import TraceStore

__all__ = ["TRACE_META_MARKER", "TraceStore", "parse_trace_meta"]
