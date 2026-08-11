"""
Trajectory: session memory across queries in interactive mode.

Records queries, answers, entities mentioned, and tools used so the planner
can reference prior context ("earlier you found X, now also check Y").
Supports persistence to JSONL for session resume.

Split into `turn.py` (Turn dataclass), `entities.py` (entity extraction +
planner context), `paths.py` (session file resolution/listing), and
`persistence.py` (save/load/usage-data) mixins combined in `core.py`;
re-exported here so `from agent.trajectory import Trajectory, Turn` keeps
working unchanged.
"""

from .core import Trajectory
from .turn import Turn

__all__ = ["Trajectory", "Turn"]
