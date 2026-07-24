"""shell: split into tools/shell_base.py + tools/shell_part*.py."""
from tools.shell_part1 import (
    _BLOCKED_BINARIES,
    _BLOCKED_PATTERNS,
    _CD_PREFIX,
    _HARD_UNSAFE_SYNTAX,
    _SAFE_PIPE_RHS,
    _SAFE_REDIRECT,
    _expand_env_refs,
    _is_blocked,
    _needs_shell,
    _split_cd_prefix,
)
from tools.shell_part2 import (
    shell_run,
)

# Back-compat alias for older tests/imports.
_UNSAFE_SHELL_SYNTAX = _HARD_UNSAFE_SYNTAX
