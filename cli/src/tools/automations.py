"""Agent tools for Automations (Cron & Event Schedules) and Remote-SSH / Slurm Management."""

from __future__ import annotations

import asyncio
from typing import Any

from tools import registry


def _automations_service() -> Any:
    from agent_server.automations_service import AutomationsService
    from agent_server.ssh_service import SshService
    from agent_server.store import AgentStore

    store = AgentStore()
    ssh_svc = SshService(store)
    return AutomationsService(store, ssh_service=ssh_svc)


def _ssh_service() -> Any:
    from agent_server.ssh_service import SshService
    from agent_server.store import AgentStore

    return SshService(AgentStore())


@registry.register(
    name="ops.automation_manage",
    description=(
        "Create, list, update, pause, resume, run, complete, snooze, unsnooze, or remove "
        "scheduled automations (cron jobs, intervals, one-shot follow-ups, and SSH/Slurm watchers)."
    ),
    category="ops",
    parameters={
        "action": (
            "Operation: 'create', 'list', 'get', 'update', 'pause', 'resume', 'run', "
            "'complete', 'remove', 'snooze', 'unsnooze', or 'templates'"
        ),
        "automation_id": "Automation ID or name (for get/update/pause/resume/run/complete/remove)",
        "name": "Human-readable name for the automation",
        "schedule": (
            "Schedule expression: 'every 15m', 'every 2h', 'in 30m', 'daily at 9am', "
            "'weekdays at 8:30am', '0 9 * * 1-5', or 'webhook'"
        ),
        "prompt": "Agent instructions to execute on each scheduled fire",
        "command": "Optional shell/Slurm command to run (or sole command when session_mode='no_agent')",
        "session_mode": "'fresh' (new session per run), 'continue' (same thread), or 'no_agent' (zero-token script)",
        "session_id": "Origin session ID for 'continue' mode or 'snooze'/'unsnooze'",
        "specialist_id": "Optional Specialist ID or slug to run the automation as",
        "ssh_host": "Optional SSH host ID, alias, or user@host target for remote execution",
        "remote_workdir": "Optional shared workspace folder on the remote SSH server",
        "workdir": "Optional local working directory path",
        "skills": "Optional comma-separated skill names to attach (e.g. 'ssh,omnigraph')",
        "continuity": "Boolean: inject previous run's output into next run to avoid duplicate reports",
        "context_from": "Optional comma-separated upstream automation IDs for multi-stage pipelines",
        "wake_on_change_only": "Boolean: when command is set, only wake LLM when stdout changes",
        "template_id": "Optional starter template ID (e.g. 'watch-slurm-queue', 'boltz-structure-digest')",
    },
    usage_guide=(
        "Use `automation.manage` whenever the user asks to schedule a recurring task, set a reminder "
        "or follow-up in 30m/2d, watch a long-running Slurm/HPC job, or manage existing cron jobs."
    ),
)
def automation_manage(
    action: str = "list",
    automation_id: str = "",
    name: str = "",
    schedule: str = "every 1h",
    prompt: str = "",
    command: str = "",
    session_mode: str = "fresh",
    session_id: str = "",
    specialist_id: str = "",
    ssh_host: str = "",
    remote_workdir: str = "",
    workdir: str = "",
    skills: str = "",
    continuity: bool = False,
    context_from: str = "",
    wake_on_change_only: bool = False,
    template_id: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    from agent_server.models.automations import (
        CreateAutomationRequest,
        UpdateAutomationRequest,
    )

    act = (action or "list").strip().lower()
    svc = _automations_service()

    if act == "templates":
        tpls = svc.list_templates()
        return {
            "ok": True,
            "summary": f"Available {len(tpls)} automation starter template(s).",
            "templates": [t.model_dump(mode="json", by_alias=True) for t in tpls],
        }

    if act == "list":
        items = svc.list_automations()
        return {
            "ok": True,
            "summary": f"Found {len(items)} automation(s).",
            "count": len(items),
            "automations": [a.model_dump(mode="json", by_alias=True) for a in items],
        }

    if act == "get":
        item = svc.get_automation(automation_id or name)
        if item is None:
            return {"ok": False, "summary": f"Automation '{automation_id or name}' not found."}
        runs = svc.list_runs(automation_id=item.id, limit=10)
        return {
            "ok": True,
            "summary": f"Automation '{item.name}' ({item.schedule_label}, status={item.last_status}).",
            "automation": item.model_dump(mode="json", by_alias=True),
            "recentRuns": [r.model_dump(mode="json", by_alias=True) for r in runs],
        }

    if act in {"snooze", "unsnooze"}:
        target_sid = session_id.strip()
        if not target_sid and automation_id:
            found = svc.get_automation(automation_id)
            if found and found.origin_session_id:
                target_sid = found.origin_session_id
        if not target_sid:
            return {"ok": False, "summary": "Provide session_id or automation_id to snooze/unsnooze."}
        snooze_flag = act == "snooze"
        updated = svc.store.update_session(target_sid, snoozed=snooze_flag)
        if updated is None:
            return {"ok": False, "summary": f"Session '{target_sid}' not found."}
        state_word = "snoozed" if snooze_flag else "unsnoozed"
        return {
            "ok": True,
            "summary": f"Session '{updated.title}' is now {state_word}.",
            "sessionId": updated.id,
            "snoozed": updated.snoozed,
        }

    if act == "create":
        skill_list = [s.strip() for s in str(skills or "").split(",") if s.strip()]
        ctx_list = [c.strip() for c in str(context_from or "").split(",") if c.strip()]
        resolved_ssh_id: str | None = None
        if ssh_host and ssh_host.strip():
            host_obj = svc.ssh_service.resolve_or_create_host(ssh_host.strip())
            resolved_ssh_id = host_obj.id

        resolved_spec_id: str | None = None
        if specialist_id and specialist_id.strip():
            needle = specialist_id.strip().lower()
            for sp in svc.store.list_specialists():
                if sp.id.lower() == needle or sp.slug.lower() == needle or sp.name.lower() == needle:
                    resolved_spec_id = sp.id
                    break

        mode_val = session_mode if session_mode in {"fresh", "continue", "no_agent"} else "fresh"
        if session_id and mode_val == "fresh" and not kwargs.get("explicit_mode"):
            mode_val = "continue"

        created = svc.create_automation(
            CreateAutomationRequest(
                name=name or None,
                prompt=prompt,
                command=command or None,
                schedule_expr=schedule or "every 1h",
                session_mode=mode_val,  # type: ignore[arg-type]
                origin_session_id=session_id or None,
                specialist_id=resolved_spec_id,
                workdir=workdir or None,
                ssh_host_id=resolved_ssh_id,
                remote_workdir=remote_workdir or None,
                skill_names=skill_list,
                continuity=bool(continuity),
                context_from=ctx_list,
                wake_on_change_only=bool(wake_on_change_only),
                template_id=template_id or None,
            )
        )
        return {
            "ok": True,
            "summary": f"Created automation '{created.name}' ({created.schedule_label}).",
            "automation": created.model_dump(mode="json", by_alias=True),
        }

    if act == "update":
        target = automation_id or name
        skill_list = (
            [s.strip() for s in str(skills).split(",") if s.strip()]
            if skills
            else None
        )
        ctx_list = (
            [c.strip() for c in str(context_from).split(",") if c.strip()]
            if context_from
            else None
        )
        updated = svc.update_automation(
            target,
            UpdateAutomationRequest(
                name=name or None,
                prompt=prompt or None,
                command=command or None,
                schedule_expr=schedule if schedule != "every 1h" or "schedule" in kwargs else None,
                session_mode=session_mode if session_mode in {"fresh", "continue", "no_agent"} else None,  # type: ignore[arg-type]
                workdir=workdir or None,
                remote_workdir=remote_workdir or None,
                skill_names=skill_list,
                continuity=continuity if "continuity" in kwargs else None,
                context_from=ctx_list,
            ),
        )
        if updated is None:
            return {"ok": False, "summary": f"Automation '{target}' not found."}
        return {
            "ok": True,
            "summary": f"Updated automation '{updated.name}' ({updated.schedule_label}).",
            "automation": updated.model_dump(mode="json", by_alias=True),
        }

    if act == "pause":
        updated = svc.pause_automation(automation_id or name)
        if updated is None:
            return {"ok": False, "summary": f"Automation '{automation_id or name}' not found."}
        return {
            "ok": True,
            "summary": f"Paused automation '{updated.name}'.",
            "automation": updated.model_dump(mode="json", by_alias=True),
        }

    if act == "resume":
        updated = svc.resume_automation(automation_id or name)
        if updated is None:
            return {"ok": False, "summary": f"Automation '{automation_id or name}' not found."}
        return {
            "ok": True,
            "summary": f"Resumed automation '{updated.name}' (next run: {updated.next_run_at}).",
            "automation": updated.model_dump(mode="json", by_alias=True),
        }

    if act == "complete":
        updated = svc.complete_automation(automation_id or name)
        if updated is None:
            return {"ok": False, "summary": f"Automation '{automation_id or name}' not found."}
        return {
            "ok": True,
            "summary": f"Marked automation '{updated.name}' completed.",
            "automation": updated.model_dump(mode="json", by_alias=True),
        }

    if act == "remove":
        deleted = svc.delete_automation(automation_id or name)
        if not deleted:
            return {"ok": False, "summary": f"Automation '{automation_id or name}' not found."}
        return {"ok": True, "summary": f"Removed automation '{automation_id or name}'."}

    if act == "run":
        target = automation_id or name
        try:
            run = asyncio.run(
                svc.trigger_automation(
                    target,
                    trigger_source="agent_tool",
                    transient_context=prompt or None,
                    wait=True,
                )
            )
            return {
                "ok": True,
                "summary": f"Triggered automation '{target}' (status={run.status}).",
                "run": run.model_dump(mode="json", by_alias=True),
            }
        except Exception as exc:
            return {"ok": False, "summary": f"Failed to run automation '{target}': {exc}"}

    return {"ok": False, "summary": f"Unknown automation action: {act!r}"}


# --- SSH Manager & Remote Execution Tools ---


@registry.register(
    name="ssh.hosts",
    description=(
        "List, add, probe, or remove SSH hosts (including ~/.ssh/config entries, Linux/HPC "
        "servers, and Slurm clusters)."
    ),
    category="ssh",
    parameters={
        "action": "Operation: 'list', 'add', 'probe', or 'remove'",
        "target": "SSH host alias, ID, or connection string (e.g. 'user@hpc.edu -p 22')",
        "alias": "Optional friendly alias when adding a host",
        "default_workdir": "Optional default remote workspace folder (e.g. '/scratch/user/project')",
    },
    usage_guide="Use to inspect configured SSH machines or register/probe a remote Linux/HPC server.",
)
def ssh_hosts_tool(
    action: str = "list",
    target: str = "",
    alias: str = "",
    default_workdir: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    from agent_server.models.automations import CreateSshHostRequest

    svc = _ssh_service()
    act = (action or "list").strip().lower()
    if act == "list":
        hosts = svc.list_hosts(include_ssh_config=True)
        return {
            "ok": True,
            "summary": f"Found {len(hosts)} SSH host(s).",
            "hosts": [h.model_dump(mode="json", by_alias=True) for h in hosts],
        }
    if act == "add":
        if not target.strip():
            return {"ok": False, "summary": "Provide target='user@host' to add an SSH host."}
        host = svc.create_host(
            CreateSshHostRequest(
                target=target.strip(),
                alias=alias.strip() or None,
                default_workdir=default_workdir.strip() or None,
            )
        )
        return {
            "ok": True,
            "summary": f"Saved SSH host '{host.alias}' ({host.host}).",
            "host": host.model_dump(mode="json", by_alias=True),
        }
    if act == "probe":
        if not target.strip():
            return {"ok": False, "summary": "Provide target host alias or user@host to probe."}
        probe = svc.probe_host(target.strip())
        return {
            "ok": probe.reachable,
            "summary": (
                f"Host {probe.hostname or target} reachable ({probe.platform} {probe.arch}, "
                f"slurm={probe.slurm_available}, sandwalk={probe.sandwalk_installed})."
                if probe.reachable
                else f"Host {target} unreachable: {probe.detail}"
            ),
            "probe": probe.model_dump(mode="json", by_alias=True),
        }
    if act == "remove":
        deleted = svc.delete_host(target.strip() or alias.strip())
        return {
            "ok": deleted,
            "summary": (
                f"Removed SSH host '{target or alias}'."
                if deleted
                else f"SSH host '{target or alias}' not found."
            ),
        }
    return {"ok": False, "summary": f"Unknown ssh.hosts action: {act!r}"}


@registry.register(
    name="ssh.exec",
    description="Execute a command on a remote SSH server or HPC/Slurm login node.",
    category="ssh",
    parameters={
        "host": "SSH host alias, ID, or 'user@host'",
        "command": "Shell command to execute on the remote machine",
        "workdir": "Optional remote working directory (defaults to host's default_workdir)",
        "timeout_seconds": "Timeout in seconds (default 60)",
    },
    usage_guide=(
        "Use to run commands on a remote Linux/macOS/HPC server over SSH (e.g. `sbatch`, "
        "`squeue`, `nvidia-smi`, checking logs, or managing remote workspaces)."
    ),
)
def ssh_exec_tool(
    host: str,
    command: str,
    workdir: str = "",
    timeout_seconds: float = 60.0,
    **kwargs: Any,
) -> dict[str, Any]:
    svc = _ssh_service()
    res = svc.exec_command(
        host,
        command,
        workdir=workdir.strip() or None,
        timeout_seconds=float(timeout_seconds or 60.0),
    )
    return {
        "ok": res.exit_code == 0,
        "summary": f"Remote command on {host} exited with {res.exit_code} in {res.duration_seconds}s.",
        **res.model_dump(mode="json", by_alias=True),
    }


@registry.register(
    name="ssh.sync",
    description="Sync files or directories between local workspace and remote SSH server via rsync.",
    category="ssh",
    parameters={
        "host": "SSH host alias, ID, or 'user@host'",
        "local_path": "Local file or directory path",
        "remote_path": "Remote file or directory path on the SSH server",
        "direction": "'push' (local -> remote, default) or 'pull' (remote -> local)",
    },
    usage_guide="Use to stage scripts/configs to an HPC workspace or pull Slurm results back locally.",
)
def ssh_sync_tool(
    host: str,
    local_path: str,
    remote_path: str,
    direction: str = "push",
    **kwargs: Any,
) -> dict[str, Any]:
    svc = _ssh_service()
    res = svc.sync_files(
        host,
        local_path=local_path,
        remote_path=remote_path,
        direction=direction,
    )
    return {
        "ok": res.exit_code == 0,
        "summary": res.summary,
        **res.model_dump(mode="json", by_alias=True),
    }


@registry.register(
    name="ssh.slurm_status",
    description="Inspect active Slurm queue jobs (squeue) on a remote HPC cluster over SSH.",
    category="ssh",
    parameters={
        "host": "SSH host alias, ID, or 'user@host'",
    },
    usage_guide="Use to check running/pending Slurm jobs on a university or research cluster.",
)
def ssh_slurm_status_tool(host: str, **kwargs: Any) -> dict[str, Any]:
    svc = _ssh_service()
    res = svc.get_slurm_status(host)
    return {
        "ok": True,
        "summary": (
            f"Found {len(res.jobs)} active Slurm job(s) on {host}."
            if res.slurm_available
            else f"Slurm (squeue) not detected on {host}."
        ),
        **res.model_dump(mode="json", by_alias=True),
    }


@registry.register(
    name="ssh.bootstrap_remote",
    description=(
        "Auto-install Sandwalk on a remote SSH machine, start its persistent background "
        "daemon (survives SSH disconnect), and open a local SSH tunnel."
    ),
    category="ssh",
    parameters={
        "host": "SSH host alias, ID, or 'user@host'",
        "default_workdir": "Optional remote workspace folder path",
        "open_tunnel": "Boolean: open local SSH port-forward tunnel (default True)",
    },
    usage_guide=(
        "Use when the user asks to install Sandwalk on a remote SSH server, start the remote "
        "daemon so automations keep running 24/7, or connect a remote window."
    ),
)
def ssh_bootstrap_remote_tool(
    host: str,
    default_workdir: str = "",
    open_tunnel: bool = True,
    **kwargs: Any,
) -> dict[str, Any]:
    from agent_server.models.automations import SshConnectRequest

    svc = _ssh_service()
    res = svc.connect_and_bootstrap(
        SshConnectRequest(
            host_id_or_target=host,
            auto_install=True,
            start_daemon=True,
            open_tunnel=bool(open_tunnel),
            enable_watchdog=True,
            default_workdir=default_workdir.strip() or None,
        )
    )
    return {
        "ok": bool(res.local_url or res.host.daemon_running),
        "summary": (
            f"Bootstrapped {res.hostname} ({res.daemon_persistence}) → {res.local_url or 'daemon active'}."
        ),
        **res.model_dump(mode="json", by_alias=True),
    }
