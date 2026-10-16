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


# Coding-agent CLIs the shell hooks announce via OSC 777. The PTY parser turns
# `\e]777;notify;Sandwalk;agent;<kind>;started\a` into an `agent.changed`
# event with no process lookup. Keep in sync with AGENT_BINARIES.
AGENT_HOOK_BINARIES = ("claude", "codex", "opencode", "fx", "hermes")

# POSIX sh fragment: `$1` is the command line about to run; prints the agent
# kind (basename of the first word) when it is one of ours, else nothing.
# Handles `claude …`, `/usr/local/bin/codex …`, `FOO=1 fx …`, `npx opencode`.
_AGENT_KIND_SH = r"""_sandwalk_agent_kind() {
  # zsh does not word-split "$1" by default; `set --` splits in both shells.
  set -- $(printf '%s' "$1")
  local word
  for word in "$@"; do
    case "$word" in
      *=*) continue ;;
      sudo|env|exec|command|nice|time|npx|bunx|pnpx) continue ;;
    esac
    word="${word##*/}"
    case "$word" in
      claude|codex|opencode|fx|hermes) printf '%s' "$word"; return 0 ;;
    esac
    return 1
  done
  return 1
}
"""


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
        "_fastfold_set_prompt\n" + _AGENT_KIND_SH + "_fastfold_osc133_precmd() {\n"
        "  local rc=$?\n"
        "  printf '\\e]133;D;%s\\a' \"$rc\"\n"
        "  printf '\\e]133;A\\a'\n"
        '  if [[ -n "$_sandwalk_agent_running" ]]; then\n'
        "    printf '\\e]777;notify;Sandwalk;agent;%s;exited\\a' \"$_sandwalk_agent_running\"\n"
        "    unset _sandwalk_agent_running\n"
        "  fi\n"
        "}\n"
        "_fastfold_osc133_preexec() {\n"
        "  printf '\\e]133;C\\a'\n"
        "  local kind\n"
        '  if kind=$(_sandwalk_agent_kind "$1"); then\n'
        '    _sandwalk_agent_running="$kind"\n'
        "    printf '\\e]777;notify;Sandwalk;agent;%s;started\\a' \"$kind\"\n"
        "  fi\n"
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
        f"PS1='{BASH_PS1}'\n" + _AGENT_KIND_SH + "_fastfold_osc133_precmd() {\n"
        "  local rc=$?\n"
        "  printf '\\e]133;D;%s\\a' \"$rc\"\n"
        "  printf '\\e]133;A\\a'\n"
        '  if [[ -n "$_sandwalk_agent_running" ]]; then\n'
        "    printf '\\e]777;notify;Sandwalk;agent;%s;exited\\a' \"$_sandwalk_agent_running\"\n"
        "    unset _sandwalk_agent_running\n"
        "  fi\n"
        "  _fastfold_osc133_in_prompt=1\n"
        "}\n"
        "_fastfold_osc133_preexec() {\n"
        '  if [[ -n "$_fastfold_osc133_in_prompt" ]]; then\n'
        "    unset _fastfold_osc133_in_prompt\n"
        "    printf '\\e]133;C\\a'\n"
        "    local kind\n"
        '    if kind=$(_sandwalk_agent_kind "$BASH_COMMAND"); then\n'
        '      _sandwalk_agent_running="$kind"\n'
        "      printf '\\e]777;notify;Sandwalk;agent;%s;started\\a' \"$kind\"\n"
        "    fi\n"
        "  fi\n"
        "}\n"
        'PROMPT_COMMAND="_fastfold_osc133_precmd; ${PROMPT_COMMAND}"\n'
        "trap '_fastfold_osc133_preexec' DEBUG\n"
    )
    return zdot


def set_winsize(fd: int, rows: int, cols: int) -> None:
    packed = struct.pack("HHHH", max(1, rows), max(1, cols), 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, packed)
