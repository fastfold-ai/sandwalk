"""
Shell execution tool for ct.

Run shell commands from within ct research workflows with safety restrictions.
"""

import re
import shlex
import subprocess
from pathlib import Path

from tools import registry

# Commands/patterns that are never allowed
_BLOCKED_PATTERNS = (
    "sudo ",
    "rm -rf /",
    "rm -rf /*",
    "chmod 777",
    ":(){ :|:& };:",  # fork bomb
    "mkfs.",
    "dd if=",
    "> /dev/sd",
    "shutdown",
    "reboot",
    "init 0",
    "init 6",
)

_BLOCKED_BINARIES = {
    "sudo", "su", "rm", "rmdir", "mkfs", "dd", "shutdown", "reboot", "poweroff",
    "halt", "init", "chown", "chgrp", "chmod", "useradd", "userdel", "groupadd",
    "groupdel", "passwd", "mount", "umount",
}

_UNSAFE_SHELL_SYNTAX = re.compile(r"(\|\|)|(&&)|[;<>`]|[$][(]")

# Safe commands that may appear on the right side of a pipe
_SAFE_PIPE_RHS = {
    "head", "tail", "grep", "wc", "sort", "uniq", "cut", "awk", "sed",
    "cat", "less", "more", "tr", "tee", "xargs",
}

# A leading ``cd <dir> &&`` prefix is a near-universal habit for running a
# script from a specific directory. Rather than blocking it (which causes the
# agent to retry repeatedly), we extract the directory and run the remaining
# single command there. The directory is a plain path (no operators/expansion).
_CD_PREFIX = re.compile(r"""^\s*cd\s+("[^"]+"|'[^']+'|[^\s&;|<>`$]+)\s*&&\s*(.+)$""", re.DOTALL)


def _split_cd_prefix(command: str) -> tuple[str | None, str]:
    """Split a leading ``cd <dir> &&`` off a command.

    Returns ``(dir_or_None, remaining_command)``. If there is no such prefix,
    ``dir`` is ``None`` and the command is returned unchanged.
    """
    match = _CD_PREFIX.match(command or "")
    if not match:
        return None, command
    raw_dir = match.group(1).strip()
    if (raw_dir[:1], raw_dir[-1:]) in (('"', '"'), ("'", "'")):
        raw_dir = raw_dir[1:-1]
    return raw_dir, match.group(2).strip()


def _is_blocked(command: str) -> str | None:
    """Return a reason string if the command is blocked, else None."""
    cmd = (command or "").strip()
    if not cmd:
        return "Empty command"

    # Check for unsafe syntax (excluding single pipe |)
    if _UNSAFE_SHELL_SYNTAX.search(cmd):
        return "Shell operators/redirection are not allowed; run a single command only"

    # Allow single-pipe commands where the RHS is a safe utility
    if "|" in cmd:
        parts = cmd.split("|")
        if len(parts) > 3:
            return "Too many pipes; simplify the command"
        for part in parts[1:]:  # Check RHS commands
            part_stripped = part.strip()
            if not part_stripped:
                return "Empty pipe segment"
            try:
                first_token = shlex.split(part_stripped, posix=True)[0]
                rhs_name = Path(first_token).name.lower()
            except (ValueError, IndexError):
                return f"Invalid pipe segment: {part_stripped[:50]}"
            if rhs_name not in _SAFE_PIPE_RHS:
                return f"Pipe to '{rhs_name}' not allowed; only safe utilities permitted after pipe"

    cmd_lower = cmd.lower()
    for pattern in _BLOCKED_PATTERNS:
        if pattern.lower() in cmd_lower:
            return f"Blocked command pattern: {pattern}"

    try:
        tokens = shlex.split(cmd, posix=True)
    except ValueError as e:
        return f"Invalid command syntax: {e}"

    if not tokens:
        return "Empty command"

    command_name = Path(tokens[0]).name.lower()
    if command_name in _BLOCKED_BINARIES:
        return f"Blocked command: {command_name}"

    if command_name in {"python", "python3", "bash", "sh", "zsh", "node", "perl", "ruby"}:
        if any(tok in {"-c", "-e"} for tok in tokens[1:]):
            return f"Blocked inline script execution for {command_name}"

    return None


@registry.register(
    name="shell.run",
    description=(
        "Run a single shell command. To run in a specific directory, pass "
        "working_dir (preferred) or a leading 'cd <dir> &&' prefix — do not chain "
        "multiple commands with && or use redirection."
    ),
    category="shell",
    parameters={
        "command": "Shell command to execute (a single command)",
        "working_dir": "Directory to run the command in (optional; absolute path preferred)",
        "timeout": "Timeout in seconds (default 30, max 300)",
    },
    usage_guide=(
        "Use to run a single shell command: scripts, data processing, git, pip, etc. "
        "Set working_dir to run from a directory (e.g. a skill folder) instead of "
        "'cd ... &&'. Dangerous commands and shell operators (multi-command chaining, "
        "redirection) are blocked for safety."
    ),
)
def shell_run(command: str, working_dir: str = None, timeout: int = 30, **kwargs) -> dict:
    """Run a shell command and return stdout/stderr."""
    # Accommodate the common ``cd <dir> && <cmd>`` habit: extract the directory
    # and run the remaining single command there instead of blocking it.
    cd_dir, command = _split_cd_prefix(command)
    if cd_dir and not working_dir:
        working_dir = cd_dir

    # Safety check (on the remaining single command)
    blocked = _is_blocked(command)
    if blocked:
        return {"summary": f"Command blocked: {blocked}", "error": "blocked_command"}

    # Resolve and validate the working directory
    cwd = Path.cwd()
    if working_dir:
        candidate = Path(working_dir).expanduser()
        if not candidate.is_dir():
            return {
                "summary": f"Working directory not found: {working_dir}",
                "error": "invalid_working_dir",
                "exit_code": -1,
            }
        cwd = candidate

    # Cap timeout
    timeout = min(max(timeout, 1), 300)

    # Use shell=True for pipe commands, shell=False otherwise
    use_shell = "|" in command
    if use_shell:
        run_args = command
    else:
        try:
            run_args = shlex.split(command, posix=True)
        except ValueError as e:
            return {
                "summary": f"Invalid command syntax: {e}",
                "error": "invalid_command",
                "exit_code": -1,
            }

    try:
        result = subprocess.run(
            run_args,
            shell=use_shell,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "summary": f"Command timed out after {timeout}s: {command[:80]}",
            "error": "timeout",
            "exit_code": -1,
        }
    except Exception as e:
        return {
            "summary": f"Command failed: {e}",
            "error": str(e),
            "exit_code": -1,
        }

    stdout = result.stdout
    stderr = result.stderr

    # Truncate large output
    if len(stdout) > 10000:
        stdout = stdout[:10000] + f"\n... [truncated, total {len(result.stdout)} chars]"
    if len(stderr) > 5000:
        stderr = stderr[:5000] + f"\n... [truncated, total {len(result.stderr)} chars]"

    if result.returncode == 0:
        output_preview = stdout.strip()[:200] if stdout.strip() else "(no output)"
        summary = f"Command succeeded (exit 0): {output_preview}"
    else:
        err_preview = stderr.strip()[:200] if stderr.strip() else stdout.strip()[:200]
        summary = f"Command failed (exit {result.returncode}): {err_preview}"

    return {
        "summary": summary,
        "exit_code": result.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "command": command,
    }
