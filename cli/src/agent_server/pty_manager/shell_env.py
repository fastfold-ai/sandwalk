"""Shell discovery + prompt-color startup files for spawned PTYs."""

from __future__ import annotations

import fcntl
import os
import struct
import termios
from pathlib import Path

# Match terminal tab accent (Tailwind emerald-500 / #10B981); gray cwd basename.
ZSH_PROMPT = "%B%F{#10B981}%n@%m%f%b %F{245}%1~%f %# "
BASH_PS1 = (
    r"\[\e[1;38;2;16;185;129m\]\u@\h\[\e[0m\] "
    r"\[\e[38;5;245m\]\W\[\e[0m\] \$ "
)


def preferred_shell() -> str:
    shell = os.environ.get("SHELL") or "/bin/zsh"
    if Path(shell).exists():
        return shell
    for candidate in ("/bin/zsh", "/bin/bash", "/bin/sh"):
        if Path(candidate).exists():
            return candidate
    return "/bin/sh"


def terminal_dot_dir() -> Path:
    """Shell startup dir that applies FastFold prompt colors after the user rc."""
    from agent.config import CONFIG_DIR

    zdot = CONFIG_DIR / "terminal-dot"
    zdot.mkdir(parents=True, exist_ok=True)
    zshrc = zdot / ".zshrc"
    zshrc.write_text(
        "# Managed by FastFold agent terminal — do not edit.\n"
        '[[ -r "${HOME}/.zshrc" ]] && source "${HOME}/.zshrc"\n'
        "_fastfold_set_prompt() {\n"
        f"  PROMPT='{ZSH_PROMPT}'\n"
        "  RPROMPT=''\n"
        "}\n"
        "_fastfold_set_prompt\n"
        "if typeset -f add-zsh-hook >/dev/null 2>&1; then\n"
        "  autoload -Uz add-zsh-hook\n"
        "  add-zsh-hook precmd _fastfold_set_prompt\n"
        "elif [[ -n ${precmd_functions+x} ]]; then\n"
        "  precmd_functions+=(_fastfold_set_prompt)\n"
        "fi\n"
    )
    bashrc = zdot / ".bashrc"
    bashrc.write_text(
        "# Managed by FastFold agent terminal — do not edit.\n"
        '[[ -r "${HOME}/.bashrc" ]] && source "${HOME}/.bashrc"\n'
        f"PS1='{BASH_PS1}'\n"
    )
    return zdot


def set_winsize(fd: int, rows: int, cols: int) -> None:
    packed = struct.pack("HHHH", max(1, rows), max(1, cols), 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, packed)
