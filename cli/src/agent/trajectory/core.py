"""Trajectory: session memory across queries in interactive mode."""

import re
import time
from typing import Any

from .entities import EntityMixin
from .paths import PathsMixin
from .persistence import PersistenceMixin
from .turn import Turn

_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)


class Trajectory(EntityMixin, PathsMixin, PersistenceMixin):
    """Session memory: records turns and provides context for the planner."""

    def __init__(
        self,
        max_turns: int = 20,
        session_id: str | None = None,
        title: str | None = None,
    ):
        self.turns: list[Turn] = []
        self.max_turns = max_turns
        self.session_id: str | None = session_id
        self.title: str | None = title
        self.created_at = time.time()
        self.updated_at: float = self.created_at
        self.model: str | None = None
        self.usage_data: dict[str, Any] = {}
        self._uuid_pattern = _UUID_PATTERN
