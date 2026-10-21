"""Automations & Scheduled Workflows Service (Hybrid Amp + Hermes + Cursor model)."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from agent import config as agent_config
from agent_server.automations_service.schedule_parser import (
    compute_next_run,
    parse_schedule,
)
from agent_server.automations_service.templates import (
    get_automation_template,
    list_automation_templates,
)
from agent_server.models.automations import (
    Automation,
    AutomationRun,
    AutomationTemplate,
    CreateAutomationRequest,
    UpdateAutomationRequest,
)
from agent_server.store import AgentStore, utc_now

logger = logging.getLogger("agent_server.automations")


def automations_output_dir(automation_id: str | None = None) -> Path:
    base = (agent_config.CONFIG_DIR / "automations" / "output").expanduser()
    if automation_id:
        base = base / automation_id
    base.mkdir(parents=True, exist_ok=True)
    return base


class AutomationsService:
    """Manages CRUD, schedule ticks, missed-run catch-up, and Hybrid execution."""

    def __init__(
        self,
        store: AgentStore,
        agent_service: Any | None = None,
        ssh_service: Any | None = None,
    ) -> None:
        self.store = store
        self.agent_service = agent_service
        self.ssh_service = ssh_service
        self._running_automation_ids: set[str] = set()
        self._ticker_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    def list_templates(self) -> list[AutomationTemplate]:
        return list_automation_templates()

    def list_automations(self) -> list[Automation]:
        return self.store.list_automations()

    def get_automation(self, id_or_name: str) -> Automation | None:
        return self.store.get_automation(id_or_name)

    def list_runs(
        self,
        *,
        automation_id: str | None = None,
        limit: int = 50,
    ) -> list[AutomationRun]:
        if automation_id:
            found = self.store.get_automation(automation_id)
            if found is not None:
                automation_id = found.id
        return self.store.list_automation_runs(
            automation_id=automation_id, limit=limit
        )

    def create_automation(self, req: CreateAutomationRequest) -> Automation:
        tpl = get_automation_template(req.template_id) if req.template_id else None
        schedule_expr = (
            req.schedule_expr.strip()
            if req.schedule_expr and req.schedule_expr.strip()
            else (tpl.schedule_expr if tpl else "every 1h")
        )
        parsed = parse_schedule(schedule_expr)
        next_run = compute_next_run(schedule_expr) if req.enabled else None

        name = (req.name or "").strip()
        if not name:
            if tpl is not None:
                name = tpl.name
            elif req.prompt.strip():
                first_line = req.prompt.strip().splitlines()[0][:64].strip()
                name = first_line or "Scheduled automation"
            elif req.command and req.command.strip():
                name = f"Script: {req.command.strip()[:48]}"
            else:
                name = "Untitled automation"

        specialist_id = req.specialist_id
        if not specialist_id and tpl and tpl.recommended_specialist_slug:
            for spec in self.store.list_specialists():
                if spec.slug == tpl.recommended_specialist_slug:
                    specialist_id = spec.id
                    break

        repeat_limit = req.repeat_limit
        if repeat_limit is None and parsed.kind == "once":
            repeat_limit = 1

        return self.store.create_automation(
            name=name,
            description=req.description or (tpl.description if tpl else None),
            prompt=req.prompt or (tpl.prompt if tpl else ""),
            command=req.command if req.command is not None else (tpl.command if tpl else None),
            schedule_expr=parsed.expr,
            schedule_kind=parsed.kind,
            schedule_label=parsed.label,
            session_mode=req.session_mode or (tpl.session_mode if tpl else "fresh"),
            origin_session_id=req.origin_session_id,
            specialist_id=specialist_id,
            project_id=req.project_id,
            workdir=req.workdir,
            ssh_host_id=req.ssh_host_id,
            remote_workdir=req.remote_workdir,
            skill_names=req.skill_names or (tpl.skill_names if tpl else []),
            tool_names=req.tool_names or (tpl.tool_names if tpl else []),
            mcp_server_ids=req.mcp_server_ids,
            provider_pin=req.provider_pin,
            model_pin=req.model_pin,
            continuity=req.continuity or (tpl.continuity if tpl else False),
            context_from=req.context_from,
            wake_on_change_only=req.wake_on_change_only
            or (tpl.wake_on_change_only if tpl else False),
            repeat_limit=repeat_limit,
            enabled=req.enabled,
            next_run_at=next_run,
            template_id=req.template_id,
        )

    def update_automation(
        self,
        id_or_name: str,
        req: UpdateAutomationRequest,
    ) -> Automation | None:
        current = self.store.get_automation(id_or_name)
        if current is None:
            return None
        updates: dict[str, Any] = {}
        if req.name is not None:
            updates["name"] = req.name.strip() or current.name
        if req.description is not None:
            updates["description"] = req.description
        if req.prompt is not None:
            updates["prompt"] = req.prompt
        if req.clear_command:
            updates["command"] = None
        elif req.command is not None:
            updates["command"] = req.command
        if req.session_mode is not None:
            updates["session_mode"] = req.session_mode
        if req.clear_origin_session_id:
            updates["origin_session_id"] = None
        elif req.origin_session_id is not None:
            updates["origin_session_id"] = req.origin_session_id
        if req.clear_specialist_id:
            updates["specialist_id"] = None
        elif req.specialist_id is not None:
            updates["specialist_id"] = req.specialist_id
        if req.clear_project_id:
            updates["project_id"] = None
        elif req.project_id is not None:
            updates["project_id"] = req.project_id
        if req.clear_workdir:
            updates["workdir"] = None
        elif req.workdir is not None:
            updates["workdir"] = req.workdir
        if req.clear_ssh_host_id:
            updates["ssh_host_id"] = None
        elif req.ssh_host_id is not None:
            updates["ssh_host_id"] = req.ssh_host_id
        if req.clear_remote_workdir:
            updates["remote_workdir"] = None
        elif req.remote_workdir is not None:
            updates["remote_workdir"] = req.remote_workdir
        if req.skill_names is not None:
            updates["skill_names"] = req.skill_names
        if req.tool_names is not None:
            updates["tool_names"] = req.tool_names
        if req.mcp_server_ids is not None:
            updates["mcp_server_ids"] = req.mcp_server_ids
        if req.clear_model_pin:
            updates["provider_pin"] = None
            updates["model_pin"] = None
        else:
            if req.provider_pin is not None:
                updates["provider_pin"] = req.provider_pin
            if req.model_pin is not None:
                updates["model_pin"] = req.model_pin
        if req.continuity is not None:
            updates["continuity"] = req.continuity
        if req.context_from is not None:
            updates["context_from"] = req.context_from
        if req.wake_on_change_only is not None:
            updates["wake_on_change_only"] = req.wake_on_change_only
        if req.clear_repeat_limit:
            updates["repeat_limit"] = None
        elif req.repeat_limit is not None:
            updates["repeat_limit"] = req.repeat_limit

        next_enabled = current.enabled if req.enabled is None else req.enabled
        if req.enabled is not None:
            updates["enabled"] = req.enabled
            if not req.enabled:
                updates["last_status"] = "paused"
                updates["next_run_at"] = None
            elif current.last_status == "paused":
                updates["last_status"] = "idle"

        next_expr = req.schedule_expr if req.schedule_expr is not None else current.schedule_expr
        if req.schedule_expr is not None or (req.enabled is True and current.next_run_at is None):
            parsed = parse_schedule(next_expr)
            updates["schedule_expr"] = parsed.expr
            updates["schedule_kind"] = parsed.kind
            updates["schedule_label"] = parsed.label
            if next_enabled:
                updates["next_run_at"] = compute_next_run(parsed.expr)

        return self.store.update_automation_fields(current.id, **updates)

    def pause_automation(self, id_or_name: str) -> Automation | None:
        return self.update_automation(
            id_or_name, UpdateAutomationRequest(enabled=False)
        )

    def resume_automation(self, id_or_name: str) -> Automation | None:
        return self.update_automation(
            id_or_name, UpdateAutomationRequest(enabled=True)
        )

    def complete_automation(self, id_or_name: str) -> Automation | None:
        current = self.store.get_automation(id_or_name)
        if current is None:
            return None
        if current.origin_session_id:
            try:
                self.store.update_session(
                    current.origin_session_id, snoozed=False
                )
            except Exception:
                pass
        return self.store.update_automation_fields(
            current.id,
            enabled=False,
            next_run_at=None,
            last_status="completed",
        )

    def delete_automation(self, id_or_name: str) -> bool:
        return self.store.delete_automation(id_or_name)

    # --- Output Continuity & Context Chaining ---

    def read_latest_output(self, automation_id: str) -> str | None:
        out_dir = automations_output_dir(automation_id)
        latest = out_dir / "latest.md"
        if latest.exists():
            try:
                text = latest.read_text(encoding="utf-8").strip()
                if text:
                    return text
            except Exception:
                pass
        return None

    def write_run_output(
        self,
        automation_id: str,
        run_id: str,
        content: str,
    ) -> Path:
        out_dir = automations_output_dir(automation_id)
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_file = out_dir / f"{ts}-{run_id[:8]}.md"
        cleaned = (content or "").strip()
        run_file.write_text(cleaned + "\n", encoding="utf-8")
        if cleaned and cleaned.lower() != "no_change":
            (out_dir / "latest.md").write_text(cleaned + "\n", encoding="utf-8")
        return run_file

    def _compose_effective_prompt(
        self,
        automation: Automation,
        *,
        transient_context: str | None = None,
        pre_command_output: str | None = None,
    ) -> str:
        sections: list[str] = []

        # 1. Upstream context_from chaining (Hermes style)
        if automation.context_from:
            upstream_blocks: list[str] = []
            for up_id in automation.context_from:
                up = self.store.get_automation(up_id)
                label = f"{up.name} ({up.id})" if up else up_id
                out = self.read_latest_output(up.id if up else up_id)
                if out:
                    upstream_blocks.append(f"### Upstream Job: {label}\n{out[:4000]}")
            if upstream_blocks:
                sections.append(
                    "## Upstream Automation Context\n" + "\n\n".join(upstream_blocks)
                )

        # 2. Self-continuity (Hermes continuity=True)
        if automation.continuity:
            prev = self.read_latest_output(automation.id)
            if prev:
                sections.append(
                    "## Previous Run Output (Continuity)\n"
                    "Avoid repeating items already reported in your previous run unless their status changed:\n\n"
                    f"{prev[:4000]}"
                )

        # 3. Pre-command / SSH probe output if attached
        if pre_command_output:
            sections.append(
                f"## Scheduled Command Output (`{automation.command}`)\n```\n{pre_command_output[:6000]}\n```"
            )

        # 4. Core task instructions
        base_prompt = automation.prompt.strip()
        if not base_prompt and automation.command:
            base_prompt = f"Analyze the output of `{automation.command}` above and report any actionable findings."
        sections.append(f"## Scheduled Automation Task ({automation.name})\n{base_prompt}")

        # 5. Attached skills hint
        if automation.skill_names:
            skills_str = ", ".join(f"/{s.lstrip('/')}" for s in automation.skill_names)
            sections.append(f"Preferred skills for this automation: {skills_str}")

        # 6. Transient run context
        if transient_context and transient_context.strip():
            sections.append(f"## Run Context\n{transient_context.strip()}")

        return "\n\n".join(sections)

    def _execute_command_target(
        self,
        automation: Automation,
    ) -> tuple[int, str, str]:
        cmd = (automation.command or "").strip()
        if not cmd:
            return 0, "", ""
        if automation.ssh_host_id and self.ssh_service is not None:
            res = self.ssh_service.exec_command(
                automation.ssh_host_id,
                cmd,
                workdir=automation.remote_workdir or automation.workdir,
                timeout_seconds=120.0,
            )
            return res.exit_code, res.stdout, res.stderr

        cwd = automation.workdir or str(Path.home())
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd if Path(cwd).exists() else None,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return proc.returncode, proc.stdout or "", proc.stderr or ""
        except Exception as exc:
            return 1, "", str(exc)

    # --- Execution Engine ---

    async def trigger_automation(
        self,
        id_or_name: str,
        *,
        trigger_source: str = "manual",
        transient_context: str | None = None,
        was_catchup: bool = False,
        wait: bool = True,
    ) -> AutomationRun:
        automation = self.store.get_automation(id_or_name)
        if automation is None:
            raise KeyError(f"Automation not found: {id_or_name}")
        if automation.id in self._running_automation_ids:
            raise RuntimeError(f"Automation '{automation.name}' is already running.")

        self._running_automation_ids.add(automation.id)
        run = self.store.create_automation_run(
            automation_id=automation.id,
            session_id=automation.origin_session_id
            if automation.session_mode == "continue"
            else None,
            status="running",
            trigger_source=trigger_source,
            was_catchup=was_catchup,
        )
        now = utc_now()
        self.store.update_automation_fields(
            automation.id,
            last_run_at=now,
            last_status="running",
            last_error=None,
        )

        if wait:
            return await self._run_automation_job(
                automation,
                run,
                transient_context=transient_context,
            )

        asyncio.create_task(
            self._run_automation_job(
                automation,
                run,
                transient_context=transient_context,
            )
        )
        return run

    async def _run_automation_job(
        self,
        automation: Automation,
        run: AutomationRun,
        *,
        transient_context: str | None = None,
    ) -> AutomationRun:
        try:
            pre_output = ""
            if automation.command and automation.command.strip():
                code, out, err = await asyncio.to_thread(
                    self._execute_command_target, automation
                )
                combined = (out + ("\n" + err if err else "")).strip()
                pre_output = combined
                prev_out = self.read_latest_output(automation.id)

                # If wake_on_change_only is set and stdout matches previous run, skip LLM call!
                if (
                    automation.wake_on_change_only
                    and code == 0
                    and prev_out is not None
                    and combined == prev_out.strip()
                ):
                    self._advance_schedule_after_run(automation, succeeded=True)
                    finished = self.store.finish_automation_run(
                        run.id,
                        status="skipped",
                        output_excerpt="No change since previous run (wake_on_change_only).",
                    )
                    return finished or run

                # Mode C: no_agent script mode — zero LLM tokens
                if automation.session_mode == "no_agent":
                    out_file = self.write_run_output(
                        automation.id, run.id, combined or "(empty output)"
                    )
                    status = "succeeded" if code == 0 else "failed"
                    err_msg = (
                        f"Command exited with code {code}: {err[:300]}"
                        if code != 0
                        else None
                    )
                    self._advance_schedule_after_run(
                        automation, succeeded=(code == 0), error=err_msg
                    )
                    finished = self.store.finish_automation_run(
                        run.id,
                        status=status,
                        output_excerpt=(combined or err or "")[:500],
                        output_path=str(out_file),
                        error=err_msg,
                    )
                    return finished or run

            # Modes A (`continue`) & B (`fresh`): Agent-backed run
            effective_prompt = self._compose_effective_prompt(
                automation,
                transient_context=transient_context,
                pre_command_output=pre_output or None,
            )

            session_id = self._resolve_or_create_run_session(automation)
            output_text = await self._dispatch_agent_session_run(
                session_id,
                effective_prompt,
            )
            out_file = self.write_run_output(
                automation.id, run.id, output_text or "(completed)"
            )
            self._advance_schedule_after_run(automation, succeeded=True)
            finished = self.store.finish_automation_run(
                run.id,
                status="succeeded",
                session_id=session_id,
                output_excerpt=(output_text or "")[:500],
                output_path=str(out_file),
            )
            return finished or run
        except Exception as exc:
            logger.warning(
                "Automation '%s' failed: %s", automation.name, exc, exc_info=True
            )
            err_str = str(exc)[:500]
            self._advance_schedule_after_run(
                automation, succeeded=False, error=err_str
            )
            finished = self.store.finish_automation_run(
                run.id,
                status="failed",
                error=err_str,
            )
            return finished or run
        finally:
            self._running_automation_ids.discard(automation.id)

    def _resolve_or_create_run_session(self, automation: Automation) -> str:
        if automation.session_mode == "continue" and automation.origin_session_id:
            existing = self.store.get_session(automation.origin_session_id)
            if existing is not None:
                return existing.id

        title_stamp = datetime.now(UTC).strftime("%b %d %H:%M")
        title = (
            automation.name
            if automation.session_mode == "continue"
            else f"{automation.name} · {title_stamp}"
        )
        sess = self.store.create_session(
            title=title,
            workspace_path=automation.workdir,
            project_id=automation.project_id,
            specialist_id=automation.specialist_id,
            source="automation",
            source_label=f"Automation · {automation.schedule_label}",
            client_surface="ui",
            provider=automation.provider_pin,
            model=automation.model_pin,
            automation_id=automation.id,
        )
        if automation.session_mode == "continue" and not automation.origin_session_id:
            self.store.update_automation_fields(
                automation.id, origin_session_id=sess.id
            )
        return sess.id

    async def _dispatch_agent_session_run(
        self,
        session_id: str,
        prompt: str,
    ) -> str:
        if self.agent_service is None:
            # Lightweight fallback when invoked from standalone CLI tick without active LLM loop
            self.store.add_message(
                session_id=session_id,
                role="user",
                content=prompt,
            )
            reply = f"Scheduled prompt recorded for session {session_id}."
            self.store.add_message(
                session_id=session_id,
                role="assistant",
                content=reply,
            )
            return reply

        start_res = self.agent_service.submit_message(
            session_id=session_id,
            content=prompt,
        )
        task = self.agent_service._active_runs.get(session_id)
        if task is not None:
            await asyncio.wait_for(asyncio.shield(task), timeout=600.0)
        messages = self.store.list_messages(session_id)
        for msg in reversed(messages):
            if msg.role == "assistant" and msg.content.strip():
                return msg.content.strip()
        return f"Run {start_res.run_id} completed."

    def _advance_schedule_after_run(
        self,
        automation: Automation,
        *,
        succeeded: bool,
        error: str | None = None,
    ) -> None:
        fresh = self.store.get_automation(automation.id) or automation
        new_count = fresh.run_count + 1
        reached_limit = (
            fresh.repeat_limit is not None and new_count >= fresh.repeat_limit
        ) or fresh.schedule_kind == "once"

        if reached_limit:
            next_enabled = False
            next_run = None
            next_status = "completed" if succeeded else "failed"
        elif not fresh.enabled:
            next_enabled = False
            next_run = None
            next_status = "paused"
        else:
            next_enabled = True
            next_run = compute_next_run(fresh.schedule_expr)
            next_status = "succeeded" if succeeded else "failed"

        self.store.update_automation_fields(
            fresh.id,
            run_count=new_count,
            enabled=next_enabled,
            next_run_at=next_run,
            last_status=next_status,
            last_error=error,
        )

    # --- Background Scheduler Loop & Missed-Run Catch-Up ---

    def reconcile_orphaned_runs(self) -> int:
        """Mark any runs left in `running` from a previous server process as failed."""
        reconciled = 0
        for run in self.store.list_automation_runs(limit=100):
            if (
                run.status == "running"
                and run.automation_id not in self._running_automation_ids
            ):
                self.store.finish_automation_run(
                    run.id,
                    status="failed",
                    error="Interrupted by server restart.",
                )
                reconciled += 1
        return reconciled

    async def tick_once(self, *, catch_up_missed: bool = True) -> list[AutomationRun]:
        """Inspect due automations and fire them. Collapses missed slots into 1 catch-up run."""
        now = datetime.now(UTC)
        fired: list[AutomationRun] = []
        for auto in self.store.list_automations():
            if not auto.enabled or auto.next_run_at is None:
                continue
            due_at = auto.next_run_at
            if due_at.tzinfo is None:
                due_at = due_at.replace(tzinfo=UTC)
            if due_at > now:
                continue

            lag_seconds = (now - due_at).total_seconds()
            is_catchup = lag_seconds > 120.0
            if is_catchup and not catch_up_missed and auto.schedule_kind != "once":
                # Re-anchor to next future occurrence without firing now
                self.store.update_automation_fields(
                    auto.id,
                    next_run_at=compute_next_run(auto.schedule_expr, after=now),
                )
                continue

            try:
                run = await self.trigger_automation(
                    auto.id,
                    trigger_source="catchup" if is_catchup else "schedule",
                    was_catchup=is_catchup,
                    wait=True,
                )
                fired.append(run)
            except Exception as exc:
                logger.warning("Scheduled tick failed for %s: %s", auto.id, exc)
        return fired

    async def start_scheduler_loop(self, poll_seconds: float = 15.0) -> None:
        self._stop_event.clear()
        await asyncio.to_thread(self.reconcile_orphaned_runs)
        while not self._stop_event.is_set():
            try:
                await self.tick_once(catch_up_missed=True)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.debug("Automation scheduler tick error", exc_info=True)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=poll_seconds
                )
            except TimeoutError:
                pass

    def stop_scheduler_loop(self) -> None:
        self._stop_event.set()
        if self._ticker_task is not None and not self._ticker_task.done():
            self._ticker_task.cancel()
