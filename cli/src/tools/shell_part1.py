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

# Always blocked — system / privilege boundaries.
_BLOCKED_BINARIES = {
    "sudo", "su", "mkfs", "dd", "shutdown", "reboot", "poweroff",
    "halt", "init", "chown", "chgrp", "useradd", "userdel", "groupadd",
    "groupdel", "passwd", "mount", "umount",
}

# Allowed against session-workspace paths only (when SANDWALK_SESSION_WORKSPACE is set).
_WORKSPACE_FILE_BINARIES = {"rm", "rmdir", "chmod"}

# Command substitution / backticks stay blocked everywhere.
_HARD_UNSAFE_SYNTAX = re.compile(r"[`]|[$][(]")

# Null / fd redirects agents use constantly — always allow these.
_SAFE_REDIRECT = re.compile(
    r"(?:(?:\d*)>|&>)\s*/dev/null|(?:2>&1|1>&2)"
)

# File redirects into/from the session workspace (downloads, saves, inputs).
_WORKSPACE_FILE_REDIRECT = re.compile(
    r"(?:(?P<fd>\d*)(?P<op>>{1,2}|<))\s*"
    r"(?P<target>\"[^\"]+\"|'[^']+'|[^\s&|;<>]+)"
)

# ``&&`` / ``||`` / ``;`` chains when a session workspace is active.
_CHAIN_SPLIT_WORKSPACE = re.compile(r"\s*(?:&&|\|\||;)\s*")
_CHAIN_SPLIT_STRICT = re.compile(r"\s*(?:&&|\|\|)\s*")
_MAX_CHAIN_SEGMENTS_STRICT = 3
_MAX_CHAIN_SEGMENTS_WORKSPACE = 12

