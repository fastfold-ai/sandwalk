"""Clarification request types raised mid-run when the planner needs input."""

from dataclasses import dataclass, field


@dataclass
class Clarification:
    """A request for user clarification before executing a query."""
    question: str
    missing: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class ClarificationNeeded(Exception):
    """Raised when the planner needs additional information."""

    def __init__(self, clarification: Clarification):
        self.clarification = clarification
        super().__init__(clarification.question)
