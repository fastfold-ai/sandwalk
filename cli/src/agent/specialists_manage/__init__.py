"""Shared specialists helpers for `sandwalk specialists` and interactive `/specialist`.

Split into `state.py` (active-specialist config + context application),
`display.py` (list/show/active read-only commands), `crud.py`
(create/update/delete/use/clear), and `dispatch.py`
(handle_specialist_argv) to stay under the file-length cap; re-exported
here so `from agent.specialists_manage import ...` keeps working
unchanged.
"""

from .crud import cmd_clear, cmd_create, cmd_delete, cmd_update, cmd_use
from .dispatch import handle_specialist_argv
from .display import cmd_active, cmd_list, cmd_show
from .state import (
    CLI_SPECIALIST_CONFIG_KEY,
    apply_specialist_to_context,
    get_active_specialist,
    get_active_specialist_ref,
    resolve_specialist_ref,
    set_active_specialist_ref,
)

__all__ = [
    "CLI_SPECIALIST_CONFIG_KEY",
    "apply_specialist_to_context",
    "cmd_active",
    "cmd_clear",
    "cmd_create",
    "cmd_delete",
    "cmd_list",
    "cmd_show",
    "cmd_update",
    "cmd_use",
    "get_active_specialist",
    "get_active_specialist_ref",
    "handle_specialist_argv",
    "resolve_specialist_ref",
    "set_active_specialist_ref",
]
