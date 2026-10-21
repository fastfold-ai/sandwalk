"""Capy management tools — orchestrate chats, skills, MCP, and the local server."""

from __future__ import annotations

from tools import registry


def _deps():
    from agent_server.capy import capy_deps

    return capy_deps()


def _parse_grid(rows: int = 0, cols: int = 0, grid: str = "") -> dict[str, int] | None:
    """Return ``{rows, cols}`` or None.

    ``grid`` is columns × rows, the way a picture is described: ``4x2`` is
    4 panes across and 2 down. Explicit ``rows`` / ``cols`` override it.
    ``rows`` is horizontal bands, ``cols`` is panes in each band.
    """
    import re

    rows_n = int(rows or 0)
    cols_n = int(cols or 0)
    text = str(grid or "").strip().lower().replace("×", "x")
    match = re.fullmatch(r"(\d+)\s*x\s*(\d+)", text)
    if match and rows_n < 1 and cols_n < 1:
        cols_n = int(match.group(1))
        rows_n = int(match.group(2))
    if rows_n < 1 or cols_n < 1:
        return None
    if rows_n > 8 or cols_n > 8:
        return None
    return {"rows": rows_n, "cols": cols_n}


def _emit_open_split(session_ids: list[str], layout: dict[str, int] | None = None) -> None:
    from agent_server.session_event_bus import session_event_bus

    cleaned = [sid for sid in session_ids if sid]
    if len(cleaned) < 2:
        return
    payload: dict = {"action": "open_split", "sessionIds": cleaned}
    if layout:
        payload["layout"] = {"rows": layout["rows"], "cols": layout["cols"]}
    session_event_bus.publish("ui.command", payload)


def _resolve_project_id(store, spec: str = "current") -> dict:
    """Resolve current / all / id / name. current uses the UI sidebar scope."""
    from agent_server.capy.scope import get_capy_scope

    raw = str(spec or "current").strip()
    key = raw.lower()
    if key in {"", "current", "selected"}:
        pid = get_capy_scope().get("project_id")
        if not pid:
            return {"ok": True, "projectId": None, "projectName": None}
        project = store.get_project(pid)
        if project is None:
            return {"ok": True, "projectId": None, "projectName": None}
        return {"ok": True, "projectId": project.id, "projectName": project.name}
    if key in {"all", "none", "unassigned"}:
        return {"ok": True, "projectId": None, "projectName": None}
    project = store.get_project(raw)
    if project is not None:
        return {"ok": True, "projectId": project.id, "projectName": project.name}
    matches = [
        item
        for item in store.list_projects()
        if item.name.lower() == key or item.name.lower().startswith(key)
    ]
    if len(matches) == 1:
        return {"ok": True, "projectId": matches[0].id, "projectName": matches[0].name}
    if len(matches) > 1:
        names = ", ".join(item.name for item in matches[:8])
        return {"ok": False, "summary": f"Multiple projects match “{raw}”: {names}."}
    return {"ok": False, "summary": f"Project not found: {raw}."}


def _resolve_specialist_ref(deps, spec: str = ""):
    """Resolve a persona / specialist by id, slug, person name, or role label."""
    raw = str(spec or "").strip()
    if not raw or raw.lower() in {"none", "default"}:
        return None
    try:
        items = deps.specialists_service.list()
    except Exception:
        items = deps.store.list_specialists()
    key = raw.lower()
    for item in items:
        if item.id == raw or item.slug.lower() == key or item.name.strip().lower() == key:
            return item
    for item in items:
        role = str(getattr(item, "role_label", "") or "").strip().lower()
        if role and (role == key or key in role):
            return item
    for item in items:
        if key in item.name.strip().lower() or key in item.slug.lower():
            return item
    return None


@registry.register(
    name="capy.list_sessions",
    description="List worker chats (id, title, status). Excludes Capy and bench.",
    category="capy",
    usage_guide="Use to see worker chats the user can mention or route work to.",
    parameters={},
)
def capy_list_sessions(**kwargs) -> dict:
    store = _deps().store
    rows = []
    for session in store.list_sessions():
        source = str(getattr(session, "source", "") or "")
        if source in {"capy", "bench"}:
            continue
        rows.append(
            {
                "id": session.id,
                "title": session.title,
                "status": session.status,
                "projectId": session.project_id,
                "lastMessageAt": session.last_message_at,
            }
        )
    return {"summary": f"{len(rows)} chats.", "sessions": rows[:80]}


@registry.register(
    name="capy.read_session",
    description="Bounded extract of a worker chat (last turns, tools). Not a full dump.",
    category="capy",
    usage_guide="Use to pull a short excerpt from one worker chat before summarizing or seeding.",
    parameters={"session_id": "Chat id (from #mention or list_sessions)."},
)
def capy_read_session(session_id: str = "", **kwargs) -> dict:
    from agent_server.capy.extract import extract_session

    return extract_session(_deps().store, str(session_id).strip())


@registry.register(
    name="capy.summarize_session",
    description="Fetch a bounded extract so you can summarize the chat in your reply.",
    category="capy",
    usage_guide="Use when the user asks what happened in a specific chat.",
    parameters={"session_id": "Chat id to summarize."},
)
def capy_summarize_session(session_id: str = "", **kwargs) -> dict:
    from agent_server.capy.extract import extract_session

    result = extract_session(_deps().store, str(session_id).strip())
    if not result.get("ok"):
        return result
    result["summary"] = (
        f"Write a short summary of “{result.get('title')}” from the excerpt."
    )
    return result


@registry.register(
    name="capy.send_message",
    description="Send a follow-up message to an existing worker chat (starts a run).",
    category="capy",
    usage_guide="Use to continue an existing worker chat with a follow-up prompt.",
    parameters={
        "session_id": "Target chat id.",
        "content": "Message text for that chat.",
    },
)
def capy_send_message(session_id: str = "", content: str = "", **kwargs) -> dict:
    sid = str(session_id).strip()
    text = str(content or "").strip()
    if not sid or not text:
        return {"ok": False, "summary": "session_id and content are required."}
    deps = _deps()
    session = deps.store.get_session(sid)
    if session is None:
        return {"ok": False, "summary": "Session not found."}
    if str(getattr(session, "source", "") or "") in {"capy", "bench"}:
        return {"ok": False, "summary": "Cannot message Capy or bench from Capy."}
    try:
        started = deps.service.submit_message(session_id=sid, content=text)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": str(exc)}
    return {
        "ok": True,
        "summary": f"Sent to {session.title}.",
        "sessionId": sid,
        "runId": getattr(started, "run_id", None),
    }