# Safe commands that may appear on the right side of a pipe
_SAFE_PIPE_RHS = {
    "head", "tail", "grep", "wc", "sort", "uniq", "cut", "awk", "sed",
    "cat", "less", "more", "tr", "tee", "xargs",
}
_SAFE_PIPE_RHS_WORKSPACE = _SAFE_PIPE_RHS | {
    "python", "python3", "curl", "wget", "jq", "base64", "gzip", "gunzip",
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


def _session_workspace_root() -> Path | None:
    raw = str(os.environ.get("SANDWALK_SESSION_WORKSPACE") or "").strip()
    if not raw:
        return None
    try:
        root = Path(raw).expanduser().resolve()
    except OSError:
        return None
    return root if root.is_dir() else None


def _path_under_workspace(raw: str, *, workspace: Path) -> Path | None:
    """Resolve ``raw`` and require it to live under the session workspace.

    Includes the intentional ``workspace/project`` symlink mount (external
    project folder), so agents can redirect/rm there.
    """
    text = (raw or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1]
    text = _expand_env_refs(text).strip()
    if not text or text.startswith("(") or text in {"&1", "&2"}:
        return None
    from agent_server.project_folder import path_under_workspace_or_project

    path = Path(text).expanduser()
    if not path.is_absolute():
        path = workspace / path
    return path_under_workspace_or_project(path, workspace)


def _strip_workspace_file_redirects(command: str) -> tuple[str | None, str]:
    """Strip workspace-scoped ``>`` / ``>>`` / ``<`` redirects for syntax checks."""
    workspace = _session_workspace_root()
    error: str | None = None

    def _replace(match: re.Match[str]) -> str:
        nonlocal error
        if error:
            return " "
        if workspace is None:
            error = (
                "File redirection requires SANDWALK_SESSION_WORKSPACE "
                "(or use >/dev/null)."
            )
            return " "
        if _path_under_workspace(match.group("target"), workspace=workspace) is None:
            error = (
                "File redirection is only allowed under the session workspace "
                f"({workspace})."
            )
            return " "
        return " "

    stripped = _WORKSPACE_FILE_REDIRECT.sub(_replace, command or "")
    return error, stripped


def _needs_shell(command: str) -> bool:
    """True when the command needs ``shell=True`` to run as written."""
    cmd = command or ""
    if "|" in cmd or "&&" in cmd or "||" in cmd or ";" in cmd:
        return True
    if _SAFE_REDIRECT.search(cmd):
        return True
    if _WORKSPACE_FILE_REDIRECT.search(cmd):
        return True
    return False


def _strip_safe_redirects(command: str) -> str:
    return _SAFE_REDIRECT.sub(" ", command or "")


def _check_pipe_segments(cmd: str, *, workspace_mode: bool) -> str | None:
    if "|" not in cmd:
        return None
    parts = re.split(r"(?<!\|)\|(?!\|)", cmd)
    limit = 6 if workspace_mode else 3
    if len(parts) > limit:
        return "Too many pipes; simplify the command"
    allowed = _SAFE_PIPE_RHS_WORKSPACE if workspace_mode else _SAFE_PIPE_RHS
    for part in parts[1:]:
        part_stripped = part.strip()
        if not part_stripped:
            return "Empty pipe segment"
        try:
            first_token = shlex.split(part_stripped, posix=True)[0]
            rhs_name = Path(first_token).name.lower()
        except (ValueError, IndexError):
            return f"Invalid pipe segment: {part_stripped[:50]}"
        if rhs_name not in allowed:
            return (
                f"Pipe to '{rhs_name}' not allowed; "
                "only safe utilities permitted after pipe"
            )
    return None


def _check_command_tokens(cmd: str, *, workspace: Path | None) -> str | None:
    try:
        tokens = shlex.split(cmd, posix=True)
    except ValueError as e:
        return f"Invalid command syntax: {e}"
    if not tokens:
        return "Empty command"
    command_name = Path(tokens[0]).name.lower()

    if command_name in _WORKSPACE_FILE_BINARIES:
        if workspace is None:
            return f"Blocked command: {command_name}"
        path_args = [tok for tok in tokens[1:] if not tok.startswith("-")]
        if not path_args:
            return f"{command_name} requires a path under the session workspace"
        for arg in path_args:
            if _path_under_workspace(arg, workspace=workspace) is None:
                return (
                    f"{command_name} is only allowed on paths under the "
                    f"session workspace ({workspace})"
                )
    elif command_name in _BLOCKED_BINARIES:
        return f"Blocked command: {command_name}"

    if command_name in {"python", "python3"}:
        # Inline -c is OK inside a session workspace (agents save/download there).
        if workspace is None and any(tok in {"-c", "-e"} for tok in tokens[1:]):
            return f"Blocked inline script execution for {command_name}"
    elif command_name in {"bash", "sh", "zsh", "node", "perl", "ruby"}:
        if any(tok in {"-c", "-e"} for tok in tokens[1:]):
            return f"Blocked inline script execution for {command_name}"
    return None


def _is_blocked(command: str) -> str | None:
    """Return a reason string if the command is blocked, else None."""
    cmd = (command or "").strip()
    if not cmd:
        return "Empty command"

    workspace = _session_workspace_root()
    workspace_mode = workspace is not None

    # Strip null/fd redirects, then workspace-scoped file redirects.
    syntax_probe = _strip_safe_redirects(cmd)
    redirect_err, syntax_probe = _strip_workspace_file_redirects(syntax_probe)
    if redirect_err:
        return redirect_err

    # Without a session workspace, keep ``;`` blocked (strict mode).
    if not workspace_mode and ";" in syntax_probe:
        return (
            "Shell metacharacters `;`, backticks, or $() are not allowed. "
            "Use && / || for short chains, or run separate shell.run calls."
        )
    if _HARD_UNSAFE_SYNTAX.search(syntax_probe):
        return (
            "Backticks and $() are not allowed. "
            "Use && / || / ; chains, or run separate shell.run calls."
        )
    # Leftover redirects outside the allowlists.
    if re.search(r"[<>]", syntax_probe):
        return (
            "File redirection is only allowed under the session workspace "
            "(SANDWALK_SESSION_WORKSPACE) or >/dev/null / 2>&1."
        )

    splitter = _CHAIN_SPLIT_WORKSPACE if workspace_mode else _CHAIN_SPLIT_STRICT
    max_segments = (
        _MAX_CHAIN_SEGMENTS_WORKSPACE if workspace_mode else _MAX_CHAIN_SEGMENTS_STRICT
    )
    segments = [part.strip() for part in splitter.split(cmd) if part.strip()]
    if len(segments) > max_segments:
        return (
            f"Too many chain segments (max {max_segments}); "
            "split into separate shell.run calls"
        )

    for segment in segments:
        pipe_err = _check_pipe_segments(segment, workspace_mode=workspace_mode)
        if pipe_err:
            return pipe_err
        left = re.split(r"(?<!\|)\|(?!\|)", segment, maxsplit=1)[0]
        left = _strip_safe_redirects(left)
        _, left = _strip_workspace_file_redirects(left)
        left = left.strip()
        token_err = _check_command_tokens(left, workspace=workspace)
        if token_err:
            return token_err

    cmd_lower = cmd.lower()
    for pattern in _BLOCKED_PATTERNS:
        if pattern.lower() in cmd_lower:
            return f"Blocked command pattern: {pattern}"

    return None
