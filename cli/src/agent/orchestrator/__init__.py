"""
Multi-agent research orchestrator for ct.

Decomposes complex queries into N independent research threads, executes them
in parallel via ThreadPoolExecutor, shares findings through an EvidenceBoard,
and merges results into a single coherent report.

Single-agent by default. Multi-agent only when explicitly requested via
--agents N, /agents N, or auto-suggested for complex queries.
"""

import logging

from rich.live import Live

from agent.evidence_board import EvidenceBoard
from agent.orchestrator.auto_save import AutoSaveMixin
from agent.orchestrator.merge import MergeMixin
from agent.orchestrator.models import OrchestratorResult, ThreadGoal, ThreadResult
from agent.orchestrator.planning import PlanningMixin
from agent.orchestrator.prompts import META_PLANNER_SYSTEM_PROMPT
from agent.orchestrator.run import RunMixin
from agent.orchestrator.thread_execution import ThreadExecutionMixin
from agent.session import Session
from agent.trajectory import Trajectory
from ui.status import ThinkingStatus

__all__ = [
    "META_PLANNER_SYSTEM_PROMPT",
    "OrchestratorResult",
    "ResearchOrchestrator",
    "ThreadGoal",
    "ThreadResult",
]

logger = logging.getLogger("orchestrator")


class ResearchOrchestrator(
    RunMixin, PlanningMixin, ThreadExecutionMixin, MergeMixin, AutoSaveMixin,
):
    """Orchestrates parallel multi-agent research threads."""

    def __init__(self, session: Session, n_threads: int = 3,
                 trajectory: Trajectory = None):
        self.session = session
        self.console = session.console
        max_threads = int(session.config.get("agent.parallel_max_threads", 5))
        self.n_threads = min(max(n_threads, 1), max_threads)
        self.trajectory = trajectory
        self.evidence_board = EvidenceBoard()

    def _thinking_status(self, label: str) -> ThinkingStatus:
        """Context manager wrapper so ``ThinkingStatus`` stays patchable here."""
        return ThinkingStatus(self.console, label)

    def _live_display(self, renderable) -> Live:
        """Context manager wrapper so ``Live`` stays patchable here."""
        return Live(renderable, console=self.console, refresh_per_second=6)