@registry.register(
    name="capy.spawn_sessions",
    description="Create worker chats (optionally with an Agent Persona / Specialist like Atlas, Nova, Milo, Soren), send a first message, and open them in the UI.",
    category="capy",
    usage_guide="Pass specialist (or specialists as comma-separated names for multi-persona grids) when the user asks to spawn a chat with a specific persona, profile, or specialist. For a grid that is 4 panes across and 2 down, pass grid='4x2' or cols=4 and rows=2.",
    parameters={
        "count": "How many chats (1-16). Ignored when rows and cols (or grid) are set; then count is rows*cols.",
        "message": "Optional first user message for each chat.",
        "title_prefix": "Optional title prefix.",
        "project_id": "current (default), all, or a project id/name.",
        "specialist": "Optional persona / specialist name, role, slug, or id (e.g. 'Atlas', 'Nova', 'Dreamer', 'Project Manager', 'Soren', 'protein-designer').",
        "specialists": "Optional comma-separated persona/specialist names to assign across panes in order (e.g. 'Nova,Soren' for a 2-pane debate).",
        "rows": "Horizontal bands. 2 for a picture that is two panes tall.",
        "cols": "Panes across each band. 4 for a picture that is four panes wide.",
        "grid": "columns x rows, e.g. 4x2 means 4 across and 2 down.",
    },
)
def capy_spawn_sessions(
    count: int = 1,
    message: str = "",
    title_prefix: str = "",
    project_id: str = "current",
    specialist: str = "",
    specialists: str = "",
    rows: int = 0,
    cols: int = 0,
    grid: str = "",
    **kwargs,
) -> dict:
    layout = _parse_grid(rows, cols, grid)
    deps = _deps()
    spec_tokens = [
        part.strip()
        for part in (str(specialists or "").split(",") if specialists else ([specialist] if specialist else []))
        if part.strip()
    ]
    resolved_specs = []
    for token in spec_tokens:
        found = _resolve_specialist_ref(deps, token)
        if found is None:
            return {
                "ok": False,
                "summary": f"Specialist / persona not found: '{token}'. Call capy.list_specialists to see available personas.",
            }
        resolved_specs.append(found)

    if layout:
        n = max(1, min(16, layout["rows"] * layout["cols"]))
    elif len(resolved_specs) > 1 and int(count or 1) == 1:
        n = min(16, len(resolved_specs))
        layout = {"rows": 1, "cols": n}
    else:
        n = max(1, min(16, int(count or 1)))
    text = str(message or "").strip()
    prefix = str(title_prefix or "").strip()
    resolved = _resolve_project_id(deps.store, project_id)
    if not resolved["ok"]:
        return resolved
    pid = resolved["projectId"]
    ids: list[str] = []
    assigned_names: list[str] = []
    for index in range(n):
        chosen_spec = (
            resolved_specs[index % len(resolved_specs)] if resolved_specs else None
        )
        if prefix:
            chat_title = f"{prefix} {index + 1}" if n > 1 else prefix
        elif chosen_spec is not None:
            role = getattr(chosen_spec, "role_label", None) or chosen_spec.slug
            chat_title = f"{chosen_spec.name} · {role}"
        else:
            chat_title = f"Chat {index + 1}" if n > 1 else "Chat"
        session = deps.service.create_session(
            title=chat_title,
            workspace_path=None,
            project_id=pid,
            specialist_id=chosen_spec.id if chosen_spec else None,
            provider=getattr(chosen_spec, "provider", None) if chosen_spec else None,
            model=getattr(chosen_spec, "model", None) if chosen_spec else None,
            openai_profile_id=getattr(chosen_spec, "openai_profile_id", None) if chosen_spec else None,
            sandbox_backend="builtin",
            client_surface="ui",
        )
        ids.append(session.id)
        if chosen_spec is not None:
            assigned_names.append(chosen_spec.name)
        if text:
            try:
                deps.service.submit_message(session_id=session.id, content=text)
            except Exception:  # noqa: BLE001
                pass
    if len(ids) >= 2:
        _emit_open_split(ids, layout)
    elif len(ids) == 1:
        from agent_server.session_event_bus import session_event_bus

        session_event_bus.publish("ui.command", {"action": "open_item", "itemId": ids[0]})
    where = resolved.get("projectName") or "All"
    shape = ""
    if layout:
        shape = f" as {layout['cols']} across × {layout['rows']} down"
    persona_note = f" with {', '.join(assigned_names)}" if assigned_names else ""
    return {
        "ok": True,
        "summary": f"Created {n} chat(s){persona_note} in {where}{shape}.",
        "sessionIds": ids,
        "specialists": assigned_names,
        "projectId": pid,
        "layout": layout,
    }


@registry.register(
    name="capy.seed_session",
    description="Send imported context from a source chat into a target chat (or create target).",
    category="capy",
    usage_guide="Use to copy a brief from one chat into another (or a new chat).",
    parameters={
        "source_id": "Chat to extract from.",
        "target_id": "Existing target chat id, or empty to create one.",
        "brief": "Short imported brief (you write this from the extract).",
        "also_prompt": "Optional ask after the imported context.",
        "specialist": "Optional persona / specialist name or slug for a newly created target chat.",
    },
)
def capy_seed_session(
    source_id: str = "",
    target_id: str = "",
    brief: str = "",
    also_prompt: str = "",
    specialist: str = "",
    **kwargs,
) -> dict:
    from agent_server.capy.extract import extract_session

    deps = _deps()
    source = extract_session(deps.store, str(source_id).strip())
    if not source.get("ok"):
        return source
    body = str(brief or "").strip() or str(source.get("excerpt") or "")[:2000]
    extra = str(also_prompt or "").strip()
    title = source.get("title") or "another chat"
    content = f"Imported context from “{title}”:\n\n{body}"
    if extra:
        content = f"{content}\n\n{extra}"
    tid = str(target_id or "").strip()
    chosen_spec = _resolve_specialist_ref(deps, specialist) if specialist else None
    if tid:
        session = deps.store.get_session(tid)
        if session is None:
            return {"ok": False, "summary": "Target session not found."}
        if str(getattr(session, "source", "") or "") in {"capy", "bench"}:
            return {"ok": False, "summary": "Cannot seed Capy or bench."}
    else:
        session = deps.service.create_session(
            title=f"From {title}",
            workspace_path=None,
            project_id=_resolve_project_id(deps.store, "current").get("projectId"),
            specialist_id=chosen_spec.id if chosen_spec else None,
            sandbox_backend="builtin",
            client_surface="ui",
        )
        tid = session.id
    try:
        deps.service.submit_message(session_id=tid, content=content)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": str(exc)}
    return {
        "ok": True,
        "summary": f"Seeded {session.title}.",
        "targetId": tid,
        "sourceId": source.get("sessionId"),
    }


@registry.register(
    name="capy.open_split",
    description="Ask the UI to open the given worker chats as a rows-by-columns grid (needs 2+ ids).",
    category="capy",
    usage_guide="Pass grid='4x2' or cols=4 and rows=2 for 4 panes across and 2 down. Without rows/cols the UI puts every chat in a single row.",
    parameters={
        "session_ids": "Comma-separated chat ids.",
        "rows": "Horizontal bands (how many panes tall).",
        "cols": "Panes across each band.",
        "grid": "columns x rows, e.g. 4x2.",
    },
)
def capy_open_split(
    session_ids: str = "",
    rows: int = 0,
    cols: int = 0,
    grid: str = "",
    **kwargs,
) -> dict:
    raw = session_ids if isinstance(session_ids, str) else ",".join(session_ids or [])
    ids = [part.strip() for part in str(raw).split(",") if part.strip()]
    if len(ids) < 2:
        return {"ok": False, "summary": "Need at least two session ids."}
    layout = _parse_grid(rows, cols, grid)
    _emit_open_split(ids, layout)
    shape = (
        f" ({layout['cols']} across × {layout['rows']} down)" if layout else ""
    )
    return {
        "ok": True,
        "summary": f"Opening split of {len(ids)} chats{shape}.",
        "sessionIds": ids,
        "layout": layout,
    }


