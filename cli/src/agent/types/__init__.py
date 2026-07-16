"""
Core data types for the agent pipeline.

Defines Plan, Step, Clarification, and ExecutionResult — the data structures
shared across the planner, executor, runner, and UI layers.

Split into `plan.py` (Plan/Step/Clarification) and `result.py`
(ExecutionResult) to stay under the file-length cap; re-exported here so
`from agent.types import ...` keeps working unchanged.
"""

from .plan import Clarification, Plan, Step
from .result import ExecutionResult

__all__ = ["Clarification", "ExecutionResult", "Plan", "Step"]
