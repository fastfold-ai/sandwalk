"""ops.todo_*: todo-tracking tools. Split from tools/ops.py."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from uuid import uuid4

from tools import registry
from tools.ops_common import _now_iso, _todos_path


def _load_todos(_session=None) -> tuple[list[dict], str | None]:
    """Load todo list, returning (todos, error)."""
    path = _todos_path(_session)
    if not path.exists():
        return [], None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [], f"Failed to read todo database: {exc}"

    if not isinstance(data, list):
        return [], "Todo database is corrupted (expected JSON list)."

    todos = [x for x in data if isinstance(x, dict)]
    return todos, None


def _save_todos(todos: list[dict], _session=None) -> tuple[Path, str | None]:
    """Persist todo list to disk."""
    path = _todos_path(_session)
    try:
        path.write_text(json.dumps(todos, indent=2), encoding="utf-8")
        return path, None
    except Exception as exc:
        return path, f"Failed to persist todo database: {exc}"


def _priority_rank(priority: str) -> int:
    mapping = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return mapping.get(priority, 2)


@registry.register(
    name="ops.todo_add",
    description="Create a tracked todo item for research follow-ups",
    category="ops",
    parameters={
        "task": "Todo description",
        "priority": "critical|high|medium|low (default medium)",
        "due_date": "Optional due date in YYYY-MM-DD",
        "owner": "Optional owner name/alias",
    },
    usage_guide=(
        "Use to capture follow-up actions from synthesis outputs (validation assays, "
        "data pulls, literature checks) so nothing is lost between sessions."
    ),
)
def todo_add(
    task: str,
    priority: str = "medium",
    due_date: str | None = None,
    owner: str | None = None,
    _session=None,
    **kwargs,
) -> dict:
    """Append a todo item to local todo storage."""
    task = (task or "").strip()
    if not task:
        return {"summary": "Todo task is required.", "error": "missing_task"}

    normalized_priority = (priority or "medium").strip().lower()
    allowed_priorities = {"critical", "high", "medium", "low"}
    if normalized_priority not in allowed_priorities:
        return {
            "summary": "Invalid priority. Use one of: critical, high, medium, low.",
            "error": "invalid_priority",
        }

    normalized_due = None
    if due_date:
        try:
            normalized_due = date.fromisoformat(str(due_date)).isoformat()
        except ValueError:
            return {
                "summary": "Invalid due_date format. Use YYYY-MM-DD.",
                "error": "invalid_due_date",
            }

    todos, err = _load_todos(_session)
    if err:
        return {"summary": err, "error": "todo_db_error"}

    item = {
        "id": uuid4().hex[:12],
        "task": task,
        "status": "open",
        "priority": normalized_priority,
        "due_date": normalized_due,
        "owner": (owner or "").strip() or None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    todos.append(item)

    path, err = _save_todos(todos, _session)
    if err:
        return {"summary": err, "error": "todo_db_error"}

    open_count = sum(1 for x in todos if x.get("status") == "open")
    return {
        "summary": f"Todo added ({item['id']}). Open items: {open_count}.",
        "item": item,
        "open_count": open_count,
        "path": str(path),
    }


@registry.register(
    name="ops.todo_list",
    description="List tracked todo items with status and priority ordering",
    category="ops",
    parameters={
        "status": "open|done|all (default open)",
        "limit": "Maximum items to return (default 50, max 200)",
    },
    usage_guide=(
        "Use at the start/end of sessions to manage execution backlog. "
        "Default ordering surfaces urgent and overdue items first."
    ),
)
def todo_list(status: str = "open", limit: int = 50, _session=None, **kwargs) -> dict:
    """Return todo items with deterministic ordering."""
    status_norm = (status or "open").strip().lower()
    if status_norm not in {"open", "done", "all"}:
        return {
            "summary": "Invalid status. Use open, done, or all.",
            "error": "invalid_status",
        }

    limit = max(1, min(int(limit), 200))
    todos, err = _load_todos(_session)
    if err:
        return {"summary": err, "error": "todo_db_error"}

    filtered = todos
    if status_norm != "all":
        filtered = [x for x in todos if x.get("status") == status_norm]

    def sort_key(item: dict) -> tuple:
        due = item.get("due_date") or "9999-12-31"
        created = item.get("created_at") or ""
        return (_priority_rank(str(item.get("priority", "medium"))), due, created)

    filtered = sorted(filtered, key=sort_key)
    limited = filtered[:limit]

    open_count = sum(1 for x in todos if x.get("status") == "open")
    done_count = sum(1 for x in todos if x.get("status") == "done")

    return {
        "summary": f"Listed {len(limited)} todo items (open={open_count}, done={done_count}).",
        "items": limited,
        "count": len(limited),
        "open_count": open_count,
        "done_count": done_count,
        "status_filter": status_norm,
        "path": str(_todos_path(_session)),
    }


@registry.register(
    name="ops.todo_get",
    description="Fetch a todo item by ID",
    category="ops",
    parameters={"todo_id": "Todo item ID"},
    usage_guide="Use to inspect a single todo in full detail.",
)
def todo_get(todo_id: str, _session=None, **kwargs) -> dict:
    """Get a todo item by ID."""
    needle = (todo_id or "").strip()
    if not needle:
        return {"summary": "todo_id is required.", "error": "missing_todo_id"}

    todos, err = _load_todos(_session)
    if err:
        return {"summary": err, "error": "todo_db_error"}

    for item in todos:
        if str(item.get("id", "")).strip() == needle:
            out = dict(item)
            out["summary"] = f"Todo item loaded: {needle}"
            out["path"] = str(_todos_path(_session))
            return out
    return {"summary": f"Todo item not found: {needle}", "error": "not_found"}


@registry.register(
    name="ops.todo_update",
    description="Update an existing todo item",
    category="ops",
    parameters={
        "todo_id": "Todo item ID",
        "task": "Optional replacement task text",
        "status": "Optional status: open|in_progress|blocked|done|cancelled",
        "priority": "Optional priority: critical|high|medium|low",
        "due_date": "Optional due date in YYYY-MM-DD (or empty to clear)",
        "owner": "Optional owner (or empty to clear)",
    },
    usage_guide="Use to track execution state and ownership of follow-up work.",
)
def todo_update(
    todo_id: str,
    task: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    due_date: str | None = None,
    owner: str | None = None,
    _session=None,
    **kwargs,
) -> dict:
    """Update a todo item by ID."""
    needle = (todo_id or "").strip()
    if not needle:
        return {"summary": "todo_id is required.", "error": "missing_todo_id"}

    todos, err = _load_todos(_session)
    if err:
        return {"summary": err, "error": "todo_db_error"}

    allowed_status = {"open", "in_progress", "blocked", "done", "cancelled"}
    allowed_priority = {"critical", "high", "medium", "low"}
    item = None
    for candidate in todos:
        if str(candidate.get("id", "")).strip() == needle:
            item = candidate
            break
    if item is None:
        return {"summary": f"Todo item not found: {needle}", "error": "not_found"}

    if task is not None:
        item["task"] = str(task).strip()
    if status is not None:
        normalized_status = str(status).strip().lower()
        if normalized_status not in allowed_status:
            return {
                "summary": "Invalid status. Use open, in_progress, blocked, done, cancelled.",
                "error": "invalid_status",
            }
        item["status"] = normalized_status
    if priority is not None:
        normalized_priority = str(priority).strip().lower()
        if normalized_priority not in allowed_priority:
            return {
                "summary": "Invalid priority. Use critical, high, medium, low.",
                "error": "invalid_priority",
            }
        item["priority"] = normalized_priority
    if due_date is not None:
        raw_due = str(due_date).strip()
        if raw_due:
            try:
                item["due_date"] = date.fromisoformat(raw_due).isoformat()
            except ValueError:
                return {
                    "summary": "Invalid due_date format. Use YYYY-MM-DD.",
                    "error": "invalid_due_date",
                }
        else:
            item["due_date"] = None
    if owner is not None:
        item["owner"] = str(owner).strip() or None

    if not str(item.get("task", "")).strip():
        return {"summary": "Todo task cannot be empty.", "error": "invalid_task"}
    item["updated_at"] = _now_iso()

    path, err = _save_todos(todos, _session)
    if err:
        return {"summary": err, "error": "todo_db_error"}
    return {"summary": f"Todo item updated: {needle}", "item": item, "path": str(path)}


@registry.register(
    name="ops.todo_delete",
    description="Delete a todo item by ID",
    category="ops",
    parameters={"todo_id": "Todo item ID"},
    usage_guide="Use to remove obsolete todo items.",
)
def todo_delete(todo_id: str, _session=None, **kwargs) -> dict:
    """Delete a todo item by ID."""
    needle = (todo_id or "").strip()
    if not needle:
        return {"summary": "todo_id is required.", "error": "missing_todo_id"}

    todos, err = _load_todos(_session)
    if err:
        return {"summary": err, "error": "todo_db_error"}

    original = len(todos)
    kept = [x for x in todos if str(x.get("id", "")).strip() != needle]
    if len(kept) == original:
        return {"summary": f"Todo item not found: {needle}", "error": "not_found"}

    path, err = _save_todos(kept, _session)
    if err:
        return {"summary": err, "error": "todo_db_error"}
    return {"summary": f"Todo item deleted: {needle}", "count": len(kept), "path": str(path)}
