"""shell — part 2 of split module. See tools/shell.py."""
from tools.shell_base import Path, os, registry, shlex, subprocess
from tools.shell_part1 import _expand_env_refs, _is_blocked, _split_cd_prefix

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
        "'cd ... &&'. Environment variables like $FASTFOLD_API_KEY are expanded. "
        "Dangerous commands and shell operators (multi-command chaining, "
        "redirection) are blocked for safety. Prefer printenv NAME to check whether "
        "a credential is set (do not print secret values into the chat)."
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
    else:
        # Prefer the chat session workspace (UI file tree) when set by the agent server.
        session_ws = str(os.environ.get("SANDWALK_SESSION_WORKSPACE") or "").strip()
        if session_ws:
            candidate = Path(session_ws).expanduser()
            if candidate.is_dir():
                cwd = candidate

    # Cap timeout
    timeout = min(max(timeout, 1), 300)

    # Use shell=True for pipe commands, shell=False otherwise.
    # Without a shell, `$VAR` is not expanded — expand from os.environ so
    # checks like `echo $FASTFOLD_API_KEY` / skill scripts see real values.
    use_shell = "|" in command
    if use_shell:
        run_args = command
    else:
        try:
            run_args = [
                _expand_env_refs(token)
                for token in shlex.split(command, posix=True)
            ]
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
