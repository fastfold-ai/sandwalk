"""PlanMermaidMixin: freeform-plan step parsing and Mermaid flowchart helpers.

Used to document the required diagram shape for plan-mode markdown files.
Approval/Y-n preview was removed — plan mode writes ``plans/*.md`` instead.
"""

from __future__ import annotations

import re


class PlanMermaidMixin:
    """Helpers for extracting plan steps and building Mermaid flowcharts."""

    @staticmethod
    def _extract_plan_preview_steps(proposed_plan: str, *, max_steps: int = 12) -> list[str]:
        """Extract step-like lines from freeform plan text."""
        if not proposed_plan:
            return []
        steps: list[str] = []
        in_code_block = False
        for raw_line in str(proposed_plan).splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if line.startswith("#"):
                continue
            normalized = line
            numbered = re.match(r"^\d+\s*[\.\)]\s+(.*)$", line)
            if numbered:
                normalized = numbered.group(1).strip()
            else:
                bulleted = re.match(r"^[-*]\s+(.*)$", line)
                if bulleted:
                    normalized = bulleted.group(1).strip()
                else:
                    step_prefix = re.match(
                        r"^step\s*\d+\s*[:\-]\s*(.*)$", line, flags=re.IGNORECASE
                    )
                    if step_prefix:
                        normalized = step_prefix.group(1).strip()
            if not normalized:
                continue
            if normalized.lower() in {"proposed plan", "plan", "execution plan"}:
                continue
            steps.append(normalized)
            if len(steps) >= max_steps:
                break
        if not steps:
            compact = " ".join(str(proposed_plan or "").split())
            if compact:
                steps.append(compact[:140])
        return steps

    @staticmethod
    def _sanitize_mermaid_label(text: str, *, max_len: int = 72) -> str:
        """Escape text for Mermaid node labels."""
        label = " ".join(str(text or "").split())
        if len(label) > max_len:
            label = label[: max_len - 3] + "..."
        label = label.replace("\\", "\\\\").replace('"', '\\"')
        label = label.replace("[", "(").replace("]", ")")
        return label

    def _plan_preview_mermaid_markdown(self, proposed_plan: str) -> str:
        """Build a Mermaid flowchart markdown block from plan step text."""
        steps = self._extract_plan_preview_steps(proposed_plan)
        if not steps:
            return ""
        lines = [
            "```mermaid",
            "flowchart TD",
            '    start([User Query])',
        ]
        for idx, step in enumerate(steps, start=1):
            lines.append(f'    s{idx}["{self._sanitize_mermaid_label(step)}"]')
        lines.append("    start --> s1")
        for idx in range(2, len(steps) + 1):
            lines.append(f"    s{idx - 1} --> s{idx}")
        lines.append("    done([Done])")
        lines.append(f"    s{len(steps)} --> done")
        lines.append("```")
        return "\n".join(lines)


# Backward-compatible alias used by older imports/tests.
PlanPreviewMixin = PlanMermaidMixin
