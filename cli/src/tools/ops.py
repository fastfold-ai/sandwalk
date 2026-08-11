"""
Research-ops productivity tools: notebook entries, todos, and workflow templates.

These tools provide lightweight project memory in ~/.sandwalk/ops (or config override)
without depending on external services.

Split across tools/ops_common.py (shared storage helpers), tools/ops_notebook.py,
tools/ops_todo.py, and tools/ops_workflow.py; re-exported here for backward
compatibility. This module is the canonical patch target for tests
(e.g. ``from tools.ops import notebook_add``).
"""

from tools.ops_common import (
    _notebook_path,
    _now_iso,
    _ops_root,
    _parse_int,
    _todos_path,
    _workflow_dir,
)
from tools.ops_notebook import (
    _load_notebook_entries,
    _normalize_tags,
    _save_notebook_entries,
    notebook_add,
    notebook_delete,
    notebook_get,
    notebook_list,
    notebook_search,
    notebook_update,
)
from tools.ops_todo import (
    _load_todos,
    _priority_rank,
    _save_todos,
    todo_add,
    todo_delete,
    todo_get,
    todo_list,
    todo_update,
)
from tools.ops_workflow import (
    _find_workflow_path,
    _list_workflow_files,
    _load_workflow_payload,
    _normalize_workflow_steps,
    _slugify_name,
    workflow_delete,
    workflow_get,
    workflow_list,
    workflow_run,
    workflow_save,
    workflow_update,
)

__all__ = [
    "_ops_root",
    "_notebook_path",
    "_todos_path",
    "_workflow_dir",
    "_now_iso",
    "_parse_int",
    "_normalize_tags",
    "_load_notebook_entries",
    "_save_notebook_entries",
    "notebook_add",
    "notebook_search",
    "notebook_get",
    "notebook_list",
    "notebook_update",
    "notebook_delete",
    "_load_todos",
    "_save_todos",
    "_priority_rank",
    "todo_add",
    "todo_list",
    "todo_get",
    "todo_update",
    "todo_delete",
    "_slugify_name",
    "_list_workflow_files",
    "_load_workflow_payload",
    "_find_workflow_path",
    "_normalize_workflow_steps",
    "workflow_save",
    "workflow_list",
    "workflow_get",
    "workflow_update",
    "workflow_delete",
    "workflow_run",
]
