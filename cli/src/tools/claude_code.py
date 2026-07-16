"""Claude tool: delegate a coding task to the Claude Code CLI."""

import subprocess
from pathlib import Path

from tools import registry


@registry.register(
    name="claude.code",
    description="Delegate a coding task to Claude Code (file editing, refactoring, debugging, test writing)",
    category="claude",
    parameters={
        "task": "Description of the coding task (be specific: which files, what changes, what to test)",
        "allowed_tools": "Claude Code tools to allow (default: 'Read,Edit,Write,Bash,Glob,Grep')",
        "max_budget": "Max spend in USD (default: 1.0)",
    },
    usage_guide=(
        "Use for complex coding tasks that need iterative edit-test-fix cycles: "
        "refactoring code, writing tests, debugging scripts, modifying config files, "
        "building analysis pipelines. Claude Code handles the full read→edit→test→fix loop. "
        "Do NOT use for simple single-shot file reads or edits — use files.* tools instead. "
        "Do NOT use for drug discovery research — use ct's specialized tools."
    ),
)
def code(
    task: str,
    allowed_tools: str = "Read,Edit,Write,Bash,Glob,Grep",
    max_budget: float = 1.0,
    _session=None,
    _prior_results=None,
    **kwargs,
) -> dict:
    """Delegate a coding task to Claude Code CLI.

    Spawns `claude -p` in non-interactive mode with permission bypass and
    a budget cap. Returns Claude Code's output as the tool result.
    """
    import os
    import shutil

    enabled = str(os.environ.get("CT_ENABLE_CLAUDE_CODE", "")).strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if _session is not None and hasattr(_session, "config"):
        enabled = bool(_session.config.get("agent.enable_claude_code_tool", False))

    if not enabled:
        return {
            "summary": (
                "claude.code is disabled by policy (opt-in). "
                "Enable with: sandwalk config set agent.enable_claude_code_tool true"
            ),
            "error": "disabled_by_policy",
        }

    claude_path = shutil.which("claude")
    if not claude_path:
        return {
            "summary": "Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code",
            "error": "claude_not_found",
        }

    # Build context from prior results so Claude Code knows what ct has already done
    context_parts = []
    if _prior_results:
        for step_id, result in _prior_results.items():
            if isinstance(result, dict):
                summary = result.get("summary", "")[:300]
            else:
                summary = str(result)[:300]
            if summary:
                context_parts.append(f"- Step {step_id}: {summary}")

    full_prompt = task
    if context_parts:
        full_prompt = (
            "Context from prior research steps:\n" + "\n".join(context_parts) + f"\n\nTask: {task}"
        )

    cmd = [
        claude_path,
        "-p",
        full_prompt,
        "--output-format",
        "text",
        "--permission-mode",
        "bypassPermissions",
        "--allowed-tools",
        allowed_tools,
        "--max-budget-usd",
        str(max_budget),
        "--no-session-persistence",
    ]

    try:
        if _session:
            from ui.status import ThinkingStatus

            with ThinkingStatus(_session.console, "coding"):
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=str(Path.cwd()),
                    timeout=300,
                )
        else:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(Path.cwd()),
                timeout=300,
            )
    except subprocess.TimeoutExpired:
        return {
            "summary": "Claude Code timed out after 5 minutes.",
            "error": "timeout",
        }
    except Exception as e:
        return {
            "summary": f"Failed to run Claude Code: {e}",
            "error": str(e),
        }

    output = result.stdout.strip()
    stderr = result.stderr.strip()

    # Truncate very long output
    if len(output) > 15000:
        output = output[:15000] + "\n... [truncated]"

    if result.returncode == 0 and output:
        summary = output[:2000]
        if len(output) > 2000:
            summary += "..."
        return {
            "summary": summary,
            "full_output": output,
            "exit_code": result.returncode,
        }
    elif output:
        return {
            "summary": f"Claude Code finished (exit {result.returncode}): {output[:1000]}",
            "full_output": output,
            "stderr": stderr[:2000] if stderr else "",
            "exit_code": result.returncode,
        }
    else:
        return {
            "summary": f"Claude Code produced no output (exit {result.returncode}). Stderr: {stderr[:500]}",
            "error": "no_output",
            "stderr": stderr[:2000] if stderr else "",
            "exit_code": result.returncode,
        }
