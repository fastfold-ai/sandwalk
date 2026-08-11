"""Entity extraction and planner-context formatting for Trajectory."""

import re
import time

from .turn import Turn

_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)


class EntityMixin:
    """Adds entity extraction, `add_turn`, `context_for_planner`, and `entities`."""

    turns: list[Turn]
    max_turns: int
    updated_at: float

    def _extract_entities(self, text: str) -> list[str]:
        """Extract durable identifiers (e.g., UUID job IDs) from text."""
        if not text:
            return []
        return [m.group(0) for m in _UUID_PATTERN.finditer(text)]

    @staticmethod
    def _dedupe_preserve_order(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in items:
            if not item or item in seen:
                continue
            seen.add(item)
            out.append(item)
        return out

    def _turn_entities(self, turn: Turn) -> list[str]:
        """Resolve entities for a turn, deriving from text if missing."""
        if turn.entities:
            return self._dedupe_preserve_order([str(e) for e in turn.entities if str(e)])
        inferred = self._extract_entities(turn.query) + self._extract_entities(turn.answer)
        return self._dedupe_preserve_order(inferred)

    def add_turn(self, query: str, answer: str, plan=None):
        """Record a completed turn with entity extraction."""
        entities = self._dedupe_preserve_order(
            self._extract_entities(query) + self._extract_entities(answer)
        )
        tools_used = []
        if plan and hasattr(plan, "steps"):
            tools_used = [s.tool for s in plan.steps if s.status == "completed"]

        turn = Turn(
            query=query,
            answer=answer,
            entities=entities,
            tools_used=tools_used,
        )
        self.turns.append(turn)

        # Drop oldest turns if over limit
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]
        self.updated_at = time.time()

    def context_for_planner(self) -> str:
        """Format recent turns as context for the planner prompt."""
        if not self.turns:
            return ""

        recent = self.turns[-5:]
        recent_count = len(recent)
        lines = ["## Session Context (prior queries this session)", ""]
        for i, turn in enumerate(recent, 1):
            resolved_entities = self._turn_entities(turn)
            entities_str = ", ".join(resolved_entities) if resolved_entities else "none"
            tools_str = ", ".join(turn.tools_used) if turn.tools_used else "none"
            # Keep richer detail for the most recent turns so resumed sessions can
            # reliably reference prior findings without requiring a re-paste.
            if i >= max(1, recent_count - 1):
                preview_limit = 1400
            else:
                preview_limit = 320
            answer_preview = (
                turn.answer[:preview_limit] + "..."
                if len(turn.answer) > preview_limit
                else turn.answer
            )
            lines.append(f"**Turn {i}**: {turn.query}")
            lines.append(f"  Entities: {entities_str}")
            lines.append(f"  Tools: {tools_str}")
            lines.append(f"  Finding: {answer_preview}")
            lines.append("")

        all_entities = self.entities()
        if all_entities:
            lines.append(f"**All entities this session**: {', '.join(all_entities)}")
            lines.append("")

        lines.append(
            "Use this context to: reference prior findings, avoid repeating work, "
            "resolve ambiguous entity references (e.g., 'it', 'the compound')."
        )
        return "\n".join(lines)

    def entities(self) -> list[str]:
        """All unique entities mentioned across the session, preserving order."""
        seen = set()
        result = []
        for turn in self.turns:
            for entity in self._turn_entities(turn):
                if entity not in seen:
                    seen.add(entity)
                    result.append(entity)
        return result
