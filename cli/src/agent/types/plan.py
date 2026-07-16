"""Plan & Step data structures for the agent pipeline."""

from dataclasses import dataclass, field


@dataclass
class Step:
    """A single research step in a plan."""

    id: int
    description: str = ""
    tool: str = ""
    tool_args: dict = field(default_factory=dict)
    depends_on: list[int] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed
    result: dict | None = None


@dataclass
class Clarification:
    """Planner needs more information from the user before it can plan."""

    question: str
    missing: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class Plan:
    """A structured research plan."""

    query: str
    steps: list[Step] = field(default_factory=list)
    context: dict = field(default_factory=dict)

    def pending_steps(self) -> list[Step]:
        return [s for s in self.steps if s.status == "pending"]

    def ready_steps(self) -> list[Step]:
        """Steps whose dependencies are all completed."""
        completed_ids = {s.id for s in self.steps if s.status == "completed"}
        return [
            s
            for s in self.steps
            if s.status == "pending" and all(d in completed_ids for d in s.depends_on)
        ]

    def is_complete(self) -> bool:
        return all(s.status in ("completed", "failed") for s in self.steps)

    def summary(self) -> str:
        lines = [f"Plan: {self.query}", ""]
        for s in self.steps:
            status_icon = {"pending": " ", "running": ">", "completed": "+", "failed": "!"}
            icon = status_icon.get(s.status, "?")
            deps = f" (after {s.depends_on})" if s.depends_on else ""
            lines.append(f"  [{icon}] {s.id}. {s.description} [{s.tool}]{deps}")
        return "\n".join(lines)