@registry.register(
    name="capy.skills_list",
    description="List installed skills (name, enabled). Management only.",
    category="capy",
    usage_guide="Use to inspect installed skills before enabling, disabling, or installing.",
    parameters={},
)
def capy_skills_list(**kwargs) -> dict:
    from agent.skills import list_skills

    skills = list_skills()
    rows = [
        {"name": item.name, "enabled": bool(getattr(item, "enabled", True))}
        for item in skills
    ]
    return {"summary": f"{len(rows)} skills.", "skills": rows}


@registry.register(
    name="capy.skills_install",
    description="Install a skill by name or slug. Does not run the skill.",
    category="capy",
    usage_guide="Use when the user wants a skill added to Sandwalk.",
    parameters={"name": "Skill name or install spec."},
)
def capy_skills_install(name: str = "", **kwargs) -> dict:
    from agent.skills import install_skill

    spec = str(name or "").strip()
    if not spec:
        return {"ok": False, "summary": "Skill name required."}
    result = install_skill(spec)
    if isinstance(result, dict):
        return result
    return {"ok": True, "summary": f"Installed {spec}."}


@registry.register(
    name="capy.skills_set_enabled",
    description="Enable or disable an installed skill.",
    category="capy",
    usage_guide="Use to turn an installed skill on or off.",
    parameters={"name": "Skill name.", "enabled": "true or false."},
)
def capy_skills_set_enabled(name: str = "", enabled: bool = True, **kwargs) -> dict:
    from agent.skills import set_skill_enabled

    spec = str(name or "").strip()
    if not spec:
        return {"ok": False, "summary": "Skill name required."}
    result = set_skill_enabled(spec, bool(enabled))
    if isinstance(result, dict):
        return result
    return {"ok": True, "summary": f"{spec} enabled={bool(enabled)}."}


@registry.register(
    name="capy.mcp_list",
    description="List configured MCP servers (id, name, enabled).",
    category="capy",
    usage_guide="Use to inspect configured MCP servers.",
    parameters={},
)
def capy_mcp_list(**kwargs) -> dict:
    store = _deps().store
    servers = store.list_mcp_servers() if hasattr(store, "list_mcp_servers") else []
    rows = [
        {
            "id": item.id,
            "name": getattr(item, "name", item.id),
            "enabled": bool(getattr(item, "enabled", True)),
        }
        for item in servers
    ]
    return {"summary": f"{len(rows)} MCP servers.", "servers": rows}


@registry.register(
    name="capy.app_status",
    description="Local Sandwalk version and whether the API is healthy.",
    category="capy",
    usage_guide="Use for a quick local app/version/health check.",
    parameters={},
)
def capy_app_status(**kwargs) -> dict:
    from _version import __version__

    deps = _deps()
    active = 0
    try:
        active = len(deps.service._active_runs)  # noqa: SLF001
    except Exception:  # noqa: BLE001
        active = -1
    return {
        "summary": f"Sandwalk {__version__}, {active} active runs.",
        "version": __version__,
        "activeRuns": active,
    }


@registry.register(
    name="capy.server_restart",
    description="Restart the local Sandwalk server process.",
    category="capy",
    usage_guide="Use only when the user asks to restart the local server.",
    parameters={},
)
def capy_server_restart(**kwargs) -> dict:
    from agent_server.status_service import schedule_restart

    result = schedule_restart()
    return {
        "ok": bool(getattr(result, "ok", True)),
        "summary": getattr(result, "message", None) or "Restart scheduled.",
    }


