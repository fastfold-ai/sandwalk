"""shell — part 1 of split module. See tools/shell.py."""
from tools.shell_base import Path, _ENV_VAR_PATTERN, os, re, shlex

def _expand_env_refs(token: str) -> str:
    """Replace ``$VAR`` / ``${VAR}`` with values from ``os.environ`` (empty if unset)."""

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        return os.environ.get(name, "")

    return _ENV_VAR_PATTERN.sub(_replace, token)
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
