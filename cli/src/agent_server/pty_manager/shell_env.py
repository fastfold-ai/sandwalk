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
    # FAS-107 · Fase 1b · shell integration OSC 133 (Semantic Prompt).
    # `precmd` emite `\e]133;D;<exit_code>\a` (fin del comando anterior)
    # seguido de `\e]133;A\a` (inicio de prompt). `preexec` emite
    # `\e]133;C\a` (comando por ejecutar). El parser del PTY usa estos
    # marcadores para saber cuándo terminó cada comando y con qué exit
    # code — habilita notificaciones "comando terminó / falló".
    zshrc.write_text(
        "# Managed by FastFold agent terminal — do not edit.\n"
        '[[ -r "${HOME}/.zshrc" ]] && source "${HOME}/.zshrc"\n'
        "_fastfold_set_prompt() {\n"
        f"  PROMPT='{ZSH_PROMPT}'\n"
        "  RPROMPT=''\n"
        "}\n"
        "_fastfold_set_prompt\n"
        "_fastfold_osc133_precmd() {\n"
        "  local rc=$?\n"
        "  printf '\\e]133;D;%s\\a' \"$rc\"\n"
        "  printf '\\e]133;A\\a'\n"
        "}\n"
        "_fastfold_osc133_preexec() {\n"
        "  printf '\\e]133;C\\a'\n"
        "}\n"
        "# Autoload first, unconditionally: `typeset -f add-zsh-hook` does not\n"
        "# see the function until it has run once, so the check must come\n"
        "# AFTER the autoload (otherwise the hook never registered).\n"
        "autoload -Uz add-zsh-hook 2>/dev/null\n"
        "if typeset -f add-zsh-hook >/dev/null 2>&1; then\n"
        "  add-zsh-hook precmd _fastfold_set_prompt\n"
        "  add-zsh-hook precmd _fastfold_osc133_precmd\n"
        "  add-zsh-hook preexec _fastfold_osc133_preexec\n"
        "else\n"
        "  typeset -ga precmd_functions preexec_functions\n"
        "  precmd_functions+=(_fastfold_set_prompt _fastfold_osc133_precmd)\n"
        "  preexec_functions+=(_fastfold_osc133_preexec)\n"
        "fi\n"
    )
    bashrc = zdot / ".bashrc"
    # Bash: PROMPT_COMMAND para precmd (D + A) y trap DEBUG para preexec (C).
    # El trap DEBUG se dispara antes de cada comando; se evita re-emitir
    # OSC C mientras se está renderizando el prompt usando `BASH_COMMAND`
    # como guard.
    bashrc.write_text(
        "# Managed by FastFold agent terminal — do not edit.\n"
        '[[ -r "${HOME}/.bashrc" ]] && source "${HOME}/.bashrc"\n'
        f"PS1='{BASH_PS1}'\n"
        "_fastfold_osc133_precmd() {\n"
        "  local rc=$?\n"
        "  printf '\\e]133;D;%s\\a' \"$rc\"\n"
        "  printf '\\e]133;A\\a'\n"
        "  _fastfold_osc133_in_prompt=1\n"
        "}\n"
        "_fastfold_osc133_preexec() {\n"
        "  if [[ -n \"$_fastfold_osc133_in_prompt\" ]]; then\n"
        "    unset _fastfold_osc133_in_prompt\n"
        "    printf '\\e]133;C\\a'\n"
        "  fi\n"
        "}\n"
        'PROMPT_COMMAND="_fastfold_osc133_precmd; ${PROMPT_COMMAND}"\n'
        "trap '_fastfold_osc133_preexec' DEBUG\n"
    )
    return zdot


def set_winsize(fd: int, rows: int, cols: int) -> None:
    packed = struct.pack("HHHH", max(1, rows), max(1, cols), 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, packed)
