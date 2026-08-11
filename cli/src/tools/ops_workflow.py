"""ops.workflow_*: reusable workflow template tools. Split from tools/ops.py."""
from __future__ import annotations

import json
import re
from pathlib import Path

from tools import registry
from tools.ops_common import _now_iso, _parse_int, _workflow_dir


def _slugify_name(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-._")
    return slug or "workflow"


def _list_workflow_files(_session=None) -> list[Path]:
    path = _workflow_dir(_session)
    return sorted([p for p in path.glob("*.json") if p.is_file()])


def _load_workflow_payload(path: Path) -> tuple[dict | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"Failed to read workflow file '{path.name}': {exc}"
    if not isinstance(payload, dict):
        return None, f"Invalid workflow file '{path.name}' (expected object)."
    return payload, None


def _find_workflow_path(identifier: str, _session=None) -> tuple[Path | None, str | None]:
    """Resolve workflow by file stem, file name, or display name."""
    ident = (identifier or "").strip()
    if not ident:
        return None, "Workflow identifier is required."

    candidates = _list_workflow_files(_session)
    if not candidates:
        return None, "No saved workflows."

    # 1) Exact filename match
    for path in candidates:
        if path.name == ident or path.stem == ident:
            return path, None

    # 2) Slug match
    slug = _slugify_name(ident)
    for path in candidates:
        if path.stem == slug:
            return path, None

    # 3) Match by workflow display name in payload
    lowered = ident.lower()
    for path in candidates:
        payload, error = _load_workflow_payload(path)
        if error or not payload:
            continue
        name = str(payload.get("name", "")).strip().lower()
        if name == lowered:
            return path, None

    return None, f"Workflow '{identifier}' not found."


def _normalize_workflow_steps(steps: list[dict] | str) -> tuple[list[dict] | None, str | None]:
    """Validate and normalize workflow step payloads."""
    if isinstance(steps, str):
        try:
            steps = json.loads(steps)
        except json.JSONDecodeError:
            return None, "Invalid steps payload. Provide JSON array or list of step objects."

    if not isinstance(steps, list) or not steps:
        return None, "Workflow steps must be a non-empty list."

    cleaned_steps = []
    for idx, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            return None, f"Step {idx} is not an object."
        tool = str(step.get("tool", "")).strip()
        description = str(step.get("description", "")).strip()
        if not tool:
            return None, f"Step {idx} is missing required field 'tool'."

        cleaned_steps.append(
            {
                "id": _parse_int(step.get("id", idx), idx),
                "description": description,
                "tool": tool,
                "tool_args": step.get("tool_args", {}) if isinstance(step.get("tool_args", {}), dict) else {},
                "depends_on": [
                    _parse_int(x, 0) for x in (step.get("depends_on", []) if isinstance(step.get("depends_on", []), list) else [])
                    if _parse_int(x, 0) > 0
                ],
            }
        )

    cleaned_steps.sort(key=lambda x: x["id"])
    return cleaned_steps, None


@registry.register(
    name="ops.workflow_save",
    description="Save a reusable workflow template from a plan-like step list",
    category="ops",
    parameters={
        "name": "Workflow template name",
        "query": "Original or canonical query this workflow answers",
        "steps": "List of step dicts (id/description/tool/tool_args/depends_on)",
        "notes": "Optional notes about assumptions or context",
    },
    usage_guide=(
        "Use after a successful run to preserve the strategy as a reusable template. "
        "Templates are stored locally and can be inspected with files.read_file."
    ),
)
def workflow_save(
    name: str,
    query: str,
    steps: list[dict] | str,
    notes: str = "",
    _session=None,
    **kwargs,
) -> dict:
    """Persist a validated workflow template to local JSON."""
    workflow_name = (name or "").strip()
    if not workflow_name:
        return {"summary": "Workflow name is required.", "error": "missing_name"}

    query = (query or "").strip()
    if not query:
        return {"summary": "Workflow query is required.", "error": "missing_query"}

    cleaned_steps, error = _normalize_workflow_steps(steps)
    if error:
        return {"summary": error, "error": "invalid_steps"}

    payload = {
        "name": workflow_name,
        "query": query,
        "notes": (notes or "").strip() or None,
        "created_at": _now_iso(),
        "version": 1,
        "steps": cleaned_steps,
    }

    out_dir = _workflow_dir(_session)
    stem = _slugify_name(workflow_name)
    out_path = out_dir / f"{stem}.json"
    suffix = 1
    while out_path.exists():
        suffix += 1
        out_path = out_dir / f"{stem}-{suffix}.json"

    try:
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:
        return {"summary": f"Failed to save workflow template: {exc}", "error": "write_failed"}

    return {
        "summary": f"Saved workflow template '{workflow_name}' with {len(cleaned_steps)} steps.",
        "workflow": payload,
        "path": str(out_path),
    }


@registry.register(
    name="ops.workflow_list",
    description="List saved workflow templates",
    category="ops",
    parameters={
        "limit": "Maximum workflows to return (default 50, max 200)",
        "query": "Optional keyword filter against name/query/notes",
    },
    usage_guide="Use to discover reusable workflow templates available in local storage.",
)
def workflow_list(limit: int = 50, query: str = "", _session=None, **kwargs) -> dict:
    """List workflow template metadata."""
    limit = max(1, min(_parse_int(limit, 50), 200))
    needle = (query or "").strip().lower()
    workflows = []
    for path in _list_workflow_files(_session):
        payload, error = _load_workflow_payload(path)
        if error or not payload:
            continue
        haystack = " ".join(
            [
                str(payload.get("name", "")),
                str(payload.get("query", "")),
                str(payload.get("notes", "")),
            ]
        ).lower()
        if needle and needle not in haystack:
            continue
        workflows.append(
            {
                "id": path.stem,
                "name": payload.get("name", path.stem),
                "query": payload.get("query", ""),
                "created_at": payload.get("created_at"),
                "updated_at": payload.get("updated_at"),
                "n_steps": len(payload.get("steps", []) if isinstance(payload.get("steps"), list) else []),
                "path": str(path),
            }
        )

    workflows.sort(key=lambda x: str(x.get("updated_at") or x.get("created_at") or ""), reverse=True)
    workflows = workflows[:limit]
    suffix = f" filter='{query}'" if needle else ""
    return {
        "summary": f"Listed {len(workflows)} workflow templates.{suffix}",
        "workflows": workflows,
        "count": len(workflows),
        "directory": str(_workflow_dir(_session)),
    }


@registry.register(
    name="ops.workflow_get",
    description="Load one saved workflow template by ID or name",
    category="ops",
    parameters={"workflow_id": "Workflow file stem, file name, or display name"},
    usage_guide="Use when you need full details of a saved workflow template.",
)
def workflow_get(workflow_id: str, _session=None, **kwargs) -> dict:
    """Get a workflow template payload."""
    path, error = _find_workflow_path(workflow_id, _session)
    if error:
        return {"summary": error, "error": "not_found"}

    payload, error = _load_workflow_payload(path)
    if error or payload is None:
        return {"summary": error or "Invalid workflow payload.", "error": "workflow_error"}

    payload = dict(payload)
    payload["summary"] = f"Workflow loaded: {payload.get('name', path.stem)}"
    payload["workflow_id"] = path.stem
    payload["path"] = str(path)
    return payload


@registry.register(
    name="ops.workflow_update",
    description="Update an existing workflow template",
    category="ops",
    parameters={
        "workflow_id": "Workflow file stem, file name, or display name",
        "name": "Optional replacement name",
        "query": "Optional replacement canonical query",
        "steps": "Optional replacement step list",
        "notes": "Optional replacement notes",
    },
    usage_guide="Use to keep reusable workflows current as your process evolves.",
)
def workflow_update(
    workflow_id: str,
    name: str | None = None,
    query: str | None = None,
    steps: list[dict] | str | None = None,
    notes: str | None = None,
    _session=None,
    **kwargs,
) -> dict:
    """Update workflow template fields and save in place."""
    path, error = _find_workflow_path(workflow_id, _session)
    if error:
        return {"summary": error, "error": "not_found"}

    payload, error = _load_workflow_payload(path)
    if error or payload is None:
        return {"summary": error or "Invalid workflow payload.", "error": "workflow_error"}

    if name is not None:
        payload["name"] = str(name).strip()
    if query is not None:
        payload["query"] = str(query).strip()
    if notes is not None:
        payload["notes"] = str(notes).strip() or None
    if steps is not None:
        cleaned_steps, step_error = _normalize_workflow_steps(steps)
        if step_error:
            return {"summary": step_error, "error": "invalid_steps"}
        payload["steps"] = cleaned_steps

    if not str(payload.get("name", "")).strip():
        return {"summary": "Workflow name cannot be empty.", "error": "invalid_name"}
    if not str(payload.get("query", "")).strip():
        return {"summary": "Workflow query cannot be empty.", "error": "invalid_query"}
    if not isinstance(payload.get("steps"), list) or not payload["steps"]:
        return {"summary": "Workflow requires at least one step.", "error": "invalid_steps"}

    payload["updated_at"] = _now_iso()
    payload["version"] = _parse_int(payload.get("version", 1), 1) + 1
    try:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:
        return {"summary": f"Failed to update workflow: {exc}", "error": "write_failed"}

    return {
        "summary": f"Workflow updated: {payload.get('name', path.stem)}",
        "workflow": payload,
        "path": str(path),
    }


@registry.register(
    name="ops.workflow_delete",
    description="Delete a saved workflow template",
    category="ops",
    parameters={"workflow_id": "Workflow file stem, file name, or display name"},
    usage_guide="Use to remove obsolete workflow templates.",
)
def workflow_delete(workflow_id: str, _session=None, **kwargs) -> dict:
    """Delete one workflow template."""
    path, error = _find_workflow_path(workflow_id, _session)
    if error:
        return {"summary": error, "error": "not_found"}

    try:
        path.unlink()
    except Exception as exc:
        return {"summary": f"Failed to delete workflow: {exc}", "error": "delete_failed"}
    return {"summary": f"Workflow deleted: {path.stem}", "path": str(path)}


@registry.register(
    name="ops.workflow_run",
    description="Execute a saved workflow template",
    category="ops",
    parameters={
        "workflow_id": "Workflow file stem, file name, or display name",
        "dry_run": "If true, return the resolved execution plan without running tools",
        "continue_on_error": "If true, continue executing later steps after failures",
    },
    usage_guide="Use to replay a validated workflow template against new inputs or contexts.",
)
def workflow_run(
    workflow_id: str,
    dry_run: bool = False,
    continue_on_error: bool = False,
    _session=None,
    _prior_results=None,
    **kwargs,
) -> dict:
    """Execute workflow steps in dependency order."""
    path, error = _find_workflow_path(workflow_id, _session)
    if error:
        return {"summary": error, "error": "not_found"}
    payload, error = _load_workflow_payload(path)
    if error or payload is None:
        return {"summary": error or "Invalid workflow payload.", "error": "workflow_error"}

    cleaned_steps, step_error = _normalize_workflow_steps(payload.get("steps", []))
    if step_error:
        return {"summary": f"Workflow invalid: {step_error}", "error": "invalid_steps"}

    if dry_run:
        return {
            "summary": f"[DRY RUN] Workflow '{payload.get('name', path.stem)}' ready with {len(cleaned_steps)} steps.",
            "workflow_id": path.stem,
            "name": payload.get("name", path.stem),
            "steps": cleaned_steps,
            "path": str(path),
        }

    from tools import registry as _tool_registry

    results = {}
    status_by_id = {step["id"]: "pending" for step in cleaned_steps}
    _step_index = {step["id"]: step for step in cleaned_steps}
    loop_guard = len(cleaned_steps) * 4 + 8
    iterations = 0
    executed = []

    while iterations < loop_guard:
        iterations += 1
        progressed = False

        for step in cleaned_steps:
            sid = step["id"]
            if status_by_id[sid] != "pending":
                continue
            deps = step.get("depends_on", [])
            if any(status_by_id.get(dep) not in {"completed"} for dep in deps):
                # If a dependency failed and we're strict, abort this step.
                if any(status_by_id.get(dep) == "failed" for dep in deps) and not continue_on_error:
                    status_by_id[sid] = "skipped"
                continue

            tool_name = step["tool"]
            tool = _tool_registry.get_tool(tool_name)
            if tool is None:
                status_by_id[sid] = "failed"
                results[sid] = {"error": "tool_not_found", "summary": f"Tool not found: {tool_name}"}
                if not continue_on_error:
                    return {
                        "summary": f"Workflow failed at step {sid}: tool not found ({tool_name}).",
                        "workflow_id": path.stem,
                        "results": results,
                        "status_by_step": status_by_id,
                    }
                progressed = True
                continue

            args = dict(step.get("tool_args", {}))
            for key, val in list(args.items()):
                if isinstance(val, str) and val.startswith("$step."):
                    parts = val.split(".")
                    if len(parts) < 2:
                        continue
                    ref_id = _parse_int(parts[1], -1)
                    if ref_id not in results:
                        continue
                    resolved = results[ref_id]
                    for field in parts[2:]:
                        if isinstance(resolved, dict) and field in resolved:
                            resolved = resolved[field]
                        else:
                            break
                    args[key] = resolved

            args["_session"] = _session
            args["_prior_results"] = dict(_prior_results or {}) | results
            try:
                result = tool.run(**args)
            except Exception as exc:
                result = {"error": "execution_exception", "summary": f"{tool_name} crashed: {exc}"}

            has_error = isinstance(result, dict) and result.get("error")
            results[sid] = result
            status_by_id[sid] = "failed" if has_error else "completed"
            executed.append({"step_id": sid, "tool": tool_name, "status": status_by_id[sid]})
            progressed = True

            if has_error and not continue_on_error:
                return {
                    "summary": f"Workflow failed at step {sid} ({tool_name}).",
                    "workflow_id": path.stem,
                    "name": payload.get("name", path.stem),
                    "results": results,
                    "status_by_step": status_by_id,
                    "executed": executed,
                }

        if not progressed:
            break

    pending = [sid for sid, st in status_by_id.items() if st == "pending"]
    if pending:
        for sid in pending:
            # unresolved dependencies / cycle
            status_by_id[sid] = "skipped"

    completed = sum(1 for st in status_by_id.values() if st == "completed")
    failed = sum(1 for st in status_by_id.values() if st == "failed")
    skipped = sum(1 for st in status_by_id.values() if st == "skipped")
    summary = (
        f"Workflow '{payload.get('name', path.stem)}' executed: "
        f"{completed} completed, {failed} failed, {skipped} skipped."
    )
    return {
        "summary": summary,
        "workflow_id": path.stem,
        "name": payload.get("name", path.stem),
        "results": results,
        "status_by_step": status_by_id,
        "executed": executed,
        "path": str(path),
    }
