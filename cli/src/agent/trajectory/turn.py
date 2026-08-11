"""Turn dataclass: a single query-answer turn in a session."""

import time
from dataclasses import dataclass, field


@dataclass
class Turn:
    """A single query-answer turn in a session."""
    query: str
    answer: str
    entities: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
