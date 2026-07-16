"""Rich rendering of a research plan for user approval."""

from rich.console import Console
from rich.panel import Panel


def render_plan_preview(plan, console=None):
    """Render a plan as a Rich Panel for user approval.

    Args:
        plan: A Plan object with .steps (each having id, tool, description,
              tool_args, depends_on).
        console: Optional Rich Console. Defaults to a new Console().

    Returns:
        The rendered Text (for testing) or prints to console.
    """
    from rich.text import Text

    from ui.traces import format_args

    if console is None:
        console = Console()

    lines = Text()
    lines.append("Research Plan\n\n", style="bold")

    for step in plan.steps:
        # Dependency indicator
        deps = getattr(step, "depends_on", []) or []
        dep_str = ""
        if deps:
            dep_str = f" (after step {', '.join(str(d) for d in deps)})"

        lines.append(f"  {step.id}. ", style="bold cyan")
        lines.append(step.tool or "", style="cyan")
        if dep_str:
            lines.append(dep_str, style="dim")
        lines.append("\n")

        # Description
        desc = getattr(step, "description", "") or ""
        if desc:
            lines.append(f"     {desc}\n", style="")

        # Key args
        args = getattr(step, "tool_args", {}) or {}
        args_str = format_args(args)
        if args_str:
            lines.append(f"     {args_str}\n", style="dim")

    console.print(Panel(lines, border_style="cyan", title="Plan Preview", width=80))
    return lines
