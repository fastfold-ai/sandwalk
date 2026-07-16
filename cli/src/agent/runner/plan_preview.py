"""PlanPreviewMixin: freeform-plan parsing, Mermaid diagram rendering, and the
one-shot terminal plan-approval prompt for AgentRunner.

Split out of ``agent/runner.py`` (package conversion) to keep files under the
project line-count limit.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("runner")


class PlanPreviewMixin:
    """Plan-preview step run before tool execution when ``agent.plan_preview`` is set."""

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
            # Numbered list: "1. ...", "2) ..."
            numbered = re.match(r"^\d+\s*[\.\)]\s+(.*)$", line)
            if numbered:
                normalized = numbered.group(1).strip()
            else:
                # Bulleted list: "- ...", "* ..."
                bulleted = re.match(r"^[-*]\s+(.*)$", line)
                if bulleted:
                    normalized = bulleted.group(1).strip()
                else:
                    # Prefix form: "Step 1: ..."
                    step_prefix = re.match(r"^step\s*\d+\s*[:\-]\s*(.*)$", line, flags=re.IGNORECASE)
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
        """Build a Mermaid flowchart markdown block for plan preview."""
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
        lines.append("    done([Execute Plan])")
        lines.append(f"    s{len(steps)} --> done")
        lines.append("```")
        return "\n".join(lines)

    async def _deepagents_plan_preview(self, model, user_prompt: str) -> bool:
        """Show a one-shot plan and ask for terminal approval (deepagents path)."""
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            response = await model.ainvoke(
                [
                    SystemMessage(content="Create a concise execution plan before running tools."),
                    HumanMessage(content=user_prompt),
                ]
            )
            from agent.deepagents_runtime import _text_from_content

            proposed_plan = _text_from_content(getattr(response, "content", "")).strip()
        except Exception:  # noqa: BLE001
            logger.debug("deepagents plan preview failed", exc_info=True)
            return True

        if proposed_plan:
            self.session.console.print("\n  [bold cyan]Proposed Plan[/bold cyan]")
            self.session.console.print(f"  {proposed_plan}\n")
            cfg = getattr(self.session, "config", None)
            mermaid_enabled = bool(cfg.get("ui.mermaid.enabled", True)) if cfg else True
            if mermaid_enabled:
                diagram_markdown = self._plan_preview_mermaid_markdown(proposed_plan)
                if diagram_markdown:
                    try:
                        from ui.markdown import print_markdown_with_mermaid

                        self.session.console.print("  [bold cyan]Plan Diagram[/bold cyan]")
                        print_markdown_with_mermaid(
                            self.session.console,
                            diagram_markdown,
                            config=cfg,
                        )
                        self.session.console.print()
                    except Exception:  # noqa: BLE001
                        logger.debug("plan-preview mermaid rendering failed", exc_info=True)
        try:
            answer = input("  Execute this plan? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"
        return answer in {"", "y", "yes"}
