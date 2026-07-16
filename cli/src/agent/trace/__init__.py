"""Lightweight trace logger used by CLI trace diagnostics/export commands.

Split into `recording.py` (event recorders), `persistence.py`
(save/load/to_text), and `diagnostics.py` (diagnostics/query_summaries)
mixins combined in `logger.py`; re-exported here so
`from agent.trace import TraceLogger` keeps working unchanged.
"""

from .logger import TraceLogger

__all__ = ["TraceLogger"]
