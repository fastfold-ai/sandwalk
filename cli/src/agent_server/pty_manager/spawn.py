"""Fork + exec an interactive shell attached to a fresh PTY."""

from __future__ import annotations

import fcntl
import os
import termios
from pathlib import Path

from agent_server.pty_manager.shell_env import (
    BASH_PS1,
    preferred_shell,
    set_winsize,
    terminal_dot_dir,
)


def spawn_pty(*, cwd: str, cols: int, rows: int) -> tuple[int, int, Path]:
    """Create a PTY pair and fork a shell into it.

    Returns (pid, master_fd, resolved_workspace_path).
    """
    workspace = Path(cwd).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    master_fd, slave_fd = os.openpty()
    set_winsize(master_fd, rows, cols)

    pid = os.fork()
    if pid == 0:
        _exec_shell_child(master_fd, slave_fd, workspace)

    os.close(slave_fd)
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    return pid, master_fd, workspace


def _exec_shell_child(master_fd: int, slave_fd: int, workspace: Path) -> None:
    try:
        os.close(master_fd)
        os.setsid()
        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        if slave_fd > 2:
            os.close(slave_fd)
        os.chdir(workspace)
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env["CLICOLOR"] = "1"
        env["CLICOLOR_FORCE"] = "1"
        env["FORCE_COLOR"] = "1"
        # BSD ls colors: dirs bold blue, executables green, symlinks magenta
        env.setdefault("LSCOLORS", "ExGxFxdxCxegedabagacad")
        env["FASTFOLD_TERMINAL"] = "1"
        shell = preferred_shell()
        shell_name = Path(shell).name
        dot = terminal_dot_dir()
        if shell_name == "zsh":
            env["ZDOTDIR"] = str(dot)
            argv = [shell, "-i"]
        elif shell_name == "bash":
            argv = [shell, "--rcfile", str(dot / ".bashrc"), "-i"]
        else:
            env["PS1"] = BASH_PS1
            argv = [shell, "-i"]
        os.execvpe(shell, argv, env)
    except Exception:
        os._exit(1)
