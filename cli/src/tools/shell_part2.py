"""shell — part 2 of split module. See tools/shell.py."""
from tools.shell_base import Path, os, registry, shlex, subprocess
from tools.shell_part1 import (
    _expand_env_refs,
    _is_blocked,
    _needs_shell,
    _split_cd_prefix,
)

@registry.register(
    name="shell.run",
    description=(
        "Run a shell command on the host. Prefer working_dir (or a leading "
        "'cd <dir> && …') for skill scripts. Inside "
        "$SANDWALK_SESSION_WORKSPACE the agent may freely redirect, chain "
        "with &&/||/;, and rm/chmod workspace paths. Backticks, $(), and "
        "system-level commands stay blocked."
    ),
    category="shell",
    parameters={
        "command": "Shell command to execute",
        "working_dir": "Directory to run the command in (optional; absolute path preferred)",
        "timeout": "Timeout in seconds (default 30, max 300)",
    },
    usage_guide=(
        "Use for host CLI / skill scripts (e.g. python3 …/create_job.py). "
        "With SANDWALK_SESSION_WORKSPACE set (normal chat): free to "
        "> / >> / < under that folder, chain with && / || / ;, "
        "rm/chmod/rmdir workspace paths, and python3 -c. "
        "Prefer skill --download-dir for FastFold artifacts. "
        "Still blocked: backticks, $(), sudo, redirects/rm outside the "
        "session workspace, bash -c. Prefer printenv NAME to check "
        "credentials (do not paste secret values into the chat)."
    ),
)
def shell_run(command: str, working_dir: str = None, timeout: int = 30, **kwargs) -> dict:
    """Run a shell command and return stdout/stderr."""
    # Refresh Integrations → process env so skill scripts see current keys
    # (and SANDWALK_* path helpers) even if config changed after serve start.
    try:
        from agent.config import sync_process_env_from_config

        sync_process_env_from_config()
    except Exception:
        pass

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

    # shell=True for pipes / && / || / null redirects. Otherwise expand $VAR
    # ourselves so skill/env checks work without a shell.
    use_shell = _needs_shell(command)
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