def _as_bool(value, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _csv(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _parse_suites(suite_ids: str, sample_size) -> list[dict]:
    """Parse `id,id` or `id:30,id:100`. Optional sample_size applies when omitted."""
    default_n = _as_int(sample_size)
    rows: list[dict] = []
    for part in _csv(suite_ids):
        sid, sep, size_raw = part.partition(":")
        sid = sid.strip()
        if not sid:
            continue
        n = _as_int(size_raw) if sep else default_n
        rows.append({"suite_id": sid, "sample_size": n})
    return rows


@registry.register(
    name="capy.bench_catalog",
    description=(
        "List Bench suites (id, title, available, sample sizes), enabled models, "
        "specialists, and current default model/provider. Call before launching."
    ),
    category="capy",
    usage_guide="Use before launching Bench to pick suite ids, models, and sample sizes.",
    parameters={},
)
def capy_bench_catalog(**kwargs) -> dict:
    from agent_server.bench_service import list_suite_cards
    from agent_server.settings_service import SettingsService

    deps = _deps()
    cards = list_suite_cards(deps.store)
    suites = [
        {
            "id": card.id,
            "title": card.title,
            "lane": card.lane,
            "available": card.available,
            "unavailableReason": card.unavailable_reason,
            "sampleSizes": card.sample_sizes,
            "defaultSampleSize": card.default_sample_size,
            "questionCount": card.question_count,
            "installable": card.installable,
            "installed": card.installed,
            "missingSkills": card.missing_skills,
            "missingMcps": card.missing_mcps,
        }
        for card in cards
    ]
    models = []
    try:
        listed = deps.models_service.list_models(enabled_only=True, discover=False)
        models = [
            {
                "id": item.id,
                "label": item.label,
                "provider": item.provider,
                "supportsReasoningEffort": item.supports_reasoning_effort,
            }
            for item in listed.data
        ]
    except Exception as exc:  # noqa: BLE001
        models = [{"error": str(exc)}]
    specialists = []
    try:
        specialists = [
            {"id": item.id, "name": item.name, "slug": getattr(item, "slug", None)}
            for item in deps.specialists_service.list()
        ]
    except Exception:  # noqa: BLE001
        specialists = []
    settings = SettingsService.get()
    available_n = sum(1 for card in cards if card.available)
    return {
        "summary": f"{available_n}/{len(cards)} suites available; {len(models)} models.",
        "defaults": {
            "model": settings.model,
            "provider": settings.provider,
            "concurrency": 1,
            "parallelRuns": 4,
            "thinking": False,
            "cleanupSessions": False,
            "dryRun": False,
        },
        "suites": suites,
        "models": models,
        "specialists": specialists,
    }


@registry.register(
    name="capy.bench_status",
    description="Current Bench queue: running, queued, paused stacks.",
    category="capy",
    usage_guide="Use to see whether Bench runs are queued, running, or paused.",
    parameters={},
)
def capy_bench_status(**kwargs) -> dict:
    from agent_server.bench_service import get_active_status

    status = get_active_status()
    payload = status.model_dump(by_alias=True)
    phase = status.phase or ("running" if status.running else "idle")
    return {
        "summary": (
            f"Bench {phase}"
            + (f" · {status.current_model}" if status.current_model else "")
            + f" · {len(status.queue)} queued · {len(status.inflight)} in flight."
        ),
        "status": payload,
    }


@registry.register(
    name="capy.bench_launch",
    description=(
        "Queue Bench run(s) like Dashboard → Bench. Requires suite_ids from "
        "bench_catalog. Optional compare models, sample size, specialist, "
        "concurrency, parallel_runs, thinking, cleanup_sessions, dry_run."
    ),
    category="capy",
    usage_guide="Use to queue Bench runs the same way as Dashboard → Bench.",
    parameters={
        "suite_ids": "Comma-separated suite ids, optionally id:sampleSize.",
        "model": "Primary model id (defaults to settings if omitted).",
        "models": "Extra compare-queue model ids, comma-separated.",
        "sample_size": "Sample size for suites that omit id:N.",
        "specialist_id": "Optional specialist id (empty = default agent).",
        "provider": "Optional provider override.",
        "project_name": "Optional bench project name.",
        "concurrency": "Workers per suite (default 1).",
        "parallel_runs": "Independent stacks in parallel (UI default 4).",
        "thinking": "true to enable thinking.",
        "cleanup_sessions": "true to delete bench sessions after success.",
        "dry_run": "true to enqueue a dry run.",
    },
)
def capy_bench_launch(
    suite_ids: str = "",
    model: str = "",
    models: str = "",
    sample_size=None,
    specialist_id: str = "",
    provider: str = "",
    project_name: str = "",
    concurrency=1,
    parallel_runs=4,
    thinking=False,
    cleanup_sessions=False,
    dry_run=False,
    **kwargs,
) -> dict:
    from agent_server.bench_service import enqueue
    from agent_server.models.bench import BenchSpawnRequest, BenchSuiteRef

    suites = _parse_suites(suite_ids, sample_size)
    if not suites:
        return {
            "ok": False,
            "summary": "suite_ids required (from bench_catalog), e.g. gpqa or gpqa:30.",
        }
    extra = _csv(models)
    primary = str(model or "").strip() or None
    req = BenchSpawnRequest(
        suites=[BenchSuiteRef(**row) for row in suites],
        model=primary,
        models=extra,
        provider=str(provider or "").strip() or None,
        project_name=str(project_name or "").strip() or None,
        specialist_id=str(specialist_id or "").strip() or None,
        thinking=_as_bool(thinking),
        dry_run=_as_bool(dry_run),
        concurrency=max(1, _as_int(concurrency, 1) or 1),
        parallel_runs=_as_int(parallel_runs, 4),
        cleanup_sessions=_as_bool(cleanup_sessions),
        client_surface="ui",
    )
    try:
        run_ids = enqueue(_deps(), req)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": str(exc)}
    names = ", ".join(row["suite_id"] for row in suites)
    return {
        "ok": True,
        "summary": f"Queued {len(run_ids)} bench stack(s) for {names}.",
        "runIds": run_ids,
        "suites": suites,
        "model": primary,
        "models": extra,
    }


@registry.register(
    name="capy.bench_install",
    description="Start downloading an installable Bench dataset (same as UI Install).",
    category="capy",
    usage_guide="Use to download an installable Bench dataset.",
    parameters={"suite_id": "Suite id from bench_catalog (installable=true)."},
)
def capy_bench_install(suite_id: str = "", **kwargs) -> dict:
    from agent_server.bench_service.dataset_install import BenchInstallError
    from agent_server.bench_service.install_jobs import start_install

    key = str(suite_id or "").strip()
    if not key:
        return {"ok": False, "summary": "suite_id required."}
    try:
        result = start_install(key)
    except BenchInstallError as exc:
        return {
            "ok": False,
            "summary": str(exc),
            "needsHfToken": bool(getattr(exc, "needs_hf_token", False)),
        }
    return {
        "ok": bool(result.ok),
        "summary": result.summary or f"Installing {key}.",
        "suiteId": result.suite_id,
        "status": result.status,
        "needsHfToken": result.needs_hf_token,
    }


def _attach_tokens(rows: list[dict]) -> list[dict]:
    ids = [str(row.get("run_id") or "") for row in rows if row.get("run_id")]
    tokens = {}
    try:
        tokens = _deps().store.lifetime_tokens_by_run(ids)
    except Exception:  # noqa: BLE001
        tokens = {}
    out = []
    for row in rows:
        rid = str(row.get("run_id") or "")
        item = dict(row)
        if item.get("lifetime_tokens") in (None, ""):
            item["lifetime_tokens"] = tokens.get(rid)
        out.append(item)
    return out


def _question_brief(questions: list, *, cap: int = 12) -> dict:
    graded = [q for q in questions if isinstance(q, dict) and not q.get("skipped")]
    wrong = [q for q in graded if not q.get("correct")]
    skipped = [q for q in questions if isinstance(q, dict) and q.get("skipped")]
    samples = []
    for q in wrong[:cap]:
        samples.append(
            {
                "id": q.get("id") or q.get("question_id"),
                "category": q.get("category"),
                "correct": False,
                "prompt": str(q.get("prompt") or q.get("question") or "")[:240],
            }
        )
    return {
        "wrong": len(wrong),
        "skipped": len(skipped),
        "showingWrong": samples,
    }


@registry.register(
    name="capy.bench_results",
    description=(
        "List Bench runs with accuracy, status, duration, and token usage. "
        "Same list as Dashboard → Bench results."
    ),
    category="capy",
    usage_guide="Use to list completed or in-progress Bench runs and scores.",
    parameters={
        "q": "Optional search (model, suite, run id, name).",
        "suite": "Optional suite/benchmark id filter.",
        "status": "Optional status filter, e.g. completed,running,paused.",
        "provider": "Optional provider filter.",
        "sort": "date_desc, date_asc, usage_desc, or usage_asc.",
        "limit": "Page size (default 25, max 50).",
    },
)
def capy_bench_results(
    q: str = "",
    suite: str = "",
    status: str = "",
    provider: str = "",
    sort: str = "date_desc",
    limit=25,
    **kwargs,
) -> dict:
    from agent_server.bench_service import list_results_page
    from agent_server.bench_service.results_store import slice_page

    sort_key = str(sort or "date_desc").strip().lower()
    usage_sort = sort_key in {"usage_desc", "usage_asc"}
    date_sort = "date_asc" if sort_key == "date_asc" else "date_desc"
    size = max(1, min(50, _as_int(limit, 25) or 25))
    page = list_results_page(
        limit=size,
        q=str(q or "").strip() or None,
        suite=str(suite or "").strip() or None,
        status=str(status or "").strip() or None,
        provider=str(provider or "").strip() or None,
        sort=date_sort,
        paginate=not usage_sort,
    )
    rows = _attach_tokens(list(page.get("data") or []))
    if usage_sort:
        reverse = sort_key == "usage_desc"

        def usage_key(row: dict) -> tuple[int, str]:
            rid = str(row.get("run_id") or "")
            n = int(row.get("lifetime_tokens") or 0)
            return (n, rid)

        rows.sort(key=usage_key, reverse=reverse)
        sliced = slice_page(rows, limit=size, cursor=None)
        rows = sliced["data"]
        page["total"] = sliced["total"]
    compact = [
        {
            "runId": row.get("run_id"),
            "name": row.get("name"),
            "suite": row.get("benchmark"),
            "model": row.get("model_id"),
            "provider": row.get("provider"),
            "status": row.get("status"),
            "accuracy": row.get("accuracy"),
            "correct": row.get("correct"),
            "total": row.get("total"),
            "timeS": row.get("time_s"),
            "lifetimeTokens": row.get("lifetime_tokens"),
            "createdAt": row.get("created_at"),
        }
        for row in rows
    ]
    total = int(page.get("total") or len(compact))
    return {
        "summary": f"{len(compact)} of {total} bench runs.",
        "runs": compact,
        "total": total,
    }


@registry.register(
    name="capy.bench_inspect",
    description=(
        "Inspect one Bench run: scores, token usage, timing, category scores, "
        "and a sample of incorrect questions. Pass run_id from bench_results."
    ),
    category="capy",
    usage_guide="Use to inspect one Bench run’s scores, tokens, and missed questions.",
    parameters={"run_id": "Bench run id."},
)
def capy_bench_inspect(run_id: str = "", **kwargs) -> dict:
    from agent_server.bench_service import (
        apply_live_status,
        get_result,
        resolve_result_run_id,
        result_from_checkpoint,
    )
    from agent_server.bench_service.checkpoint import load_checkpoint

    key = str(run_id or "").strip()
    if not key:
        return {"ok": False, "summary": "run_id required."}
    rid = resolve_result_run_id(key) or key
    row = get_result(rid)
    if row is None:
        ckpt = load_checkpoint(rid) or load_checkpoint(key)
        if ckpt is None:
            return {"ok": False, "summary": f"Run {key} not found."}
        row = result_from_checkpoint(ckpt)
    live = apply_live_status(row)
    questions = live.get("questions") if isinstance(live.get("questions"), list) else []
    tokens = _attach_tokens([live])[0]
    acc = tokens.get("accuracy")
    acc_pct = f"{float(acc) * 100:.1f}%" if acc is not None else "n/a"
    tok = tokens.get("lifetime_tokens")
    brief = _question_brief(questions)
    return {
        "ok": True,
        "summary": (
            f"{tokens.get('benchmark') or rid}: {acc_pct} "
            f"({tokens.get('correct')}/{tokens.get('total')}), "
            f"{tok or 0} tokens, {tokens.get('time_s') or 0}s, "
            f"{brief['wrong']} wrong."
        ),
        "run": {
            "runId": tokens.get("run_id") or rid,
            "name": tokens.get("name"),
            "suite": tokens.get("benchmark"),
            "model": tokens.get("model_id"),
            "provider": tokens.get("provider"),
            "status": tokens.get("status"),
            "accuracy": tokens.get("accuracy"),
            "correct": tokens.get("correct"),
            "total": tokens.get("total"),
            "skipped": tokens.get("skipped"),
            "timeS": tokens.get("time_s"),
            "thinkingUsed": tokens.get("thinking_used"),
            "reasoningEffort": tokens.get("reasoning_effort"),
            "inputTokens": tokens.get("input_tokens"),
            "outputTokens": tokens.get("output_tokens"),
            "lifetimeTokens": tokens.get("lifetime_tokens"),
            "createdAt": tokens.get("created_at"),
            "categoryScores": tokens.get("category_scores") or {},
            "questions": brief,
        },
    }


def _log_issue_lines(*, max_lines: int = 12) -> dict:
    from agent.diagnostics.collectors import _collect_log_files, _read_log_tail

    files = _collect_log_files()
    if not files:
        return {"files": [], "issues": [], "note": "No log files under the Sandwalk logs dir."}
    newest = files[0]
    tail = _read_log_tail(newest)
    issues = []
    needles = ("error", "exception", "traceback", "warn", "critical")
    for line in tail.splitlines()[::-1]:
        low = line.lower()
        if any(n in low for n in needles):
            issues.append(line.strip()[:400])
        if len(issues) >= max_lines:
            break
    issues.reverse()
    return {
        "files": [path.name for path in files[:8]],
        "newest": newest.name,
        "issues": issues,
    }


@registry.register(
    name="capy.doctor",
    description=(
        "Run Sandwalk Doctor (same as Dashboard → Doctor) and return a "
        "diagnostics summary: check counts, errors/warns with fixes, system "
        "info, skills, and recent log issues. Does not download a zip."
    ),
    category="capy",
    usage_guide="Use when the user asks if Sandwalk is healthy or why something is broken.",
    parameters={"scope": "full (default) or core."},
)
def capy_doctor(scope: str = "full", **kwargs) -> dict:
    from _version import __version__
    from agent.diagnostics.collectors import _skills_summary, _system_info
    from agent.diagnostics.logging_setup import ensure_logging_configured
    from agent.doctor import to_report

    normalized = str(scope or "full").strip().lower()
    if normalized not in {"full", "core"}:
        normalized = "full"
    ensure_logging_configured()
    report = to_report(scope=normalized)
    summary = report.get("summary") or {}
    checks = list(report.get("checks") or [])
    problems = [
        {
            "name": item.get("name"),
            "status": item.get("status"),
            "category": item.get("category"),
            "detail": item.get("detail"),
            "fix": item.get("fix"),
        }
        for item in checks
        if item.get("status") in {"error", "warn"}
    ]
    diagnostics = {
        "system": _system_info(__version__),
        "skills": _skills_summary(),
        "logs": _log_issue_lines(),
    }
    err_n = int(summary.get("error") or 0)
    warn_n = int(summary.get("warn") or 0)
    ok_n = int(summary.get("ok") or 0)
    headline = (
        f"Doctor {normalized}: {ok_n} ok, {warn_n} warn, {err_n} error "
        f"({summary.get('total') or len(checks)} checks)."
    )
    return {
        "ok": bool(report.get("ok")),
        "summary": headline,
        "scope": normalized,
        "counts": summary,
        "problems": problems,
        "checks": checks,
        "diagnostics": diagnostics,
    }


@registry.register(
    name="capy.list_projects",
    description="List projects (id, name, chat count) plus the current UI scope.",
    category="capy",
    usage_guide="Use to see projects and the current sidebar scope (All vs a project).",
    parameters={},
)
def capy_list_projects(**kwargs) -> dict:
    from agent_server.capy.scope import get_capy_scope

    store = _deps().store
    scope = get_capy_scope()
    rows = [
        {
            "id": item.id,
            "name": item.name,
            "sessionCount": item.session_count,
            "pinned": item.pinned,
        }
        for item in store.list_projects()
    ]
    current = None
    if scope.get("project_id"):
        current = next((row for row in rows if row["id"] == scope["project_id"]), None)
    return {
        "summary": (
            f"{len(rows)} projects. UI scope: "
            + (f"“{current['name']}”" if current else "All")
            + "."
        ),
        "projects": rows,
        "currentProjectId": scope.get("project_id"),
        "currentSessionId": scope.get("session_id"),
    }


@registry.register(
    name="capy.create_project",
    description="Create a project. Optionally create a first chat inside it.",
    category="capy",
    usage_guide="Use to create a project, optionally with a first chat.",
    parameters={
        "name": "Project name.",
        "description": "Optional description.",
        "create_chat": "true to also create one chat in the new project.",
        "message": "Optional first message for that chat.",
    },
)
def capy_create_project(
    name: str = "",
    description: str = "",
    create_chat=False,
    message: str = "",
    **kwargs,
) -> dict:
    title = str(name or "").strip()
    if not title:
        return {"ok": False, "summary": "Project name required."}
    deps = _deps()
    try:
        project = deps.store.create_project(
            name=title,
            description=str(description or "").strip() or None,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": str(exc)}
    session_id = None
    if _as_bool(create_chat) or str(message or "").strip():
        session = deps.service.create_session(
            title=title,
            workspace_path=None,
            project_id=project.id,
            sandbox_backend="builtin",
            client_surface="ui",
        )
        session_id = session.id
        text = str(message or "").strip()
        if text:
            try:
                deps.service.submit_message(session_id=session.id, content=text)
            except Exception:  # noqa: BLE001
                pass
    return {
        "ok": True,
        "summary": f"Created project “{project.name}”.",
        "projectId": project.id,
        "sessionId": session_id,
    }


@registry.register(
    name="capy.move_session",
    description="Move one or more chats into a project, or All (unassigned).",
    category="capy",
    usage_guide="Use to move worker chats into a project or All.",
    parameters={
        "session_ids": "Comma-separated chat ids.",
        "project_id": "Project id/name, current, or all.",
    },
)
def capy_move_session(session_ids: str = "", project_id: str = "current", **kwargs) -> dict:
    deps = _deps()
    resolved = _resolve_project_id(deps.store, project_id)
    if not resolved["ok"]:
        return resolved
    ids = _csv(session_ids)
    if not ids:
        return {"ok": False, "summary": "session_ids required."}
    moved = []
    errors = []
    for sid in ids:
        session = deps.store.get_session(sid)
        if session is None:
            errors.append(sid)
            continue
        if str(getattr(session, "source", "") or "") in {"capy", "bench"}:
            errors.append(sid)
            continue
        try:
            deps.service.update_session(
                session_id=sid,
                title=None,
                organize_label=None,
                update_organize_label=False,
                project_id=resolved["projectId"],
                update_project_id=True,
            )
            moved.append(sid)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{sid}: {exc}")
    where = resolved.get("projectName") or "All"
    return {
        "ok": bool(moved) and not errors,
        "summary": f"Moved {len(moved)} chat(s) to {where}.",
        "sessionIds": moved,
        "errors": errors,
        "projectId": resolved["projectId"],
    }


# --- Other coding-agent CLIs (Claude Code, Codex, OpenCode, fx) -----------------


def _external_workspace(deps, project_id: str, workspace_path: str) -> tuple[str | None, str | None, dict | None]:
    """Resolve (workspace, project_id) for external-agent tools."""
    folder = str(workspace_path or "").strip() or None
    resolved = _resolve_project_id(deps.store, project_id)
    if not resolved["ok"]:
        return None, None, resolved
    pid = resolved["projectId"]
    if not folder and pid:
        project = deps.store.get_project(pid)
        folder = getattr(project, "folder_path", None) if project else None
    return folder, pid, None


@registry.register(
    name="capy.list_external_sessions",
    description="List recent Claude Code, Codex, OpenCode, fx, and Hermes sessions on this machine (and which of those CLIs are installed).",
    category="capy",
    usage_guide="Use before importing. Pass agent to filter (claude, codex, opencode, fx, hermes) and workspace_path to scope to one folder; otherwise the current project's folder is used when it has one.",
    parameters={
        "agent": "Optional: claude, codex, opencode, fx, or hermes. Empty lists all of them.",
        "workspace_path": "Optional folder to scope the list to.",
        "project_id": "current (default), all, or a project id/name — its folder scopes the list when workspace_path is empty.",
        "limit": "Max sessions (default 20).",
    },
)
def capy_list_external_sessions(
    agent: str = "",
    workspace_path: str = "",
    project_id: str = "current",
    limit: int = 20,
    **kwargs,
) -> dict:
    from agent_server import external_agents_service as svc

    deps = _deps()
    folder, _pid, err = _external_workspace(deps, project_id, workspace_path)
    if err:
        return err
    kind = str(agent or "").strip() or None
    try:
        sessions = svc.list_external(kind, folder, max(1, min(100, int(limit or 20))))
    except svc.ExternalAgentError as exc:
        return {"ok": False, "summary": str(exc)}
    installed = [row["label"] for row in svc.list_installed() if row["installed"]]
    scope = f" in {folder}" if folder else ""
    return {
        "ok": True,
        "summary": f"{len(sessions)} external session(s){scope}. Installed: {', '.join(installed) or 'none'}.",
        "installed": svc.list_installed(),
        "sessions": sessions,
    }


@registry.register(
    name="capy.import_external_session",
    description="Convert a Claude Code / Codex / OpenCode / fx / Hermes session into a Sandwalk chat (history only; no model run).",
    category="capy",
    usage_guide="Use after list_external_sessions. The new chat keeps the original folder as its workspace and lands in the chosen project.",
    parameters={
        "agent": "claude, codex, opencode, fx, or hermes.",
        "session_id": "The external session id from list_external_sessions.",
        "project_id": "current (default), all, or a project id/name.",
    },
)
def capy_import_external_session(
    agent: str = "",
    session_id: str = "",
    project_id: str = "current",
    **kwargs,
) -> dict:
    from agent_server import external_agents_service as svc

    deps = _deps()
    resolved = _resolve_project_id(deps.store, project_id)
    if not resolved["ok"]:
        return resolved
    try:
        session = svc.import_session(
            service=deps.service,
            store=deps.store,
            kind=str(agent or ""),
            session_id=str(session_id or ""),
            project_id=resolved["projectId"],
        )
    except (svc.ExternalAgentError, ValueError) as exc:
        return {"ok": False, "summary": str(exc)}
    return {
        "ok": True,
        "summary": f"Imported “{session.title}” from {session.source_label} into {resolved.get('projectName') or 'All'}.",
        "sessionId": session.id,
        "title": session.title,
        "workspacePath": session.workspace_path,
    }


@registry.register(
    name="capy.launch_external_agent",
    description="Open a terminal running Claude Code, Codex, OpenCode, fx, or Hermes in a folder, optionally with a first prompt or resuming one of its sessions.",
    category="capy",
    usage_guide="Use when the user wants to start or continue work in one of those CLIs. Defaults to the current project's folder.",
    parameters={
        "agent": "claude, codex, opencode, fx, or hermes.",
        "workspace_path": "Folder to open in. Empty uses the current project's folder, then the home folder.",
        "prompt": "Optional first message for the CLI.",
        "resume_id": "Optional external session id to resume instead of starting fresh.",
        "project_id": "current (default), all, or a project id/name for the new terminal.",
    },
)
def capy_launch_external_agent(
    agent: str = "",
    workspace_path: str = "",
    prompt: str = "",
    resume_id: str = "",
    project_id: str = "current",
    **kwargs,
) -> dict:
    from agent_server import external_agents_service as svc

    deps = _deps()
    folder, pid, err = _external_workspace(deps, project_id, workspace_path)
    if err:
        return err
    try:
        result = deps.pty_manager.run_sync(
            svc.launch_terminal(
                store=deps.store,
                pty_manager=deps.pty_manager,
                kind=str(agent or ""),
                workspace_path=folder,
                project_id=pid,
                prompt=str(prompt or "").strip() or None,
                resume_id=str(resume_id or "").strip() or None,
            )
        )
    except svc.ExternalAgentError as exc:
        return {"ok": False, "summary": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": f"Could not open the terminal: {exc}"}
    terminal = result["terminal"]
    from agent_server.session_event_bus import session_event_bus

    session_event_bus.publish("ui.command", {"action": "open_item", "itemId": terminal["id"]})
    return {
        "ok": True,
        "summary": f"Opened {terminal['title']} in {terminal.get('workspacePath') or 'home'}.",
        "terminalId": terminal["id"],
        "command": result["command"],
    }


@registry.register(
    name="capy.handoff_session",
    description="Hand a Sandwalk chat to Claude Code, Codex, OpenCode, fx, or Hermes: writes a transcript file in its folder and opens that CLI on it.",
    category="capy",
    usage_guide="Use when the user wants to continue a Sandwalk chat inside one of those CLIs.",
    parameters={
        "session_id": "Sandwalk chat id (from #mention or list_sessions).",
        "agent": "claude, codex, opencode, fx, or hermes.",
    },
)
def capy_handoff_session(session_id: str = "", agent: str = "", **kwargs) -> dict:
    from agent_server import external_agents_service as svc

    deps = _deps()
    sid = str(session_id or "").strip()
    chat = deps.store.get_session(sid) if sid else None
    if chat is None:
        return {"ok": False, "summary": "Session not found."}
    if str(getattr(chat, "source", "") or "") in {"capy", "bench"}:
        return {"ok": False, "summary": "Cannot hand off Capy or bench chats."}
    try:
        exported = svc.export_handoff(service=deps.service, store=deps.store, session_id=sid, kind=str(agent or ""))
        launched = deps.pty_manager.run_sync(
            svc.launch_terminal(
                store=deps.store,
                pty_manager=deps.pty_manager,
                kind=str(agent or ""),
                workspace_path=exported["workspacePath"],
                project_id=chat.project_id,
                origin_chat_id=sid,
                prompt=exported["prompt"],
            )
        )
    except svc.ExternalAgentError as exc:
        return {"ok": False, "summary": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": f"Could not open the terminal: {exc}"}
    from agent_server.session_event_bus import session_event_bus

    session_event_bus.publish("ui.command", {"action": "open_item", "itemId": launched["terminal"]["id"]})
    return {
        "ok": True,
        "summary": f"Handed “{chat.title}” to {launched['terminal']['title']} ({exported['messages']} messages).",
        "terminalId": launched["terminal"]["id"],
        "path": exported["path"],
    }


@registry.register(
    name="capy.list_specialists",
    description="List available Agent Personas and Specialists (id, name, role, slug, priors, memory count, cookbook lens).",
    category="capy",
    usage_guide="Use before spawning a chat with a persona/specialist or when the user asks what personas/specialists exist.",
    parameters={},
)
def capy_list_specialists(**kwargs) -> dict:
    deps = _deps()
    items = deps.specialists_service.list()
    rows = [
        {
            "id": s.id,
            "name": s.name,
            "slug": s.slug,
            "role": getattr(s, "role_label", None) or s.description or s.slug,
            "cookbook": getattr(s, "cookbook_id", None) or "biomed-research",
            "priors": getattr(s, "priors", None) or "",
            "memoryCount": getattr(s, "memory_count", 0),
            "enabled": s.enabled,
        }
        for s in items
    ]
    return {
        "ok": True,
        "count": len(rows),
        "specialists": rows,
        "summary": f"{len(rows)} agent personas/specialists available.",
    }


@registry.register(
    name="capy.memory_search",
    description="Search Sandwalk's curated memories, past session transcripts, and knowledge graph claims.",
    category="capy",
    usage_guide="Use when the user asks what we know, decided, or learned across sessions or projects.",
    parameters={
        "query": "Search query (optional; leave empty to list current scope memories and graph overview).",
        "scope": "Scope: 'global', 'project:<id>', or 'specialist:<id>' (defaults to current UI project or 'global').",
    },
)
def capy_memory_search(query: str = "", scope: str = "", **kwargs) -> dict:
    from agent_server.capy.scope import get_capy_scope
    from agent_server.memory_service import MemoryService, search_past_sessions

    deps = _deps()
    resolved_scope = str(scope or "").strip()
    if not resolved_scope:
        pid = get_capy_scope().get("project_id")
        resolved_scope = f"project:{pid}" if pid else "global"
    svc = MemoryService(agent_store=deps.store)
    entries = svc.list_entries(resolved_scope).data
    snap = svc.get_graph(resolved_scope)
    q = str(query or "").strip()
    session_hits = search_past_sessions(deps.store, q, limit=5) if q else []
    if q:
        low = q.lower()
        entries = [e for e in entries if low in e.content.lower() or any(low in t.lower() for t in e.tags)]
    return {
        "ok": True,
        "scope": resolved_scope,
        "cookbook": snap.active_cookbook.name,
        "memories": [e.model_dump(mode="json", by_alias=True) for e in entries[:15]],
        "graphNodes": len(snap.nodes),
        "graphEdges": len(snap.edges),
        "contradictions": snap.contradiction_count,
        "sessionMatches": session_hits,
        "summary": (
            f"Scope {resolved_scope} ({snap.active_cookbook.name}): "
            f"{len(entries)} matching memory note(s), {len(snap.nodes)} graph node(s), "
            f"{snap.contradiction_count} contradiction(s), and {len(session_hits)} session match(es)."
        ),
    }


@registry.register(
    name="capy.wiki_digest",
    description="List or read Living Markdown Wiki pages for the current project or global brain.",
    category="capy",
    usage_guide="Use to inspect synthesized Wiki pages and [[wikilinks]].",
    parameters={
        "slug": "Optional page slug to read in full (omit to list all pages in scope).",
        "scope": "Optional scope ('global' or 'project:<id>').",
    },
)
def capy_wiki_digest(slug: str = "", scope: str = "", **kwargs) -> dict:
    from agent_server.capy.scope import get_capy_scope
    from agent_server.memory_service import MemoryService

    deps = _deps()
    resolved_scope = str(scope or "").strip()
    if not resolved_scope:
        pid = get_capy_scope().get("project_id")
        resolved_scope = f"project:{pid}" if pid else "global"
    svc = MemoryService(agent_store=deps.store)
    if str(slug or "").strip():
        page = svc.get_wiki_page(slug.strip(), scope=resolved_scope)
        if page is None:
            return {"ok": False, "summary": f"Wiki page '{slug}' not found in {resolved_scope}."}
        return {
            "ok": True,
            "summary": f"Wiki page [[{page.slug}]]: {page.title}",
            "page": page.model_dump(mode="json", by_alias=True),
        }
    listed = svc.list_wiki(resolved_scope)
    return {
        "ok": True,
        "scope": listed.scope,
        "pages": [p.model_dump(mode="json", by_alias=True) for p in listed.data],
        "summary": f"Found {len(listed.data)} wiki page(s) in {listed.scope}.",
    }


@registry.register(
    name="capy.distill_session",
    description="Distill a Sandwalk chat session into durable Memory notes, a Living Wiki page, and Knowledge Graph claims.",
    category="capy",
    usage_guide="Use when the user asks to save, distill, or extract learnings from a session into Memory/Wiki/Graph.",
    parameters={
        "session_id": "Chat session id to distill.",
        "scope": "Optional target scope ('global', 'project:<id>', or 'specialist:<id>').",
    },
)
def capy_distill_session(session_id: str = "", scope: str = "", **kwargs) -> dict:
    from agent_server.memory_service import MemoryService

    deps = _deps()
    sid = str(session_id or "").strip()
    if not sid:
        return {"ok": False, "summary": "session_id is required."}
    svc = MemoryService(agent_store=deps.store)
    try:
        res = svc.distill_session(sid, scope=str(scope or "").strip() or None)
        return res.model_dump(mode="json", by_alias=True)
    except KeyError:
        return {"ok": False, "summary": f"Session not found: {sid}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": f"Distillation failed: {exc}"}


@registry.register(
    name="capy.create_skill_from_memory",
    description=(
        "Crystallize curated Memories, Living Wiki pages, and Omnigraph Cookbook ontologies "
        "from a scope into a reusable Sandwalk Skill (~/.sandwalk/skills/<slug>/SKILL.md)."
    ),
    category="capy",
    usage_guide=(
        "Use when the user asks to convert what we know about a topic, a Living Wiki page, "
        "or an Omnigraph Cookbook ontology into an installed Skill (/skill-slug)."
    ),
    parameters={
        "name": "Skill title or slug (e.g. 'Oral GLP-1R Discovery').",
        "scope": "Source scope ('global', 'project:<id>', or 'specialist:<id>').",
        "topic": "Optional topic filter.",
        "wiki_slug": "Optional specific Wiki page slug.",
        "description": "Optional 1-sentence skill description.",
    },
)
def capy_create_skill_from_memory(
    name: str = "",
    scope: str = "global",
    topic: str = "",
    wiki_slug: str = "",
    description: str = "",
    **kwargs,
) -> dict:
    from agent_server.memory_service import MemoryService
    from agent_server.models.memory import CreateSkillFromMemoryRequest

    clean_name = str(name or "").strip()
    if not clean_name:
        return {"ok": False, "summary": "name is required to create a skill."}
    deps = _deps()
    svc = MemoryService(agent_store=deps.store)
    res = svc.create_skill(
        CreateSkillFromMemoryRequest(
            scope=str(scope or "global").strip() or "global",
            name=clean_name,
            description=str(description or "").strip() or None,
            topic=str(topic or "").strip() or None,
            wiki_slug=str(wiki_slug or "").strip() or None,
        )
    )
    return res.model_dump(mode="json", by_alias=True)


@registry.register(
    name="capy.memory_manage",
    description=(
        "Manage Sandwalk's Memory (USER.md / MEMORY.md), Living Wiki pages, "
        "Knowledge Graph nodes/claims, or active Cookbook Mode (01-06)."
    ),
    category="capy",
    usage_guide=(
        "Use when the user asks Capy to remember a preference or rule, write/update a Wiki page, "
        "record a Knowledge Graph claim, or switch Cookbook mode (industry-intel, pharma-intel, "
        "context-graph, vc-os, biomed-research, second-brain)."
    ),
    parameters={
        "operation": (
            "'add_memory', 'add_user_memory', 'remove_memory', 'write_wiki', "
            "'record_claim', or 'select_cookbook'"
        ),
        "scope": "Target scope ('global', 'project:<id>', or 'specialist:<id>').",
        "content": "Memory text, Wiki Markdown content, or claim summary.",
        "title": "Wiki page title or Graph subject name.",
        "slug": "Wiki page slug or Cookbook ID (for select_cookbook).",
        "predicate": "Graph claim predicate (e.g. 'Supports', 'Contradicts') when operation='record_claim'.",
        "target": "Graph claim object (e.g. 'Goal:local-first') when operation='record_claim'.",
        "polarity": "'support', 'contradict', or 'neutral' when operation='record_claim'.",
    },
)
def capy_memory_manage(
    operation: str = "add_memory",
    scope: str = "global",
    content: str = "",
    title: str = "",
    slug: str = "",
    predicate: str = "Supports",
    target: str = "",
    polarity: str = "support",
    **kwargs,
) -> dict:
    from agent_server.memory_service import MemoryService
    from agent_server.models.memory import (
        CreateGraphClaimRequest,
        UpsertWikiPageRequest,
    )

    deps = _deps()
    svc = MemoryService(agent_store=deps.store)
    op = str(operation or "add_memory").strip().lower()
    resolved_scope = str(scope or "global").strip() or "global"

    if op in {"add_memory", "add_user_memory"}:
        tgt = "user" if op == "add_user_memory" else "memory"
        res = svc.store.mutate_by_substring(
            scope="user" if tgt == "user" else resolved_scope,
            target=tgt,
            action="add",
            content=content,
            bypass_approval=True,
        )
        return {"summary": f"Saved entry to {tgt.upper()}.md ({resolved_scope}).", **res}
    if op == "remove_memory":
        res = svc.store.mutate_by_substring(
            scope=resolved_scope,
            target="memory",
            action="remove",
            old_text=content or title,
            bypass_approval=True,
        )
        return {"summary": f"Removed memory matching '{content or title}'.", **res}
    if op == "write_wiki":
        page_slug = str(slug or title or "note").strip()
        page_title = str(title or slug or "Wiki Note").strip()
        page = svc.write_wiki_page(
            page_slug,
            UpsertWikiPageRequest(
                scope=resolved_scope,
                title=page_title,
                content=content,
            ),
        )
        return {
            "ok": True,
            "summary": f"Saved Living Wiki page [[{page.slug}]] ({page.title}).",
            "page": page.model_dump(mode="json", by_alias=True),
        }
    if op == "record_claim":
        edge = svc.record_graph_claim(
            CreateGraphClaimRequest(
                scope=resolved_scope,
                subject_id=title or slug or "Entity:subject",
                predicate=predicate or "Supports",
                object_id=target or "Claim:object",
                polarity=polarity if polarity in {"support", "contradict", "neutral"} else "support",  # type: ignore[arg-type]
                summary=content,
            )
        )
        return {
            "ok": True,
            "summary": f"Recorded graph claim {edge.source_id} -[{edge.predicate}]-> {edge.target_id}.",
            "edge": edge.model_dump(mode="json", by_alias=True),
        }
    if op == "select_cookbook":
        cb_id = str(slug or content or "second-brain").strip()
        snap = svc.select_cookbook(scope=resolved_scope, cookbook_id=cb_id, load_demo_seed=True)
        return {
            "ok": True,
            "summary": f"Switched {resolved_scope} to Cookbook {snap.active_cookbook.number} {snap.active_cookbook.name}.",
            "cookbookId": snap.active_cookbook.id,
        }
    return {"ok": False, "summary": f"Unsupported memory_manage operation: {operation}"}



